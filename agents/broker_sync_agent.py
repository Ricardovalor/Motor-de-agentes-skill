import asyncio
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
    """
    def __init__(self):
        super().__init__(name="BrokerSyncAgent", role="Order Manager & PnL Sync")
        self.sync_skill = BrokerSyncSkill()
        self.trailing_skill = TrailingStopSkill()
        self._last_written_pnl = None  # Change detection para evitar I/O desnecessário

    async def initialize(self):
        self.logger.info("Broker Sync Agent ligado. Iniciando varredura contínua do DOM (L2 PnL/Trailing)...")
        # Inicia loop de trailing stop
        asyncio.create_task(self.continuous_risk_monitor())

    async def handle_message(self, message):
        pass # Não processa mensagens reativas neste escopo, ele é proativo.

    async def continuous_risk_monitor(self):
        # V16.2: Dynamic trailing threshold from rules.json
        try:
            import json
            rules_paths = [
                os.path.join(os.path.dirname(__file__), "..", "rules.json"),
                r"e:\extratredey\rules.json",
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

        while True:
            try:
                pnl_res = await self.sync_skill.execute({})
                pnl = pnl_res.get("current_daily_pnl", 0.0)
                
                # Só escreve no disco se o PnL realmente mudou (evita I/O desnecessário)
                if pnl != self._last_written_pnl:
                    self._last_written_pnl = pnl
                    import json
                    os.makedirs("memory_data", exist_ok=True)
                    with open("memory_data/live_pnl.json", "w") as f:
                        json.dump({
                            "pnl": pnl,
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }, f)

                # V16.2: Dynamic trailing + DLL safety check
                if pnl > trailing_trigger and pnl > 0:
                    await self.trailing_skill.execute({"new_sl_price": "BREAKEVEN"})
                    self.logger.info(f"Trailing Stop acionado (PnL=${pnl:.2f} > trigger=${trailing_trigger:.2f})")
                elif pnl < -(dll_limit * 0.7):
                    self.logger.warning(f"⚠️ DLL DANGER ZONE: PnL=${pnl:.2f} | DLL Limit=${dll_limit}")
                    
            except Exception as e:
                self.logger.debug(f"Falha no BrokerSync Loop: {e}")
                
            await asyncio.sleep(15)  # Intervalo de 15s
