import logging
from typing import Dict, Any
from core.base import BaseSkill
import datetime
import pytz

logger = logging.getLogger("MacroNews")

class MacroNewsSkill(BaseSkill):
    """
    Skill que simula o rastreamento do Calendário Econômico (Forex Factory / Investing.com)
    e lê feeds de notícias RSS buscando choques de liquidez.
    """
    def __init__(self):
        super().__init__(name="MacroNewsSkill", description="Leitura de Sentimento Macro e Calendário Econômico")
        self.market_tz = pytz.timezone("America/New_York")

    async def execute(self, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Retorna o sentimento macroeconômico atual e avisa sobre "Red Folder News"
        """
        # Em produção real, faríamos um HTTP GET para uma API de calendário econômico.
        # Aqui, vamos simular a lógica de detecção baseada no horário atual.
        
        current_time = datetime.datetime.now(self.market_tz)
        
        # Simulação: Notícias NFP ou CPI geralmente saem 08:30 EST ou FOMC 14:00 EST.
        # Vamos assumir que não há Red Folders no exato milissegundo de hoje, 
        # mas retornamos a estrutura que a IA irá usar.
        
        import urllib.request
        import xml.etree.ElementTree as ET
        
        red_folder_imminent = False
        macro_sentiment = "RISK_ON"
        news_volatility_multiplier = 1.0
        headline = "Aguardando dados macro..."
        
        try:
            # Tenta buscar notícias financeiras reais via RSS (CNBC)
            url = 'https://search.cnbc.com/rs/search/combinedcms/view.xml?profile=12000000&id=10000664'
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            response = urllib.request.urlopen(req, timeout=3)
            xml_data = response.read()
            root = ET.fromstring(xml_data)
            
            # Pega a última notícia
            first_item = root.find('.//item')
            if first_item is not None:
                headline = first_item.find('title').text
                desc = first_item.find('description').text or ""
                
                # Análise simples de sentimento/choque
                text_to_analyze = (headline + " " + desc).lower()
                shock_keywords = ['crash', 'plunge', 'fed', 'rate', 'cpi', 'inflation', 'war', 'missile', 'emergency', 'hike', 'powell']
                
                if any(kw in text_to_analyze for kw in shock_keywords):
                    red_folder_imminent = True
                    macro_sentiment = "UNCERTAIN_SHOCK"
                    news_volatility_multiplier = 0.5 # Corta a convicção pela metade em notícias graves
                    logger.warning(f"🚨 [ALERTA MACRO REAL] Choque detectado: {headline}")
                else:
                    logger.info(f"Macro Calendar Limpo. Última notícia: {headline}")
        except Exception as e:
            logger.warning(f"Falha ao conectar com feed Macro RSS ({e}). Assumindo cenário RISK_ON (sem bloqueio fake).")
            headline = "Feed RSS indisponível — cenário conservador RISK_ON aplicado."
            # Sem dados reais, assumimos cenário limpo (não bloqueamos trades com dados fake)
            logger.info("Macro Calendar indisponível — operando normalmente sem bloqueio arbitrário.")

        return {
            "red_folder_imminent": red_folder_imminent,
            "macro_sentiment": macro_sentiment,
            "news_volatility_multiplier": news_volatility_multiplier,
            "last_headline": headline
        }
