import asyncio
import aiohttp
import json
import logging
import time
import os
from core.base import BaseSkill

class TradingViewTradovateMCPExecutionSkill(BaseSkill):
    """
    Skill de Execução Física via CDP (Chrome DevTools Protocol) / MCP.
    Adaptada para o TradingView DOM com painel Tradovate (Integração Direta).
    "O Braço Robótico HFT".
    
    Acessa a porta 9222 do Chrome para encontrar a aba do TradingView, e injeta
    o comando de compra/venda diretamente no painel de negociação nativo (Tradovate).
    """
    def __init__(self, cdp_host=None, cdp_port=None):
        super().__init__(name="BrowserMCPExecution")
        
        # Resolução Dinâmica Híbrida do Host CDP
        env_host = os.getenv("CDP_HOST")
        if env_host:
            self.cdp_host = env_host
        elif cdp_host:
            self.cdp_host = cdp_host
        else:
            # Detecta se está em container Docker
            if os.path.exists("/.dockerenv") or os.getenv("DOCKER_CONTAINER") == "true":
                self.cdp_host = "host.docker.internal"
            else:
                self.cdp_host = "127.0.0.1"
                
        # Resolução Dinâmica Híbrida da Porta CDP
        env_port = os.getenv("CDP_PORT")
        if env_port:
            try:
                self.cdp_port = int(env_port)
            except ValueError:
                self.cdp_port = 9222
        elif cdp_port:
            self.cdp_port = cdp_port
        else:
            self.cdp_port = 9222
            
        self.logger.info(f"[BrowserMCP] Host de depuração do Chrome resolvido para: {self.cdp_host}:{self.cdp_port}")

    def _generate_tv_dom_payload(self, trade_payload: dict) -> str:
        """
        Gera o código JavaScript para injetar a boleta fisicamente no DOM do TradingView.
        (Mirando o painel Tradovate embutido).
        V16.2: Per-asset tick_size/risk_ticks + seletores com fallback chain.
        """
        signal = trade_payload.get('signal', 'BUY')
        price = trade_payload.get('price', 0.0)
        rr_ratio = trade_payload.get('target_take_profit', 2.0)
        asset = trade_payload.get('asset', 'MNQ')
        qty = trade_payload.get('qty', 1)
        
        # BUG-07 FIX: Per-asset parameters (MNQ vs MGC)
        # TITAN-007 FIX: Adicionados MES e M6E (antes caíam no fallback MNQ errado)
        ASSET_PARAMS = {
            "MNQ": {"tick_size": 0.25, "tick_value": 0.50, "risk_ticks": 40},  # 10 pts SL = $20
            "MGC": {"tick_size": 0.10, "tick_value": 1.00, "risk_ticks": 30},  # 3 pts SL = $30
            "MES": {"tick_size": 0.25, "tick_value": 1.25, "risk_ticks": 32},  # 8 pts SL = $40
            "M6E": {"tick_size": 0.0001, "tick_value": 1.25, "risk_ticks": 40},  # 40 pips SL
        }
        params = ASSET_PARAMS.get(asset, ASSET_PARAMS["MNQ"])
        tick_size = trade_payload.get('tick_size', params["tick_size"])
        risk_ticks = trade_payload.get('risk_ticks', params["risk_ticks"])
        
        if signal == "LONG" or signal == "BUY":
            sl_price = price - (risk_ticks * tick_size)
            tp_price = price + (risk_ticks * tick_size * rr_ratio)
            btn_selectors = "[data-name='buy-button'], .tv-trading-buy-button, button.buy, button[class*='buyButton'], button[class*='Buy'], .orderWidgetContent button.buy"
        else:
            sl_price = price + (risk_ticks * tick_size)
            tp_price = price - (risk_ticks * tick_size * rr_ratio)
            btn_selectors = "[data-name='sell-button'], .tv-trading-sell-button, button.sell, button[class*='sellButton'], button[class*='Sell'], .orderWidgetContent button.sell"

        # JS injetado remotamente na aba do TradingView via CDP WebSocket
        js_code = f"""
        (function() {{
            console.log('Nexus Zenith V16.2 Injetando Ordem {signal} ({asset}) no TradingView...');
            
            // Helper: tenta múltiplos seletores (fallback chain)
            function findEl(selectors) {{
                for (const sel of selectors.split(',')) {{
                    const el = document.querySelector(sel.trim());
                    if (el) return el;
                }}
                return null;
            }}
            
            function setInputValue(el, value) {{
                if (!el) return false;
                const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                    window.HTMLInputElement.prototype, 'value'
                ).set;
                nativeInputValueSetter.call(el, value);
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                return true;
            }}
            
            // 1. Configurar Quantidade
            const qtyInput = findEl('[data-name="qty-input"], .js-order-ticket-qty, input[name="qty"], input[class*="qty"], input[class*="Qty"], .orderWidgetContent input[type="number"]');
            setInputValue(qtyInput, '{qty}');

            // 2. TP e SL
            const tpToggle = findEl('[data-name="tp-checkbox"], .js-tp-toggle, input[class*="takeProfitCheckbox"], [data-name="take-profit-toggle"]');
            if(tpToggle && !tpToggle.checked) tpToggle.click();
            
            const slToggle = findEl('[data-name="sl-checkbox"], .js-sl-toggle, input[class*="stopLossCheckbox"], [data-name="stop-loss-toggle"]');
            if(slToggle && !slToggle.checked) slToggle.click();
            
            const tpInput = findEl('[data-name="tp-input"], .js-tp-value, input[name="tp"], input[class*="takeProfitInput"], [data-name="take-profit-price"] input');
            setInputValue(tpInput, '{tp_price}');
            
            const slInput = findEl('[data-name="sl-input"], .js-sl-value, input[name="sl"], input[class*="stopLossInput"], [data-name="stop-loss-price"] input');
            setInputValue(slInput, '{sl_price}');
            
            // 3. Clicar no botão Comprar/Vender a Mercado
            const execBtn = findEl('{btn_selectors}');
            if (execBtn) {{
                execBtn.click();
                return 'DOM_TV_INJECTION_SUCCESS';
            }} else {{
                return 'ERROR_BUTTON_NOT_FOUND';
            }}
        }})();
        """
        return js_code

    async def _inject_js_payload(self, session: aiohttp.ClientSession, ws_url: str, js_code: str) -> dict:
        """Envia o payload via WebSocket CDP real para injeção na aba do Chrome."""
        try:
            async with session.ws_connect(ws_url, timeout=3.0) as ws:
                # O CDP precisa de idenas sequenciais
                msg = {
                    "id": 1,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": js_code,
                        "returnByValue": True
                    }
                }
                await ws.send_json(msg)
                response = await ws.receive_json()
                
                if "result" in response and "result" in response["result"]:
                    exec_result = response["result"]["result"].get("value")
                    self.logger.info(f"[CDP] Resposta do Node (Tradovate): {exec_result}")
                    return {"status": "SUCCESS", "cdp_response": exec_result}
                else:
                    self.logger.warning(f"[CDP] Erro na injeção DOM: {response}")
                    return {"status": "FAILED", "cdp_response": response}
        except Exception as e:
            self.logger.error(f"[CDP] Falha na conexão WebSocket: {e}")
            return {"status": "ERROR", "error": str(e)}

    async def execute(self, trade_payload: dict) -> dict:
        self.logger.info(f"Iniciando protocolo de execução DOM via MCP para TradingView (Tradovate Panel) - {trade_payload.get('asset')}")
        
        target_url = f"http://{self.cdp_host}:{self.cdp_port}/json"
        exec_status = "MOCK_FALLBACK"
        start_time = time.monotonic()
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(target_url, timeout=2.0) as response:
                    if response.status == 200:
                        tabs = await response.json()
                        tv_tabs = [t for t in tabs if 'tradingview.com' in t.get('url', '')]
                        
                        if tv_tabs:
                            ws_url = tv_tabs[0].get('webSocketDebuggerUrl')
                            self.logger.info(f"[MCP-CDP] Aba do TradingView Localizada! WebSocket: {ws_url}")
                            js_payload = self._generate_tv_dom_payload(trade_payload)
                            
                            self.logger.info(f"[CDP] Disparando Payload JS para o painel TradingView->Tradovate!")
                            # TITAN-008: Passa a sessão aiohttp aquecida para reutilização
                            injection_result = await self._inject_js_payload(session, ws_url, js_payload)
                            if injection_result["status"] == "SUCCESS":
                                exec_status = "SUCCESS_INJECTED"
                            else:
                                self.logger.warning(f"[MCP-CDP] Injeção DOM falhou: {injection_result}")
                        else:
                            self.logger.warning("[MCP-CDP] Aba do TradingView não encontrada na porta 9222.")
                    else:
                        self.logger.warning("[MCP-CDP] Chrome host inacessível na 9222.")
                        
        except Exception as e:
            self.logger.warning(f"[MCP-CDP] Falha na ponte CDP/Host: {e}. Fallback sem execução.")

        # Latência REAL medida do round-trip completo
        real_latency_ms = round((time.monotonic() - start_time) * 1000, 2)

        return {
            "execution_status": exec_status,
            "execution_latency_ms": real_latency_ms,
            "broker_ticket_id": f"APEX-TRADOVATE-{trade_payload.get('asset')}-X9",
            "dom_injected": exec_status == "SUCCESS_INJECTED",
            "routing": "TradingView_Tradovate_Panel"
        }
