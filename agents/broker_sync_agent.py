import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from core.base import BaseAgent
from skills.broker_skills import BrokerSyncSkill, TrailingStopSkill

class BrokerSyncAgent(BaseAgent):
    """
    Agente de Sincronização e Manejo de Risco Físico.
    Rodando em loop contínuo para:
    1. Monitorar o Saldo Flutuante e ativar o Killswitch.
    2. Arrastar o Stop Loss via Trailing StopSkill (Breakeven Automático).
    
    TITAN-006 FIX: Trailing agora usa entry_price real (não string "0").
    TITAN-009 FIX: Loop respeita _should_stop para shutdown graceful.
    TITAN-012 FIX: import json movido para o topo do arquivo.
    """
    def __init__(self):
        super().__init__(name="BrokerSyncAgent", role="Order Manager & PnL Sync")
        self.sync_skill = BrokerSyncSkill()
        self.trailing_skill = TrailingStopSkill()
        self._last_written_pnl = None  # Change detection para evitar I/O desnecessário
        self._should_stop = False  # TITAN-009: Flag de shutdown graceful
        self._active_entry_price = 0.0  # TITAN-006: Armazena preço de entrada real

    async def initialize(self):
        await super().initialize()  # FIX: Registra no bus + log de startup
        self.logger.info("Broker Sync Agent ligado. Iniciando varredura contínua do DOM (L2 PnL/Trailing)...")
        
        # Escuta trade_receipt para capturar entry_price real (TITAN-006)
        self.bus.subscribe("trade_receipt", self)
        
        # FIX: Callback para capturar erros do loop contínuo (mesmo padrão que BUG-C03)
        def _on_monitor_crash(task):
            if not task.cancelled() and task.exception():
                self.logger.critical(f"🔴 CRITICAL: BrokerSync monitor crashed: {task.exception()}")
        
        task = asyncio.create_task(self.continuous_risk_monitor())
        task.add_done_callback(_on_monitor_crash)

    async def handle_message(self, message):
        """
        TITAN-006 FIX: Captura o entry_price do trade_receipt
        para usar no trailing stop (breakeven real).
        """
        if message.topic == "trade_receipt":
            trade_data = message.payload.get("trade_payload", {})
            entry = trade_data.get("entry_price", 0.0)
            if entry > 0:
                self._active_entry_price = entry
                self.logger.info(f"TITAN-006: Entry price capturado para trailing: ${entry}")

    async def continuous_risk_monitor(self):
        # V10.5: Dynamic trailing threshold from rules.json
        try:
            rules_paths = [
                os.path.join(os.path.dirname(__file__), "..", "rules.json"),
                # TITAN-021 FIX: Path explícito absoluto para a base de regras (evitando falhas em E:)
                r"e:\extratredey\rules.json",
                # Fallback antigo mantido por precaução
                os.path.join(os.path.expanduser("~"), "extratredey", "rules.json"),
            ]
            rules = {}
            for rp in rules_paths:
                if os.path.exists(rp):
                    with open(rp, "r", encoding="utf-8") as f:
                        rules = json.load(f)
                    break
        except Exception:
            rules = {}

        account_size = rules.get("account_size", 50000)
        # Trailing activates at 0.4% of account (e.g., $200 for 50K)
        trailing_trigger = account_size * 0.004
        dll_limit = rules.get("max_daily_loss", 1000)
        
        # MARKET CLOSE CONFIG (rules.json)
        market_close = rules.get("market_close", {})
        auto_flatten_time = market_close.get("auto_flatten_time", "16:55")
        warning_minutes = market_close.get("warning_minutes", [15, 5, 1])
        close_time_str = market_close.get("close_time", "16:59")
        _flatten_triggered_today = None  # Evita flatten duplicado

        # TITAN-009 FIX: Loop respeita flag de shutdown graceful
        while not self._should_stop:
            try:
                # === PNL SYNC ===
                # TITAN-023 FIX: Tenta via REST API primeiro
                tradovate_skill = self.skills.get("TradovateAPI")
                pnl = None
                
                if tradovate_skill:
                    try:
                        pnl = await tradovate_skill.get_open_pnl()
                    except Exception as e:
                        self.logger.error(f"Erro ao obter PnL via API: {e}")
                
                if pnl is None:
                    # Fallback para o CDP SyncSkill
                    pnl_res = await self.sync_skill.execute({})
                    pnl = pnl_res.get("current_daily_pnl", 0.0)
                
                # Só escreve no disco se o PnL realmente mudou (evita I/O desnecessário)
                if pnl != self._last_written_pnl:
                    self._last_written_pnl = pnl
                    os.makedirs("memory_data", exist_ok=True)
                    with open("memory_data/live_pnl.json", "w") as f:
                        json.dump({
                            "pnl": pnl,
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }, f)

                # === TRAILING STOP + DLL CHECK ===
                if pnl > trailing_trigger and pnl > 0:
                    # TITAN-006 FIX: Usa entry_price real para breakeven
                    if self._active_entry_price > 0:
                        breakeven_price = str(self._active_entry_price)
                        self.logger.info(
                            f"Trailing Stop → Breakeven real @ ${self._active_entry_price} "
                            f"(PnL=${pnl:.2f} > trigger=${trailing_trigger:.2f})"
                        )
                    else:
                        breakeven_price = "0"
                        self.logger.warning(
                            "TITAN-006: Entry price não disponível para trailing. "
                            "Usando 0 (breakeven genérico CDP)."
                        )
                    # TITAN-022 FIX: Tenta via REST API primeiro (Institucional DMA)
                    tradovate_skill = self.skills.get("TradovateAPI")
                    if tradovate_skill and self._active_entry_price > 0:
                        try:
                            working_orders = await tradovate_skill.get_working_orders()
                            stop_orders = [o for o in working_orders if o.get("orderType") == "Stop"]
                            if stop_orders:
                                for stop_order in stop_orders:
                                    order_id = stop_order.get("id")
                                    order_qty = stop_order.get("orderQty", 1)
                                    order_type = stop_order.get("orderType", "Stop")
                                    await tradovate_skill.modify_order(order_id, order_qty, order_type, float(breakeven_price), is_stop=True)
                                self.logger.info("API Trailing Stop executado via Tradovate REST API.")
                            else:
                                self.logger.warning("Nenhuma ordem Stop encontrada para Trailing via API.")
                        except Exception as e:
                            self.logger.error(f"Erro no Trailing Stop API: {e}")
                    else:
                        # Fallback legacy CDP
                        await self.trailing_skill.execute({"new_sl_price": breakeven_price})
                elif pnl < -(dll_limit * 0.7):
                    self.logger.warning(f"⚠️ DLL DANGER ZONE: PnL=${pnl:.2f} | DLL Limit=${dll_limit}")
                
                # === MARKET CLOSE AUTO-FLATTEN (EOD Compliance) ===
                try:
                    import pytz
                    ny_now = datetime.now(pytz.timezone("America/New_York"))
                    today_str = ny_now.strftime("%Y-%m-%d")
                    
                    # Parse close/flatten times
                    close_h, close_m = map(int, close_time_str.split(":"))
                    flatten_h, flatten_m = map(int, auto_flatten_time.split(":"))
                    minutes_to_close = (close_h * 60 + close_m) - (ny_now.hour * 60 + ny_now.minute)
                    
                    # Warning alerts
                    if minutes_to_close in warning_minutes:
                        self.logger.warning(f"⏰ MARKET CLOSE WARNING: {minutes_to_close} minuto(s) para o fechamento ({close_time_str} NY)")
                    
                    # Auto-flatten at configured time (e.g., 16:55)
                    if (ny_now.hour == flatten_h and ny_now.minute >= flatten_m and 
                        _flatten_triggered_today != today_str):
                        _flatten_triggered_today = today_str
                        self.logger.critical(f"🔴 MARKET CLOSE AUTO-FLATTEN ATIVADO ({auto_flatten_time} NY)!")
                        self.logger.critical("Zerando todas as posições para compliance EOD Apex...")
                        
                        # Tenta flatten via Tradovate API
                        try:
                            if self.bus:
                                from core.engine import Message
                                await self.bus.publish(Message(
                                    sender=self.name,
                                    topic="emergency_flatten",
                                    payload={"reason": "MARKET_CLOSE_EOD", "time": auto_flatten_time}
                                ))
                            else:
                                self.logger.error("Bus não disponível para flatten EOD.")
                        except Exception as flatten_err:
                            self.logger.error(f"Falha no flatten via API: {flatten_err}. CDP fallback necessário.")
                            
                except Exception as tz_err:
                    self.logger.debug(f"Erro no Market Close check: {tz_err}")
                    
            except Exception as e:
                self.logger.debug(f"Falha no BrokerSync Loop: {e}")
                
            await asyncio.sleep(15)  # Intervalo de 15s
        
        self.logger.info("BrokerSync loop encerrado (shutdown graceful).")
