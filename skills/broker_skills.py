import asyncio
import aiohttp
import json
import logging
import re
from core.base import BaseSkill

logger = logging.getLogger("BrokerSkills")

class BrokerSyncSkill(BaseSkill):
    """
    1. Broker Sync Agent (O Fim do Mock PnL)
    Lê a "Janela de Posições Abertas" do Tradovate no TradingView,
    capturando o saldo flutuante (Floating PnL).
    """
    def __init__(self, cdp_host="host.docker.internal", cdp_port=9222):
        super().__init__(name="BrokerSyncSkill")
        self.cdp_host = cdp_host
        self.cdp_port = cdp_port

    async def _evaluate_cdp(self, js_code: str):
        target_url = f"http://{self.cdp_host}:{self.cdp_port}/json"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(target_url, timeout=2.0) as response:
                    if response.status == 200:
                        tabs = await response.json()
                        tv_tabs = [t for t in tabs if 'tradingview.com' in t.get('url', '')]
                        if tv_tabs:
                            ws_url = tv_tabs[0].get('webSocketDebuggerUrl')
                            async with session.ws_connect(ws_url, timeout=3.0) as ws:
                                msg = {
                                    "id": 1,
                                    "method": "Runtime.evaluate",
                                    "params": {"expression": js_code, "returnByValue": True}
                                }
                                await ws.send_json(msg)
                                ws_resp = await ws.receive_json()
                                if "result" in ws_resp and "result" in ws_resp["result"]:
                                    return ws_resp["result"]["result"].get("value")
        except Exception as e:
            logger.debug(f"[BrokerSync] Erro ao ler CDP: {e}")
        return None

    async def execute(self, params: dict) -> dict:
        # JS para buscar a PnL aberta. O Tradovate no TradingView geralmente exibe em classes específicas.
        # Aqui injetamos uma lógica heurística para capturar o valor financeiro do PnL (Ex: "$ 150.00")
        js_code = """
        (function() {
            // Busca elementos que contenham PnL na barra de rodapé do Paper Trading / Tradovate
            const pnlElements = document.querySelectorAll('.tv-account-manager__text.tv-account-manager__text--profit, .tv-account-manager__text.tv-account-manager__text--loss, [data-name="account-manager-pnl"]');
            for (let el of pnlElements) {
                if (el.innerText.includes('$') || el.innerText.includes('USDT')) {
                    return el.innerText;
                }
            }
            return "0.00";
        })();
        """
        result = await self._evaluate_cdp(js_code)
        
        real_pnl = 0.0
        if result and isinstance(result, str):
            # Extrair números
            numbers = re.findall(r'[-+]?\d*\.\d+|\d+', result.replace(',', ''))
            if numbers:
                real_pnl = float(numbers[0])
                if '-' in result or 'loss' in result.lower():
                    real_pnl = -abs(real_pnl)
                    
        return {"current_daily_pnl": real_pnl}

class TrailingStopSkill(BrokerSyncSkill):
    """
    2. Trailing Stop via WebSocket
    Move o Stop Loss dinamicamente acompanhando o preço via DOM injection.
    """
    def __init__(self, cdp_host="host.docker.internal", cdp_port=9222):
        super().__init__(cdp_host, cdp_port)
        self.name = "TrailingStopSkill"

    async def execute(self, params: dict) -> dict:
        new_sl = params.get("new_sl_price")
        if not new_sl:
            return {"status": "ignored", "reason": "No new_sl_price provided"}

        js_code = f"""
        (function() {{
            // Simula clique na ordem ativa no gráfico e edição do campo Stop Loss
            const slInput = document.querySelector('[data-name="sl-input"]');
            if(slInput) {{ 
                slInput.value = '{new_sl}'; 
                slInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
                
                const modifyBtn = document.querySelector('[data-name="modify-button"]');
                if (modifyBtn) modifyBtn.click();
                return 'TRAILING_STOP_MOVED';
            }}
            return 'NO_OPEN_ORDER_FOUND';
        }})();
        """
        result = await self._evaluate_cdp(js_code)
        return {"status": "success", "cdp_response": result}

class MarketDepthL2Skill(BrokerSyncSkill):
    """
    3. Análise de Tape (Book de Ofertas Dinâmico L2)
    Acessa o DOM Depth of Market do TradingView para ler a Absorção (Baleias).
    """
    def __init__(self, cdp_host="host.docker.internal", cdp_port=9222):
        super().__init__(cdp_host, cdp_port)
        self.name = "MarketDepthL2Skill"

    async def execute(self, params: dict) -> dict:
        js_code = """
        (function() {
            // Varre o painel DOM do TradingView (L2 Order Book)
            const bidElements = document.querySelectorAll('.dom-bid-volume');
            const askElements = document.querySelectorAll('.dom-ask-volume');
            
            let total_bids = 0;
            let total_asks = 0;
            
            bidElements.forEach(el => total_bids += parseFloat(el.innerText || 0));
            askElements.forEach(el => total_asks += parseFloat(el.innerText || 0));
            
            // Se o painel DOM não está aberto, retorna zeros reais (NÃO dados fake)
            return JSON.stringify({"bids": total_bids, "asks": total_asks});
        })();
        """
        result = await self._evaluate_cdp(js_code)
        try:
            depth_data = json.loads(result) if result else {"bids": 0, "asks": 0}
        except Exception:
            depth_data = {"bids": 0, "asks": 0}

        # Se não há dados reais do DOM, retornar status explícito para decisão segura
        if depth_data["bids"] == 0 and depth_data["asks"] == 0:
            logger.warning("[L2] DOM não disponível — retornando NO_DATA (sem dados fake)")
            return {
                "l2_imbalance": 0,
                "absorption_detected": False,
                "dominant_force": "UNKNOWN",
                "data_available": False
            }
            
        imbalance = depth_data["bids"] - depth_data["asks"]
        absorption_detected = abs(imbalance) > 1500

        return {
            "l2_imbalance": imbalance,
            "absorption_detected": absorption_detected,
            "dominant_force": "BUYERS" if imbalance > 0 else "SELLERS",
            "data_available": True
        }
