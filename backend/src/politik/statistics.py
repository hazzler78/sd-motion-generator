"""
Statistikhantering för motionsgeneratorn.

Detta modul hanterar mappning mellan statistiktyper och KPI:er,
samt formattering och presentation av statistik.
"""

from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

class StatisticsType(Enum):
    """Olika typer av statistik som kan hämtas från Kolada och BRÅ"""
    BEFOLKNING = "befolkning"
    INVANDRING = "invandring"
    ARBETSMARKNAD = "arbetsmarknad"
    TRYGGHET = "trygghet"
    EKONOMI = "ekonomi"
    SKATTESATS = "skattesats"
    SOCIALBIDRAG = "socialbidrag"
    BOSTADSBYGGANDE = "bostadsbyggande"
    SKOLRESULTAT = "skolresultat"
    ALDREOMSORG = "aldreomsorg"
    KULTUR = "kultur"
    BRA_STATISTIK = "bra_statistik"

# Mappning av kommunnamn till kommun-ID för Värmland
VARMLAND_MUNICIPALITIES = {
    "arvika": "1784",
    "eda": "1730",
    "filipstad": "1782",
    "forshaga": "1763",
    "grums": "1764",
    "hagfors": "1783",
    "hammarö": "1761",
    "karlstad": "1715",
    "kil": "1715",
    "kristinehamn": "1781",
    "munkfors": "1762",
    "storfors": "1760",
    "sunne": "1766",
    "säffle": "1785",
    "torsby": "1737",
    "årjäng": "1765"
}

def get_municipality_id(name: str) -> Optional[str]:
    """
    Översätt kommunnamn till kommun-ID
    
    Args:
        name: Kommunens namn (case-insensitive)
        
    Returns:
        Optional[str]: Kommun-ID eller None om kommunen inte hittas
    """
    return VARMLAND_MUNICIPALITIES.get(name.lower())

class KPIConfig:
    """Konfiguration för en KPI"""
    def __init__(
        self,
        name: str,
        kpi_id: str,
        format_type: str,
        format_template: str,
        trend_template: str,
        min_value: Optional[float] = None,
        max_value: Optional[float] = None
    ):
        self.name = name
        self.kpi_id = kpi_id
        self.format_type = format_type
        self.format_template = format_template
        self.trend_template = trend_template
        self.min_value = min_value
        self.max_value = max_value

