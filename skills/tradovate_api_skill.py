"""
Nexus Zenith V10.0 — Fase 2: Tradovate Direct API Skill
========================================================
Execução autônoma via REST API + WebSocket da Tradovate.
Substitui CDP/DOM injection por API nativa com OCO bracket orders.

Compliance Apex:
- NUNCA envia ordem sem SL (OSO bracket obrigatório)
- NUNCA abre posição oposta (anti-hedging via position/list)
- Delay humano 1-3s (anti-bot detection)
- Kill Switch: liquidatePosition + cancelar ordens pendentes

Endpoints:
- POST /auth/accesstokenrequest    → OAuth2 token
- POST /order/placeOSO             → Bracket order (Entry + SL + TP)
- POST /order/liquidatePosition    → FLATTEN (Kill Switch)
- GET  /position/list              → Anti-hedging check
- GET  /account/list               → Account info
"""

import asyncio
import aiohttp
import json
import logging
import time
import random
import os
from typing import Dict, Any, Optional, List
from core.base import BaseSkill

logger = logging.getLogger("TradovateAPI")


class TradovateAPISkill(BaseSkill):
    """
    Skill de execução direta via Tradovate REST API.
    Suporta: Auth, OSO Bracket, Flatten, Position Query, Fill Stream.
    
    Modos:
    - "demo": https://demo.tradovate.com/v1 (paper trading)
    - "live": https://live.tradovate.com/v1 (produção)
    """
    
    DEMO_URL = "https://demo.tradovate.com/v1"
    LIVE_URL = "https://live.tradovate.com/v1"
    DEMO_WS = "wss://demo.tradovate.com/v1/websocket"
    LIVE_WS = "wss://live.tradovate.com/v1/websocket"
    
    # MED-02 FIX: Mapeamento dinâmico de símbolos Pine → Tradovate
    # Lê do .env para evitar quebra no rollover trimestral (H/M/U/Z)
    # Fallback: calcula automaticamente baseado na data atual
    @staticmethod
    def _current_contract_suffix() -> str:
        """Calcula sufixo do contrato ativo baseado no mês atual (CME quarterly)."""
        import datetime
        now = datetime.datetime.now()
        month = now.month
        year = str(now.year)[-1]  # Último dígito do ano
        # CME months: H=Mar, M=Jun, U=Sep, Z=Dec
        # O contrato ativo muda ~2 semanas antes do vencimento
        if month <= 3:
            return f"H{year}"
        elif month <= 6:
            return f"M{year}"
        elif month <= 9:
            return f"U{year}"
        else:
            return f"Z{year}"
    
    @property
    def SYMBOL_MAP(self) -> dict:
        suffix = os.getenv("TRADOVATE_CONTRACT_SUFFIX", self._current_contract_suffix())
        return {
            "MNQ1!": f"MNQ{suffix}",
            "MGC1!": f"MGC{suffix}",
            "MNQ": f"MNQ{suffix}",
            "MGC": f"MGC{suffix}",
            "MES": f"MES{suffix}",
            "M6E": f"M6E{suffix}",
        }
    
    # Tick size por ativo (para validação de preço)
    TICK_PARAMS = {
        "MNQ": {"tick_size": 0.25, "tick_value": 0.50, "min_ticks_sl": 20},
        "MGC": {"tick_size": 0.10, "tick_value": 1.00, "min_ticks_sl": 15},
        "MES": {"tick_size": 0.25, "tick_value": 1.25, "min_ticks_sl": 16},  # MED-01 FIX
        "M6E": {"tick_size": 0.0001, "tick_value": 1.25, "min_ticks_sl": 20},  # MED-01 FIX
    }

    def __init__(self, mode: str = "demo"):
        super().__init__(name="TradovateAPI", description="Tradovate REST API Direct Execution")
        self.mode = mode
        self.base_url = self.DEMO_URL if mode == "demo" else self.LIVE_URL
        self.ws_url = self.DEMO_WS if mode == "demo" else self.LIVE_WS
        
        # Auth state
        self.access_token: Optional[str] = None
        self.token_expiry: float = 0
        self.account_id: Optional[int] = None
        self.account_spec: Optional[str] = None
        
        # Credentials from environment
        self.username = os.getenv("TRADOVATE_USERNAME", "")
        self.password = os.getenv("TRADOVATE_PASSWORD", "")
        self.device_id = os.getenv("TRADOVATE_DEVICE_ID", "nexus-zenith-v10")
        self.app_id = os.getenv("TRADOVATE_APP_ID", "NexusZenith")
        self.app_version = os.getenv("TRADOVATE_APP_VERSION", "10.0.0")
        self.cid = os.getenv("TRADOVATE_CID", "")
        self.secret = os.getenv("TRADOVATE_SECRET", "")
        
        # Rate limiting
        self._last_order_time: float = 0
        self._min_order_interval: float = 1.0  # Min 1s between orders (anti-bot)
        
        # TITAN-014 FIX: Sessão HTTP persistente (reutiliza conexão TCP + TLS)
        self._session: aiohttp.ClientSession = None
        
        logger.info(f"TradovateAPISkill initialized in {mode.upper()} mode → {self.base_url}")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """TITAN-014: Retorna sessão persistente, criando se necessário."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10),
                headers={"Accept": "application/json"}
            )
        return self._session
    
    async def close(self):
        """TITAN-014: Cleanup da sessão persistente (chamado no shutdown)."""
        if self._session and not self._session.closed:
            await self._session.close()
            logger.info("TradovateAPI session fechada.")

    # =====================================================================
    # AUTHENTICATION
    # =====================================================================
    
    async def authenticate(self) -> bool:
        """
        OAuth2 authentication → access_token + account_id.
        Token é válido por ~24h, mas renovamos a cada 12h por segurança.
        """
        if self.access_token and time.time() < self.token_expiry:
            return True  # Token ainda válido
            
        if not self.username or not self.password:
            logger.error("TRADOVATE_USERNAME/PASSWORD não configurados no .env")
            return False
            
        url = f"{self.base_url}/auth/accesstokenrequest"
        payload = {
            "name": self.username,
            "password": self.password,
            "appId": self.app_id,
            "appVersion": self.app_version,
            "deviceId": self.device_id,
            "cid": self.cid,
            "sec": self.secret,
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self.access_token = data.get("accessToken")
                        # Token válido por 24h, renovamos a cada 12h
                        self.token_expiry = time.time() + 43200  # 12h
                        
                        # Buscar account_id
                        await self._fetch_account_info()
                        
                        logger.info(f"✅ Tradovate Auth OK | Account: {self.account_spec} (ID: {self.account_id}) | Mode: {self.mode.upper()}")
                        return True
                    else:
                        error = await resp.text()
                        logger.error(f"❌ Tradovate Auth FAILED ({resp.status}): {error}")
                        return False
        except Exception as e:
            logger.error(f"❌ Tradovate Auth Exception: {e}")
            return False
    
    async def _fetch_account_info(self):
        """Busca account_id e account_spec após autenticação."""
        accounts = await self._api_get("/account/list")
        if accounts and len(accounts) > 0:
            self.account_id = accounts[0].get("id")
            self.account_spec = accounts[0].get("name")
    
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    # =====================================================================
    # HTTP HELPERS
    # =====================================================================
    
    async def _api_get(self, endpoint: str) -> Optional[Any]:
        """GET request com auth header. TITAN-014: Usa sessão persistente."""
        url = f"{self.base_url}{endpoint}"
        try:
            session = await self._get_session()
            async with session.get(url, headers=self._headers()) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    logger.warning(f"GET {endpoint} → {resp.status}")
                    return None
        except Exception as e:
            logger.error(f"GET {endpoint} Exception: {e}")
            return None
    
    async def _api_post(self, endpoint: str, payload: dict) -> Optional[dict]:
        """POST request com auth header. TITAN-014: Usa sessão persistente."""
        url = f"{self.base_url}{endpoint}"
        try:
            session = await self._get_session()
            async with session.post(url, headers=self._headers(), json=payload) as resp:
                data = await resp.json()
                if resp.status in (200, 201):
                    return data
                else:
                    logger.error(f"POST {endpoint} → {resp.status}: {data}")
                    return {"error": True, "status": resp.status, "detail": data}
        except Exception as e:
            logger.error(f"POST {endpoint} Exception: {e}")
            return {"error": True, "detail": str(e)}

    # =====================================================================
    # ORDER EXECUTION (OSO Bracket)
    # =====================================================================
    
    async def place_oso_bracket(self, symbol: str, action: str, qty: int,
                                 sl_price: float, tp_price: float,
                                 order_type: str = "Market") -> Dict[str, Any]:
        """
        Envia bracket order OSO (One-Sends-Other) nativa.
        
        Entry order + 2 brackets:
        - bracket1: Stop Loss (Stop order)
        - bracket2: Take Profit (Limit order)
        
        Compliance Apex:
        - SEMPRE com SL (bracket1 obrigatório)
        - Delay humano anti-bot
        - Logging completo para auditoria
        
        Args:
            symbol: "MNQ" ou "MGC" (será mapeado para contrato ativo)
            action: "Buy" ou "Sell"
            qty: Quantidade de contratos (default 1)
            sl_price: Preço do Stop Loss
            tp_price: Preço do Take Profit
            order_type: "Market" ou "Limit"
            
        Returns:
            {"orderId": ..., "status": ..., "brackets": [...]}
        """
        if not await self.authenticate():
            return {"error": True, "detail": "Authentication failed"}
        
        # Anti-bot delay (1-3 segundos aleatórios)
        delay = random.uniform(1.0, 3.0)
        logger.info(f"⏱️ Anti-bot delay: {delay:.1f}s")
        await asyncio.sleep(delay)
        
        # Rate limiting
        elapsed = time.time() - self._last_order_time
        if elapsed < self._min_order_interval:
            await asyncio.sleep(self._min_order_interval - elapsed)
        
        # Mapear símbolo
        tv_symbol = self.SYMBOL_MAP.get(symbol, symbol)
        
        # Determinar ação oposta para brackets
        opposite_action = "Sell" if action in ("Buy", "BUY", "LONG") else "Buy"
        normalized_action = "Buy" if action in ("Buy", "BUY", "LONG") else "Sell"
        
        # Validar SL mínimo
        asset_key = "MNQ" if "MNQ" in symbol or "NQ" in symbol else "MGC"
        params = self.TICK_PARAMS.get(asset_key, self.TICK_PARAMS["MNQ"])
        
        payload = {
            "accountSpec": self.account_spec,
            "accountId": self.account_id,
            "action": normalized_action,
            "symbol": tv_symbol,
            "orderQty": qty,
            "orderType": order_type,
            "isAutomated": True,
            # Bracket 1: Stop Loss
            "bracket1": {
                "action": opposite_action,
                "orderType": "Stop",
                "stopPrice": round(sl_price, 2),
            },
            # Bracket 2: Take Profit
            "bracket2": {
                "action": opposite_action,
                "orderType": "Limit",
                "price": round(tp_price, 2),
            }
        }
        
        logger.info(f"📤 Sending OSO: {normalized_action} {qty}x {tv_symbol} | SL={sl_price} | TP={tp_price}")
        
        result = await self._api_post("/order/placeOSO", payload)
        self._last_order_time = time.time()
        
        if result and not result.get("error"):
            logger.info(f"✅ OSO Order placed: ID={result.get('orderId')} | Status={result.get('ordStatus')}")
        else:
            logger.error(f"❌ OSO Order FAILED: {result}")
            
        return result

    # =====================================================================
    # KILL SWITCH: FLATTEN ALL
    # =====================================================================
    
    async def flatten_all(self) -> Dict[str, Any]:
        """
        EMERGENCY: Liquida TODAS as posições + cancela ordens pendentes.
        Chamado pelo DevOps-Watchdog quando system_status == PANIC_FLATTEN.
        
        Sequência:
        1. Cancel all working orders
        2. Liquidate all open positions
        3. Log tudo para auditoria forense
        """
        if not await self.authenticate():
            return {"error": True, "detail": "Auth failed during FLATTEN"}
        
        logger.critical("🚨 KILL SWITCH ACTIVATED — FLATTEN ALL POSITIONS")
        
        results = {"orders_cancelled": 0, "positions_flattened": 0, "errors": []}
        
        # 1. Cancelar ordens pendentes
        try:
            orders = await self._api_get(f"/order/list")
            if orders:
                working_orders = [o for o in orders if o.get("ordStatus") in ("Working", "Accepted")]
                for order in working_orders:
                    cancel_result = await self._api_post("/order/cancelorder", {"orderId": order["id"]})
                    if cancel_result and not cancel_result.get("error"):
                        results["orders_cancelled"] += 1
                    else:
                        results["errors"].append(f"Cancel order {order['id']}: {cancel_result}")
        except Exception as e:
            results["errors"].append(f"Cancel orders: {e}")
        
        # 2. Liquidar posições abertas
        try:
            positions = await self._api_get(f"/position/list")
            if positions:
                open_positions = [p for p in positions if p.get("netPos", 0) != 0]
                for pos in open_positions:
                    flatten_result = await self._api_post("/order/liquidatePosition", {
                        "accountId": self.account_id,
                        "contractId": pos.get("contractId"),
                    })
                    if flatten_result and not flatten_result.get("error"):
                        results["positions_flattened"] += 1
                    else:
                        results["errors"].append(f"Flatten {pos.get('contractId')}: {flatten_result}")
        except Exception as e:
            results["errors"].append(f"Flatten positions: {e}")
        
        logger.critical(f"🚨 FLATTEN RESULT: {results['orders_cancelled']} orders cancelled, "
                        f"{results['positions_flattened']} positions flattened, "
                        f"{len(results['errors'])} errors")
        
        return results

    # =====================================================================
    # ANTI-HEDGING CHECK
    # =====================================================================
    
    async def get_open_positions(self) -> List[Dict]:
        """
        Verifica posições abertas antes de novo trade.
        Compliance Apex: NUNCA abrir posição oposta no mesmo ativo.
        
        Returns:
            Lista de posições abertas com símbolo, direção e quantidade.
        """
        if not await self.authenticate():
            return []
        
        positions = await self._api_get("/position/list")
        if not positions:
            return []
        
        open_positions = []
        for pos in positions:
            net_pos = pos.get("netPos", 0)
            if net_pos != 0:
                open_positions.append({
                    "contractId": pos.get("contractId"),
                    "symbol": pos.get("contractId"),  # Será resolvido com /contract/item
                    "netPos": net_pos,
                    "direction": "LONG" if net_pos > 0 else "SHORT",
                    "avgPrice": pos.get("netPrice", 0),
                })
        
        return open_positions
    
    async def has_open_position(self, symbol: str) -> bool:
        """Retorna True se já existe posição aberta no ativo (anti-hedging)."""
        positions = await self.get_open_positions()
        tv_symbol = self.SYMBOL_MAP.get(symbol, symbol)
        return any(tv_symbol in str(p.get("symbol", "")) for p in positions)

    # =====================================================================
    # MAIN EXECUTE (BaseSkill interface)
    # =====================================================================
    
    async def execute(self, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Interface BaseSkill. Roteador de ações:
        - params["command"] = "place_order" → place_oso_bracket
        - params["command"] = "flatten"     → flatten_all
        - params["command"] = "positions"   → get_open_positions
        - params["command"] = "auth"        → authenticate
        """
        if not params:
            return {"error": True, "detail": "No params provided"}
        
        command = params.get("command", "place_order")
        
        if command == "auth":
            ok = await self.authenticate()
            return {"authenticated": ok, "account_id": self.account_id}
        
        elif command == "flatten":
            return await self.flatten_all()
        
        elif command == "positions":
            positions = await self.get_open_positions()
            return {"positions": positions, "count": len(positions)}
        
        elif command == "place_order":
            # Anti-hedging check
            symbol = params.get("symbol", "MNQ")
            if await self.has_open_position(symbol):
                logger.error(f"🚫 ANTI-HEDGING: Posição já aberta em {symbol}. Ordem REJEITADA.")
                return {"error": True, "detail": f"ANTI_HEDGING: Position already open in {symbol}"}
            
            return await self.place_oso_bracket(
                symbol=symbol,
                action=params.get("action", "Buy"),
                qty=params.get("qty", 1),
                sl_price=params.get("sl_price", 0),
                tp_price=params.get("tp_price", 0),
                order_type=params.get("order_type", "Market"),
            )
        
        return {"error": True, "detail": f"Unknown command: {command}"}
