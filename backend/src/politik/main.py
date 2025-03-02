"""
Motion Generator API

Ett API för att generera motioner med Grok 2 och statistik från Kolada.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, field_validator, constr, Field
from fastapi.middleware.cors import CORSMiddleware
import requests
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging
from dotenv import load_dotenv
import os
import time

from politik.kolada_v2 import KoladaClient, KoladaError, NoDataError, ValidationError
from politik.statistics import StatisticsType, format_statistic, format_trend, get_kpi_config, get_municipality_id
from .bra_statistics import BRAStatistics

# Konfigurera logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Ladda miljövariabler
load_dotenv()
XAI_API_KEY = os.getenv("XAI_API_KEY")
XAI_URL = "https://api.x.ai/v1/chat/completions"
MODEL_NAME = "grok-2-latest"

if not XAI_API_KEY:
    raise ValueError("XAI_API_KEY saknas i .env filen")

# Skapa en global instans av Kolada-klienten
kolada_client = KoladaClient()

app = FastAPI(
    title="SD Motion Generator API",
    description="API för att generera motioner med Grok 2 och statistik från Kolada",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_current_year() -> int:
    return datetime.now().year

class MotionRequest(BaseModel):
    """Request-modell för att generera en motion."""
    topic: str = Field(..., min_length=1)
    statistics: Optional[List[StatisticsType]] = []
    year: Optional[int] = Field(default=None)
    municipality: Optional[str] = Field(default="karlstad")

    @field_validator('year')
    def set_default_year(cls, v):
        return v or datetime.now().year

    @field_validator('topic')
    def topic_not_empty(cls, v):
        if not v.strip():
            raise ValueError('Topic cannot be empty or just whitespace')
        return v.strip()

    @field_validator('municipality')
    def validate_municipality(cls, v):
        if v and not get_municipality_id(v):
            raise ValueError(f'Okänd kommun: {v}. Måste vara en kommun i Värmland.')
        return v.lower()

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "topic": "trygghet",
                "statistics": ["befolkning", "trygghet"],
                "year": 2024,
                "municipality": "karlstad"
            }
        }
    )

def call_grok(prompt: str, role: str, max_retries: int = 3, timeout: int = 60) -> str:
    """Anropa x.ai's Grok API med given prompt och roll."""
    for attempt in range(max_retries):
        try:
            # Exponentiell backoff mellan försök
            if attempt > 0:
                wait_time = min(30, (2 ** attempt) * 5)  # Max 30 sekunder väntetid
                logger.info(f"Väntar {wait_time} sekunder innan nästa försök...")
                time.sleep(wait_time)
            
            headers = {
                "Authorization": f"Bearer {XAI_API_KEY}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": MODEL_NAME,
                "messages": [
                    {
                        "role": "system",
                        "content": role
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.7
            }
            
            response = requests.post(XAI_URL, json=data, headers=headers, timeout=timeout)
            
            if response.status_code != 200:
                error_msg = f"Grok API Error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                if attempt == max_retries - 1:
                    raise HTTPException(status_code=500, detail=error_msg)
                continue
            
            result = response.json()
            if "choices" not in result or not result["choices"]:
                error_msg = "Grok API Error: Invalid response format"
                logger.error(error_msg)
                if attempt == max_retries - 1:
                    raise HTTPException(status_code=500, detail=error_msg)
                continue
                
            return result["choices"][0]["message"]["content"]

        except requests.Timeout:
            error_msg = f"Grok API Error: Request timed out (attempt {attempt + 1}/{max_retries})"
            logger.error(error_msg)
            if attempt == max_retries - 1:
                raise HTTPException(status_code=504, detail=error_msg)
            continue
            
        except Exception as e:
            error_msg = f"Grok API Error: {str(e)} (attempt {attempt + 1}/{max_retries})"
            logger.error(error_msg)
            if attempt == max_retries - 1:
                raise HTTPException(status_code=500, detail=error_msg)
            continue

    raise HTTPException(status_code=500, detail=f"Grok API Error: All {max_retries} attempts failed")

def agent_1_suggestion(topic: str) -> str:
    """Generera initial förslag med Grok."""
    role = (
        "Du är en erfaren politisk strateg för Sverigedemokraterna med djup förståelse för kommunal politik. "
        "Din uppgift är att föreslå EN genomförbar motion som:\n"
        "1. Ligger inom kommunens juridiska befogenheter\n"
        "2. Har en realistisk ekonomisk kalkyl\n"
        "3. Kan implementeras inom en rimlig tidsram\n"
        "4. Har stöd i tillgänglig statistik\n"
        "5. Bidrar till kommunens långsiktiga mål\n\n"
        "OBS: Generera endast EN sammanhållen motion, inte flera separata motioner.\n\n"
        "Du har tillgång till följande statistiktyper från Kolada som ska användas för att stödja förslaget:\n"
        "- Befolkning (N01900): Demografisk utveckling\n"
        "- Trygghet (N07403): Antal anmälda våldsbrott\n"
        "- Ekonomi (N03101): Kommunens resultat\n"
        "- Invandring (N02955): Andel utrikes födda\n"
        "- Arbetslöshet (N00914): Arbetslöshetssiffror\n"
        "- Socialbidrag (N31816): Ekonomiskt bistånd\n"
        "- Skattesats (N00901): Kommunal skattesats\n\n"
        "Föreslå 2-3 relevanta statistiktyper som stärker argumentationen."
    )
    return call_grok(topic, role)

def agent_2_draft(suggestion: str) -> str:
    """Skapa motion-utkast med Grok."""
    role = (
        "Du är en expert på framgångsrika kommunala motioner. Din uppgift är att skapa "
        "EN övertygande motion som har hög sannolikhet att bli bifallen. "
        "OBS: Skapa endast EN sammanhållen motion, inte flera separata motioner.\n"
        "\nFokusera på:"
        "\n1. Tydlig koppling till kommunens ansvar och befogenheter"
        "\n2. Konkret ekonomisk genomförbarhet med kostnadsuppskattningar"
        "\n3. Realistisk implementeringsplan"
        "\n4. Statistiskt underbyggd argumentation"
        "\n5. Tydliga, mätbara mål"
        "\n\nMotionen ska innehålla:"
        "\n- En koncis bakgrundsbeskrivning med relevant statistik"
        "\n- Tydlig problemformulering"
        "\n- Konkreta att-satser med:"
        "\n  * Specificerade åtgärder"
        "\n  * Uppskattad kostnad"
        "\n  * Förslag på finansiering"
        "\n  * Tidsplan för genomförande"
        "\n\nAnvänd formellt språk och var konkret. Sammanfatta alla åtgärder i EN sammanhållen motion."
    )
    return call_grok(suggestion, role)

def agent_3_improve(draft: str, statistics: List[Dict[str, Any]]) -> str:
    """Förbättra motionen med statistik och ekonomisk realism."""
    if not statistics:
        return draft

    # Skapa en strukturerad sammanfattning av statistiken
    stats_summary = "\n\nStatistiskt underlag och ekonomisk analys:\n"
    crime_stats = None
    
    for stat in statistics:
        # Spara brottsstatistik separat för djupare analys
        if "crimes_per_100k" in stat.get("data", {}):
            crime_stats = stat["data"]
            
        stats_summary += f"\n• {stat['text']}"
        if stat.get('trend'):
            stats_summary += f"\n  Trend: {stat['trend']}"
            
    # Lägg till djupare analys av brottsstatistik om tillgänglig
    if crime_stats:
        stats_summary += "\n\nFördjupad brottsanalys:"
        stats_summary += f"\n• Totalt antal anmälda brott: {crime_stats['total_crimes']:,}".replace(",", " ")
        stats_summary += f"\n• Brott per 100 000 invånare: {crime_stats['crimes_per_100k']:.1f}"
        stats_summary += f"\n• Förändring från föregående år: {crime_stats['change_from_previous_year']:.1f}%"
        
        if crime_stats.get("crimes_by_category"):
            stats_summary += "\n\nBrottskategorier:"
            for category, count in crime_stats["crimes_by_category"].items():
                stats_summary += f"\n• {category}: {count:,}".replace(",", " ")

    # Skapa en förbättrad version med Grok
    role = (
        "Du är en expert på att förbättra kommunala motioner för maximal genomslagskraft. "
        "Din uppgift är att:\n"
        "1. Integrera statistiken naturligt i argumentationen\n"
        "2. Stärka den ekonomiska genomförbarheten\n"
        "3. Tydliggöra kopplingen till kommunens mål\n"
        "4. Säkerställa att varje att-sats är:\n"
        "   - Konkret och mätbar\n"
        "   - Ekonomiskt realistisk\n"
        "   - Tidsmässigt avgränsad\n"
        "5. Behåll motionens grundstruktur men förstärk argumentationen\n"
        "6. Lägg till konkreta exempel på liknande framgångsrika projekt\n"
        "7. Inkludera förslag på uppföljning och utvärdering\n"
        "8. Om brottsstatistik finns:\n"
        "   - Analysera trender och mönster\n"
        "   - Jämför med nationella genomsnitt\n"
        "   - Föreslå evidensbaserade åtgärder\n"
        "   - Inkludera kostnadseffektiva förebyggande insatser"
    )
    
    improved_motion = call_grok(f"Motion:\n{draft}\n\nStatistik och ekonomisk analys:{stats_summary}", role)
    return improved_motion

async def fetch_statistics(stat_type: StatisticsType, year: int, municipality: str) -> Dict[str, Any]:
    """
    Hämta statistik från Kolada eller BRÅ.
    
    Args:
        stat_type: Typ av statistik att hämta
        year: År att hämta statistik för
        municipality: Kommun att hämta statistik för
        
    Returns:
        Dictionary containing formatted statistics and trend information
    """
    try:
        # Hantera BRÅ-statistik separat
        if stat_type == StatisticsType.BRA_STATISTIK:
            async with BRAStatistics() as bra:
                current_stats = await bra.get_crime_statistics(year)
                prev_stats = await bra.get_crime_statistics(year - 1)
            
            # Formatera statistiken
            config = get_kpi_config(stat_type)
            result = {
                "text": config.format_template.format(
                    year=year,
                    value=current_stats["total_crimes"],
                    crimes_per_100k=current_stats["crimes_per_100k"]
                ),
                "data": current_stats
            }
            
            # Lägg till trend om tillgänglig
            if prev_stats:
                result["trend"] = config.trend_template.format(
                    previous_value=prev_stats["total_crimes"],
                    previous_year=year - 1,
                    current_value=current_stats["total_crimes"],
                    current_year=year,
                    change_from_previous_year=current_stats["change_from_previous_year"]
                )
                
            return result
            
        # Hantera Kolada-statistik som tidigare
        municipality_id = get_municipality_id(municipality)
        if not municipality_id:
            raise ValueError(f"Okänd kommun: {municipality}")

        # Hämta aktuell data
        current_data = kolada_client.get_municipality_data(
            kpi_id=get_kpi_config(stat_type).kpi_id,
            municipality_id=municipality_id,
            year=year
        )
        
        # Lägg till kommunnamn för formattering
        current_data["municipality"] = municipality.title()
        
        result = {
            "text": format_statistic(stat_type, current_data),
            "data": current_data
        }
        
        # Försök hämta data för föregående år för trend
        try:
            prev_data = kolada_client.get_municipality_data(
                kpi_id=get_kpi_config(stat_type).kpi_id,
                municipality_id=municipality_id,
                year=year - 1
            )
            # Lägg till kommunnamn för formattering
            prev_data["municipality"] = municipality.title()
            result["trend"] = format_trend(stat_type, current_data, prev_data)
        except (KoladaError, KeyError):
            # Om vi inte kan hämta trend, skippa den
            pass
            
        return result
            
    except NoDataError as e:
        logger.warning(f"Ingen data tillgänglig för {stat_type.value} i {municipality}: {str(e)}")
        return {
            "text": f"Statistik för {stat_type.value} är inte tillgänglig för {municipality} år {year}",
            "data": None
        }
    except ValidationError as e:
        logger.error(f"Ogiltig data för {stat_type.value} i {municipality}: {str(e)}")
        return {
            "text": f"Statistik för {stat_type.value} i {municipality} kunde inte valideras",
            "data": None
        }
    except Exception as e:
        logger.error(f"Fel vid hämtning av {stat_type.value} för {municipality}: {str(e)}")
        return {
            "text": f"Ett fel uppstod vid hämtning av statistik för {stat_type.value} i {municipality}",
            "data": None
        }

@app.get("/")
async def root():
    return {
        "message": "Välkommen till SD Motion Generator API",
        "docs": "/docs",
        "endpoints": {
            "generate_motion": "/api/generate-motion",
            "health": "/health"
        }
    }

@app.post("/api/generate-motion")
async def generate_motion(request: MotionRequest):
    """Generera en motion med Grok 2 och relevant statistik."""
    try:
        # Steg 1: Generera förslag med Grok
        suggestion = agent_1_suggestion(request.topic)
        
        # Steg 2: Skapa motion-utkast med Grok
        draft = agent_2_draft(suggestion)
        
        # Steg 3: Hämta och lägg till statistik
        statistics = []
        if request.statistics:
            for stat_type in request.statistics:
                stat_data = await fetch_statistics(stat_type, request.year, request.municipality)
                if stat_data["data"] is not None:
                    statistics.append(stat_data)
                    
        # Steg 4: Förbättra motionen med statistik
        motion = agent_3_improve(draft, statistics)
        
        return {
            "motion": motion,
            "metadata": {
                "topic": request.topic,
                "municipality": request.municipality,
                "generated": "success",
                "ai_model": MODEL_NAME,
                "statistics": [
                    {
                        "type": stat_type.value,
                        "year": request.year,
                        "municipality": request.municipality,
                        "data": stat["data"]
                    }
                    for stat_type, stat in zip(request.statistics, statistics)
                    if stat["data"] is not None
                ]
            }
        }
    except Exception as e:
        logger.error(f"Ett fel uppstod vid generering av motionen: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Ett fel uppstod vid generering av motionen: {str(e)}"
        )

@app.get("/health")
async def health_check():
    """Kontrollera API:ets status"""
    status = {
        "api": "healthy",
        "kolada": "unknown",
        "ai_service": "unknown"
    }
    
    try:
        # Testa Kolada-anslutningen
        test_data = kolada_client.get_municipality_data(
            "N01900",  # Befolkning
            "1715",    # Karlstad
            datetime.now().year - 1  # Föregående år för att säkerställa data finns
        )
        status["kolada"] = "ok" if test_data else "error"
        
        # Testa AI-tjänsten
        test_response = call_grok("test", "Du är en testassistent. Svara 'OK'.")
        status["ai_service"] = "ok" if test_response else "error"
        
        return status
    except Exception as e:
        status["error"] = str(e)
        return status

@app.get("/api/crime-statistics/{year}")
async def get_crime_statistics(year: int = 2024, crime_type: Optional[str] = None):
    """
    Get crime statistics from BRÅ for a specific year.
    
    Args:
        year: The year to get statistics for (default: 2024)
        crime_type: Optional specific crime type to filter by
        
    Returns:
        Dictionary containing crime statistics
    """
    async with BRAStatistics() as bra:
        return await bra.get_crime_statistics(year, crime_type)

@app.get("/api/crime-trends/{start_year}/{end_year}")
async def get_crime_trends(start_year: int, end_year: int, crime_type: Optional[str] = None) -> Dict:
    """Get crime trends between specified years."""
    current_year = datetime.now().year
    
    if end_year < start_year:
        raise HTTPException(status_code=400, detail="End year cannot be before start year")
        
    if start_year > current_year or end_year > current_year:
        raise HTTPException(status_code=400, detail="Cannot fetch statistics for future years")
    
    try:
        async with BRAStatistics() as bra:
            stats = []
            for year in range(start_year, end_year + 1):
                year_stats = await bra.get_crime_statistics(year, crime_type)
                if year_stats:
                    stats.append(year_stats)
            
            if not stats:
                raise HTTPException(status_code=404, detail="No statistics found for the specified years")
                
            return {
                "years": list(range(start_year, end_year + 1)),
                "values": [s["total_crimes"] for s in stats],
                "trend": "increasing" if stats[-1]["total_crimes"] > stats[0]["total_crimes"] * 1.05
                        else "decreasing" if stats[-1]["total_crimes"] < stats[0]["total_crimes"] * 0.95
                        else "stable"
            }
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) 