# Mappning mellan statistiktyper och KPI:er
KPI_MAPPING: Dict[StatisticsType, KPIConfig] = {
    StatisticsType.BEFOLKNING: KPIConfig(
        name="Befolkning",
        kpi_id="N01900",
        format_type="number",
        format_template="{municipality} har {value} invånare ({year})",
        trend_template="Befolkningsutveckling i {municipality}: {previous_value} ({previous_year}) → {current_value} ({current_year})",
        min_value=50000,
        max_value=150000
    ),
    StatisticsType.INVANDRING: KPIConfig(
        name="Utrikes födda",
        kpi_id="N02955",
        format_type="percent",
        format_template="{municipality} har {value}% utrikes födda invånare ({year})",
        trend_template="Utveckling utrikes födda i {municipality}: {previous_value}% ({previous_year}) → {current_value}% ({current_year})",
        min_value=0,
        max_value=100
    ),
    StatisticsType.ARBETSMARKNAD: KPIConfig(
        name="Arbetslöshet",
        kpi_id="N00914",
        format_type="percent",
        format_template="Arbetslösheten i {municipality} är {value}% ({year})",
        trend_template="Utveckling arbetslöshet i {municipality}: {previous_value}% ({previous_year}) → {current_value}% ({current_year})",
        min_value=0,
        max_value=100
    ),
    StatisticsType.TRYGGHET: KPIConfig(
        name="Våldsbrott",
        kpi_id="N07403",
        format_type="number",
        format_template="I {municipality} anmäldes {value} våldsbrott per 100 000 invånare ({year})",
        trend_template="Utveckling av våldsbrott i {municipality}: {previous_value} ({previous_year}) → {current_value} ({current_year})",
        min_value=0,
        max_value=2000
    ),
    StatisticsType.EKONOMI: KPIConfig(
        name="Ekonomiskt resultat",
        kpi_id="N03101",
        format_type="percent",
        format_template="{municipality}s ekonomiska resultat var {value}% av skatter och statsbidrag ({year})",
        trend_template="Ekonomisk utveckling i {municipality}: {previous_value}% ({previous_year}) → {current_value}% ({current_year})",
        min_value=-10,
        max_value=10
    ),
    StatisticsType.SKATTESATS: KPIConfig(
        name="Kommunal skattesats",
        kpi_id="N00406",
        format_type="percent",
        format_template="Den kommunala skattesatsen i Karlstad är {value:.2f}% ({year})",
        trend_template="Utveckling skattesats: {previous_value:.2f}% ({previous_year}) → {current_value:.2f}% ({current_year})",
        min_value=15,
        max_value=35
    ),
    StatisticsType.SOCIALBIDRAG: KPIConfig(
        name="Ekonomiskt bistånd",
        kpi_id="N31816",
        format_type="percent",
        format_template="{value:.1f}% av Karlstads invånare erhöll ekonomiskt bistånd ({year})",
        trend_template="Utveckling ekonomiskt bistånd: {previous_value:.1f}% ({previous_year}) → {current_value:.1f}% ({current_year})",
        min_value=0,
        max_value=100
    ),
    StatisticsType.BOSTADSBYGGANDE: KPIConfig(
        name="Färdigställda bostäder",
        kpi_id="N07906",
        format_type="number",
        format_template="Under {year} färdigställdes {value:,.0f} nya bostäder i Karlstad ({source})",
        trend_template="Utveckling bostadsbyggande: {previous_value:,.0f} bostäder ({previous_year}) → {current_value:,.0f} bostäder ({current_year})",
        min_value=0,
        max_value=2000
    ),
    StatisticsType.SKOLRESULTAT: KPIConfig(
        name="Skolresultat åk 9",
        kpi_id="N15419",
        format_type="percent",
        format_template="{value:.1f}% av eleverna i årskurs 9 uppnådde kunskapskraven i alla ämnen ({year})",
        trend_template="Utveckling skolresultat: {previous_value:.1f}% ({previous_year}) → {current_value:.1f}% ({current_year})",
        min_value=0,
        max_value=100
    ),
    StatisticsType.ALDREOMSORG: KPIConfig(
        name="Brukarbedömning äldreomsorg",
        kpi_id="U23471",
        format_type="percent",
        format_template="{value:.0f}% av brukarna är nöjda med sitt särskilda boende ({year})",
        trend_template="Utveckling nöjdhet äldreboende: {previous_value:.0f}% ({previous_year}) → {current_value:.0f}% ({current_year})",
        min_value=0,
        max_value=100
    ),
    StatisticsType.KULTUR: KPIConfig(
        name="Kulturverksamhet",
        kpi_id="N09100",
        format_type="number",
        format_template="Karlstad spenderar {value:,.0f} kr per invånare på kulturverksamhet ({year})",
        trend_template="Utveckling kulturkostnad: {previous_value:,.0f} kr/inv ({previous_year}) → {current_value:,.0f} kr/inv ({current_year})",
        min_value=0,
        max_value=5000
    ),
    StatisticsType.BRA_STATISTIK: KPIConfig(
        name="Brottsstatistik",
        kpi_id="BRA_TOTAL",
        format_type="number",
        format_template="Under {year} anmäldes {value:,.0f} brott i Sverige, vilket motsvarar {crimes_per_100k:.1f} brott per 100 000 invånare",
        trend_template="Utveckling av anmälda brott: {previous_value:,.0f} ({previous_year}) → {current_value:,.0f} ({current_year}), en förändring med {change_from_previous_year:.1f}%",
        min_value=0,
        max_value=2000000
    ),
}

def get_kpi_config(stat_type: StatisticsType) -> Optional[KPIConfig]:
    """Hämta KPI-konfiguration för en statistiktyp"""
    return KPI_MAPPING.get(stat_type)

def format_value(value: float, format_type: str) -> str:
    """Formatera ett värde baserat på format_type"""
    if format_type == "number":
        return f"{value:,.0f}".replace(",", " ")  # Använd mellanslag som tusentalsavgränsare
    elif format_type == "percent":
        return f"{value:.1f}"
    else:
        return str(value)

def format_statistic(statistic_type: StatisticsType, data: dict) -> str:
    """Formatera ett statistikvärde för en viss typ av statistik"""
    try:
        config = get_kpi_config(statistic_type)
        value = data.get('value')
        year = data.get('year')
        municipality = data.get('municipality', 'Karlstad')  # Default till Karlstad om inget annat anges
        
        if value is None or year is None:
            return f"Kunde inte formatera statistik för {config.name.lower()}: saknar värde eller år"
        
        formatted_value = format_value(value, config.format_type)
        return config.format_template.format(
            municipality=municipality,
            value=formatted_value,
            year=year
        )
    except Exception as e:
        return f"Kunde inte formatera statistik för {statistic_type.name.lower()}: {str(e)}"

def format_trend(statistic_type: StatisticsType, current: dict, previous: dict) -> str:
    """Formatera en trend för en viss typ av statistik"""
    try:
        config = get_kpi_config(statistic_type)
        current_value = current.get('value')
        current_year = current.get('year')
        previous_value = previous.get('value')
        previous_year = previous.get('year')
        municipality = current.get('municipality', 'Karlstad')  # Default till Karlstad om inget annat anges
        
        if any(v is None for v in [current_value, current_year, previous_value, previous_year]):
            return f"Kunde inte formatera trend för {config.name.lower()}: saknar värden eller år"
        
        current_formatted = format_value(current_value, config.format_type)
        previous_formatted = format_value(previous_value, config.format_type)
        
        return config.trend_template.format(
            municipality=municipality,
            previous_value=previous_formatted,
            previous_year=previous_year,
            current_value=current_formatted,
            current_year=current_year
        )
    except Exception as e:
        return f"Kunde inte formatera trend för {statistic_type.name.lower()}: {str(e)}" 