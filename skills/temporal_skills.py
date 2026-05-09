from core.base import BaseSkill
from typing import Dict, Any
import datetime
import pytz
import logging

logger = logging.getLogger("TemporalChronos")

class TemporalChronosSkill(BaseSkill):
    """
    Skill responsável pela Cadeira Temporal do Comitê Neural.
    Implementa as janelas de tempo institucionais (Kill Zones)
    inspiradas no projeto Nexus Zenith V9.4.
    """
    def __init__(self):
        super().__init__(name="TemporalChronosSkill", description="Validação de Kill Zones e Time-based Compliance.")
        # Fuso horário base do mercado de NY (NYSE/CME)
        self.market_tz = pytz.timezone("America/New_York")
        
        # Definição das Kill Zones (Horários em NY Time - EST/EDT)
        self.kill_zones = [
            {"name": "NY AM Session", "start": datetime.time(9, 30), "end": datetime.time(12, 0)},
            {"name": "NY PM Session", "start": datetime.time(13, 30), "end": datetime.time(15, 45)}
        ]

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Avalia se o timestamp atual (ou o passado em params) cai dentro
        de uma janela institucional de alta probabilidade (Kill Zone).
        """
        # Se um timestamp simulado for passado (para backtesting), usamos ele.
        # Caso contrário, usamos a hora real do sistema.
        current_time_utc = params.get("timestamp", datetime.datetime.now(pytz.utc))
        if isinstance(current_time_utc, str):
            try:
                current_time_utc = datetime.datetime.fromisoformat(current_time_utc.replace("Z", "+00:00"))
            except:
                current_time_utc = datetime.datetime.now(pytz.utc)

        # Converter para o fuso horário de NY
        ny_time = current_time_utc.astimezone(self.market_tz).time()
        
        in_kill_zone = False
        active_zone = "Fora de Kill Zone"
        
        for zone in self.kill_zones:
            if zone["start"] <= ny_time <= zone["end"]:
                in_kill_zone = True
                active_zone = zone["name"]
                break
                
        logger.info(f"Avaliação Temporal: {ny_time.strftime('%H:%M')} NY -> {active_zone}")

        return {
            "status": "success",
            "in_kill_zone": in_kill_zone,
            "active_zone": active_zone,
            "ny_time": ny_time.strftime("%H:%M"),
            "confidence_penalty": 0 if in_kill_zone else 0.5 # Corta a confiança pela metade se operar fora do horário
        }
