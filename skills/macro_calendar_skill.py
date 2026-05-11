"""
Nexus Zenith V10.0 — Fase 3: Macro Calendar Skill
===================================================
Calendar-based blackout windows usando ForexFactory JSON API.
Substitui keyword scanning (RSS) por horários estruturados de eventos.

Fonte: https://nfs.faireconomy.media/ff_calendar_thisweek.json
Rate limit: 1 request/hora max (cache local obrigatório)

Regras de Blackout (Compliance Apex):
- T-15 minutos: BLOQUEIA todos os sinais
- T+15 minutos: COOLDOWN (slippage ainda perigoso)  
- T+16 minutos: LIBERA sistema normalmente
"""

import asyncio
import json
import logging
import os
import time
import urllib.request
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from core.base import BaseSkill

logger = logging.getLogger("MacroCalendar")


class MacroCalendarSkill(BaseSkill):
    """
    Skill de calendário econômico com blackout windows.
    Busca eventos de alto impacto USD do ForexFactory e bloqueia
    sinais durante janelas de volatilidade (T-15 a T+15).
    """
    
    CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
    
    # Blackout config (minutos)
    BLACKOUT_PRE_MINUTES = 15    # Bloqueia X min ANTES do evento
    BLACKOUT_POST_MINUTES = 15   # Mantém bloqueio X min DEPOIS
    
    # Cache config
    CACHE_FILE = "memory_data/macro_calendar_cache.json"
    CACHE_TTL_SECONDS = 3600     # 1 hora (respeita rate limit)
    
    # Eventos que SEMPRE bloqueiam (mesmo se impact != High)
    CRITICAL_EVENTS = [
        "Non-Farm Employment Change",
        "Nonfarm Payrolls",
        "CPI m/m", "CPI y/y", "Core CPI",
        "Federal Funds Rate",
        "FOMC Statement", "FOMC Press Conference",
        "GDP q/q", "Advance GDP",
        "Unemployment Rate",
        "ISM Manufacturing PMI",
        "Retail Sales m/m",
        "PPI m/m",
    ]

    def __init__(self):
        super().__init__(
            name="MacroCalendarSkill", 
            description="Economic Calendar with Blackout Windows (ForexFactory)"
        )
        self._cache: List[dict] = []
        self._cache_timestamp: float = 0
        os.makedirs("memory_data", exist_ok=True)

    # =====================================================================
    # DATA FETCHING
    # =====================================================================
    
    async def _fetch_calendar(self) -> List[dict]:
        """
        Busca calendário da semana do ForexFactory via FairEconomy proxy.
        Respeita rate limit de 1 request/hora com cache local.
        """
        # Check cache
        if self._cache and (time.time() - self._cache_timestamp) < self.CACHE_TTL_SECONDS:
            return self._cache
        
        # Check file cache
        if os.path.exists(self.CACHE_FILE):
            try:
                with open(self.CACHE_FILE, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                    cache_age = time.time() - cached.get("timestamp", 0)
                    if cache_age < self.CACHE_TTL_SECONDS:
                        self._cache = cached.get("events", [])
                        self._cache_timestamp = cached.get("timestamp", 0)
                        logger.debug(f"Calendar loaded from file cache ({cache_age:.0f}s old)")
                        return self._cache
            except Exception:
                pass
        
        # Fetch from API
        try:
            req = urllib.request.Request(
                self.CALENDAR_URL,
                headers={"User-Agent": "NexusZenith/10.0"}
            )
            
            def _fetch():
                response = urllib.request.urlopen(req, timeout=10)
                return json.loads(response.read().decode("utf-8"))
            
            events = await asyncio.to_thread(_fetch)
            
            # Filter: USD only, High impact or critical events
            filtered = []
            for event in events:
                country = event.get("country", "")
                impact = event.get("impact", "").lower()
                title = event.get("title", "")
                
                if country != "USD":
                    continue
                    
                is_high_impact = impact in ("high", "red")
                is_critical = any(ce.lower() in title.lower() for ce in self.CRITICAL_EVENTS)
                
                if is_high_impact or is_critical:
                    filtered.append({
                        "title": title,
                        "date": event.get("date", ""),
                        "time": event.get("time", ""),
                        "impact": event.get("impact", ""),
                        "forecast": event.get("forecast", ""),
                        "previous": event.get("previous", ""),
                        "is_critical": is_critical,
                    })
            
            # Save to cache
            self._cache = filtered
            self._cache_timestamp = time.time()
            
            with open(self.CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump({"timestamp": self._cache_timestamp, "events": filtered}, f, indent=2)
            
            logger.info(f"📅 Calendar fetched: {len(filtered)} USD High Impact events this week")
            return filtered
            
        except Exception as e:
            logger.warning(f"Calendar fetch failed: {e}. Using cached data if available.")
            return self._cache or []

    # =====================================================================
    # BLACKOUT LOGIC
    # =====================================================================
    
    def _parse_event_datetime(self, event: dict) -> Optional[datetime]:
        """
        Parseia date+time do evento ForexFactory para datetime.
        Formato: date="2026-05-12", time="8:30am"
        """
        try:
            date_str = event.get("date", "")
            time_str = event.get("time", "")
            
            if not date_str or not time_str or time_str == "All Day":
                return None
            
            # Parse "8:30am" → "08:30"
            time_str = time_str.strip().lower()
            if "am" in time_str or "pm" in time_str:
                dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %I:%M%p")
            else:
                dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            
            return dt
        except Exception:
            return None
    
    def check_blackout(self, events: List[dict], now: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Verifica se estamos em uma janela de blackout.
        
        Returns:
            {
                "blackout_active": True/False,
                "reason": "CPI m/m in 12 minutes",
                "event_title": "CPI m/m",
                "event_time": "08:30",
                "minutes_to_event": 12,
                "action": "BLOCK_ALL_SIGNALS" | "COOLDOWN" | "CLEAR"
            }
        """
        if now is None:
            now = datetime.now()
        
        for event in events:
            event_dt = self._parse_event_datetime(event)
            if event_dt is None:
                continue
            
            delta = (event_dt - now).total_seconds() / 60  # Minutes
            
            # PRE-EVENT: T-15 min
            if 0 < delta <= self.BLACKOUT_PRE_MINUTES:
                return {
                    "blackout_active": True,
                    "reason": f"{event['title']} in {delta:.0f} minutes",
                    "event_title": event["title"],
                    "event_time": event.get("time", ""),
                    "minutes_to_event": delta,
                    "action": "BLOCK_ALL_SIGNALS",
                    "severity": "CRITICAL" if event.get("is_critical") else "HIGH",
                }
            
            # POST-EVENT: T+0 to T+15 min (cooldown)
            if -self.BLACKOUT_POST_MINUTES <= delta <= 0:
                minutes_since = abs(delta)
                return {
                    "blackout_active": True,
                    "reason": f"{event['title']} released {minutes_since:.0f} minutes ago (cooldown)",
                    "event_title": event["title"],
                    "event_time": event.get("time", ""),
                    "minutes_since_event": minutes_since,
                    "action": "COOLDOWN",
                    "severity": "HIGH",
                }
        
        # Encontrar próximo evento
        next_event = None
        min_delta = float("inf")
        for event in events:
            event_dt = self._parse_event_datetime(event)
            if event_dt and event_dt > now:
                delta = (event_dt - now).total_seconds() / 60
                if delta < min_delta:
                    min_delta = delta
                    next_event = event
        
        return {
            "blackout_active": False,
            "reason": "No high-impact events in blackout window",
            "next_event": next_event.get("title") if next_event else None,
            "next_event_time": next_event.get("time") if next_event else None,
            "minutes_to_next": min_delta if next_event else None,
            "action": "CLEAR",
            "severity": "NONE",
        }

    # =====================================================================
    # MAIN EXECUTE (BaseSkill interface)
    # =====================================================================
    
    async def execute(self, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Interface BaseSkill.
        Retorna status do calendário + blackout window.
        """
        events = await self._fetch_calendar()
        blackout = self.check_blackout(events)
        
        if blackout["blackout_active"]:
            logger.warning(f"🚨 BLACKOUT ACTIVE: {blackout['reason']} | Action: {blackout['action']}")
        else:
            next_info = f"Next: {blackout.get('next_event', 'None')} at {blackout.get('next_event_time', 'N/A')}"
            logger.info(f"📅 Calendar CLEAR | {next_info}")
        
        return blackout
