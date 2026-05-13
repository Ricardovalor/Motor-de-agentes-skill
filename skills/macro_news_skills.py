import logging
from typing import Dict, Any
from core.base import BaseSkill
import datetime
import pytz

logger = logging.getLogger("MacroNews")

class MacroNewsSkill(BaseSkill):
    """
    Skill de rastreamento do Calendário Econômico e notícias macro.
    
    TITAN-011 FIX: Provedor RSS (CNBC XML) retornava HTTP 503 em 100% das
    tentativas. Implementado fallback chain com múltiplos provedores:
    1. CNBC RSS (original)
    2. Yahoo Finance RSS (backup)
    3. MarketWatch RSS (backup 2)
    Se todos falharem, opera em modo conservador RISK_ON (não bloqueia trades).
    """
    def __init__(self):
        super().__init__(name="MacroNewsSkill", description="Leitura de Sentimento Macro e Calendário Econômico")
        self.market_tz = pytz.timezone("America/New_York")
        
        # TITAN-011 FIX: Chain de provedores RSS (fallback automático)
        self._rss_feeds = [
            {
                "name": "CNBC Economy",
                "url": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258",
            },
            {
                "name": "Yahoo Finance",
                "url": "https://finance.yahoo.com/news/rssindex",
            },
            {
                "name": "MarketWatch",
                "url": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
            },
        ]

    async def execute(self, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Retorna o sentimento macroeconômico atual e avisa sobre "Red Folder News"
        
        TITAN-011 FIX: Tenta múltiplos provedores RSS em cadeia. Se o primeiro
        falhar (503/timeout), tenta o próximo automaticamente.
        """
        import urllib.request
        import xml.etree.ElementTree as ET
        import asyncio
        
        red_folder_imminent = False
        macro_sentiment = "RISK_ON"
        news_volatility_multiplier = 1.0
        headline = "Aguardando dados macro..."
        feed_source = "NONE"
        
        # TITAN-011 FIX: Tenta cada provedor em sequência até obter sucesso
        for feed in self._rss_feeds:
            try:
                req = urllib.request.Request(
                    feed["url"], 
                    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) NexusZenith/10.5'}
                )
                # MED-04 FIX: Chamada assíncrona (não bloqueia event loop)
                response = await asyncio.to_thread(urllib.request.urlopen, req, timeout=4)
                xml_data = response.read()
                root = ET.fromstring(xml_data)
                
                # Pega a última notícia (estrutura RSS padrão)
                first_item = root.find('.//item')
                if first_item is not None:
                    title_el = first_item.find('title')
                    desc_el = first_item.find('description')
                    headline = title_el.text if title_el is not None else "Sem título"
                    desc = desc_el.text if desc_el is not None else ""
                    feed_source = feed["name"]
                    
                    # Análise de sentimento/choque
                    text_to_analyze = (headline + " " + desc).lower()
                    # GAP-M02 FIX: Frases compostas para evitar falsos positivos
                    shock_keywords = [
                        'crash', 'plunge', 'recession', 'black swan',
                        'fed rate', 'rate hike', 'rate cut', 'interest rate',
                        'fomc', 'powell speaks', 'powell says',
                        'cpi data', 'cpi report', 'core cpi',
                        'inflation surge', 'inflation spike',
                        'missile strike', 'war breaks', 'military',
                        'emergency meeting', 'bank failure',
                        'nonfarm', 'non-farm', 'jobs report',
                    ]
                    
                    if any(kw in text_to_analyze for kw in shock_keywords):
                        red_folder_imminent = True
                        macro_sentiment = "UNCERTAIN_SHOCK"
                        news_volatility_multiplier = 0.5
                        logger.warning(f"🚨 [ALERTA MACRO REAL] Choque detectado via {feed_source}: {headline}")
                    else:
                        logger.info(f"Macro Calendar Limpo via {feed_source}. Última notícia: {headline[:80]}...")
                    
                    # Sucesso — não precisa tentar próximo provedor
                    break
                    
            except Exception as e:
                logger.debug(f"Feed '{feed['name']}' falhou: {e}. Tentando próximo...")
                continue
        
        # Se nenhum provedor funcionou
        if feed_source == "NONE":
            logger.warning(
                "TITAN-011: Todos os provedores RSS falharam. "
                "Operando em modo conservador RISK_ON (sem bloqueio fake)."
            )
            headline = "Todos os feeds RSS indisponíveis — cenário conservador RISK_ON aplicado."

        return {
            "red_folder_imminent": red_folder_imminent,
            "macro_sentiment": macro_sentiment,
            "news_volatility_multiplier": news_volatility_multiplier,
            "last_headline": headline,
            "feed_source": feed_source,  # TITAN-011: Indica qual provedor respondeu
        }
