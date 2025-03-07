"""
Kolada API Client V2

En förbättrad implementation av Kolada API-klienten med bättre felhantering,
caching och validering av data.

Dokumentation: https://github.com/Hypergene/kolada
"""

import requests
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import logging
from enum import Enum
from dataclasses import dataclass
from functools import lru_cache
import json
import httpx

# Konfigurera logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KoladaError(Exception):
    """Basklass för Kolada-relaterade fel"""
    pass

class InvalidKPIError(KoladaError):
    """Kastas när ett ogiltigt KPI anges"""
    pass

class NoDataError(KoladaError):
    """Kastas när ingen data finns tillgänglig"""
    pass

class ValidationError(KoladaError):
    """Kastas när data inte klarar validering"""
    pass

@dataclass
class KPIMetadata:
    """Metadata för ett KPI"""
    id: str
    title: str
    description: str
    municipality_type: bool
    has_municipality_data: bool
    is_numbered: bool
    operating_area: str
    perspective: str
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'KPIMetadata':
        """Skapa en KPIMetadata-instans från API-response"""
        return cls(
            id=data['id'],
            title=data['title'],
            description=data.get('description', ''),
            municipality_type=data.get('municipality_type', True),
            has_municipality_data=data.get('has_municipality_data', True),
            is_numbered=data.get('is_numbered', True),
            operating_area=data.get('operating_area', ''),
            perspective=data.get('perspective', '')
        )

class DataType(Enum):
    """Typer av data som kan hämtas från Kolada"""
    N = "N"  # Numerisk
    P = "P"  # Procent
    T = "T"  # Text

class KoladaClient:
    """
    En förbättrad Kolada API-klient med caching och validering.
    
    Features:
    - Automatisk caching av metadata och vanliga anrop
    - Validering av KPI-koder och data
    - Detaljerad felhantering
    - Stöd för olika datatyper
    """
    
    BASE_URL = "https://api.kolada.se/v2"
    CACHE_TIMEOUT = 3600  # 1 timme
    
    def __init__(self):
        """Initiera klienten med grundläggande konfiguration"""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'KoladaClient/2.0',
            'Accept': 'application/json'
        })
        
    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Gör ett HTTP-anrop till Kolada API:et
        
        Args:
            endpoint: API-endpoint att anropa
            params: Query-parametrar att skicka med
            
        Returns:
            Dict[str, Any]: API-response som dictionary
            
        Raises:
            KoladaError: Om något går fel med anropet
        """
        try:
            url = f"{self.BASE_URL}/{endpoint}"
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"API-anrop misslyckades: {str(e)}")
            raise KoladaError(f"Kunde inte hämta data från Kolada: {str(e)}")
            
    @lru_cache(maxsize=100)
    def get_kpi_metadata(self, kpi_id: str) -> KPIMetadata:
        """
        Hämta metadata för ett specifikt KPI
        
        Args:
            kpi_id: KPI-koden att hämta metadata för
            
        Returns:
            KPIMetadata: Metadata för KPI:t
            
        Raises:
            InvalidKPIError: Om KPI:t inte finns
        """
        try:
            response = self._make_request(f"kpi/{kpi_id}")
            if not response.get('values'):
                raise InvalidKPIError(f"Inget KPI med ID {kpi_id} hittades")
            return KPIMetadata.from_dict(response['values'][0])
        except KoladaError as e:
            raise InvalidKPIError(f"Kunde inte hämta metadata för KPI {kpi_id}: {str(e)}")
            
    def get_municipality_data(
        self,
        kpi_id: str,
        municipality_id: str,
        year: int,
        validate: bool = True
    ) -> Dict[str, Any]:
        """
        Hämta data för ett specifikt KPI och kommun
        
        Args:
            kpi_id: KPI-koden att hämta data för
            municipality_id: Kommun-ID (t.ex. "1715" för Karlstad)
            year: År att hämta data för
            validate: Om True, validera datan innan den returneras
            
        Returns:
            Dict[str, Any]: Dictionary med värdet och metadata
            
        Raises:
            NoDataError: Om ingen data finns för given kombination
            ValidationError: Om datan inte klarar validering
        """
        try:
            # Hämta metadata först för att validera KPI:t
            metadata = self.get_kpi_metadata(kpi_id)
            
            # Hämta data
            response = self._make_request(
                "data/v1/kpi",
                params={
                    "kpi": kpi_id,
                    "municipality": municipality_id,
                    "year": year
                }
            )
            
            if not response.get('values'):
                raise NoDataError(f"No data found for KPI {kpi_id}, municipality {municipality_id}, year {year}")
                
            # Extrahera värdet och året
            try:
                data = response['values'][0]
                if 'values' in data:
                    # New API format
                    value = float(data['values'][0]['value'])
                    actual_year = int(data['period'])
                else:
                    # Old API format
                    value = float(data.get('value', 0))
                    actual_year = int(data.get('period', year))
                    
                # Validera värdet om validate=True
                if validate and not self._validate_value(value, kpi_id):
                    raise ValidationError(f"Value {value} is not valid for KPI {kpi_id}")
                    
                return {
                    "value": value,
                    "year": actual_year,  # Använd året från API-svaret
                    "municipality": municipality_id,
                    "kpi": kpi_id
                }
                
            except (KeyError, ValueError, IndexError) as e:
                raise NoDataError(f"Could not parse value: {str(e)}")
                
        except Exception as e:
            if isinstance(e, (NoDataError, ValidationError)):
                raise
            raise KoladaError(f"Error fetching data: {str(e)}")
        
    def _validate_value(self, value: float, kpi_id: str) -> bool:
        """
        Validera att ett värde är rimligt för ett specifikt KPI
        
        Args:
            value: Värdet att validera
            kpi_id: KPI-koden att validera mot
            
        Returns:
            bool: True om värdet är giltigt
            
        Raises:
            ValidationError: Om värdet är ogiltigt
        """
        # Validera specifika KPIs
        validations = {
            "N01900": lambda x: 50000 <= x <= 150000,  # Befolkning i Karlstad
            "N07403": lambda x: 0 <= x <= 2000,  # Våldsbrott per 100k invånare
            "N03101": lambda x: -1000 <= x <= 1000  # Ekonomiskt resultat
        }
        
        if kpi_id in validations:
            if not validations[kpi_id](value):
                raise ValidationError(f"Value {value} is not valid for KPI {kpi_id}")
            return True
            
        # Grundläggande validering för numeriska värden
        if value is None or value < -100000 or value > 100000:
            raise ValidationError(f"Value {value} is outside reasonable bounds")
        return True
        
    def get_municipality_data_with_fallback(
        self,
        kpi_id: str,
        municipality_id: str,
        target_year: int,
        max_fallback_years: int = 3
    ) -> Dict[str, Any]:
        """
        Hämta data för ett KPI och en kommun med fallback till tidigare år.
        Om data inte finns för målåret, försök med tidigare år.
        
        Args:
            kpi_id: KPI-koden att hämta data för
            municipality_id: Kommun-ID att hämta data för
            target_year: Målår att hämta data för
            max_fallback_years: Max antal år att gå tillbaka
            
        Returns:
            Dict[str, Any]: Dictionary med värdet och metadata
            
        Raises:
            NoDataError: Om ingen data finns för given kombination
            ValidationError: Om datan inte klarar validering
        """
        errors = []
        
        # Försök först med målåret
        try:
            data = self.get_municipality_data(kpi_id, municipality_id, target_year)
            return data
        except (NoDataError, KoladaError) as e:
            errors.append(f"Ingen data för år {target_year}: {str(e)}")
        
        # Om målåret inte finns, hämta lista på tillgängliga år
        available_years = self.get_available_years(kpi_id, municipality_id)
        if not available_years:
            raise NoDataError(f"Ingen data tillgänglig för KPI {kpi_id}, kommun {municipality_id}")
        
        # Filtrera år inom fallback-perioden
        valid_years = [y for y in available_years if y >= target_year - max_fallback_years]
        if not valid_years:
            error_msg = f"Ingen data tillgänglig för KPI {kpi_id}, kommun {municipality_id} "
            error_msg += f"mellan åren {target_year-max_fallback_years} och {target_year}. "
            error_msg += f"Fel: {'; '.join(errors)}"
            raise NoDataError(error_msg)
        
        # Försök med det senaste tillgängliga året
        latest_year = max(valid_years)
        try:
            data = self.get_municipality_data(kpi_id, municipality_id, latest_year)
            return data  # Detta kommer att innehålla det faktiska året som data hämtades för
        except (NoDataError, ValidationError) as e:
            error_msg = f"Kunde inte hämta data för senaste tillgängliga år {latest_year}: {str(e)}"
            raise NoDataError(error_msg)
        
    def get_available_years(self, kpi_id: str, municipality_id: str) -> List[int]:
        """
        Hämta tillgängliga år för ett KPI och en kommun.
        
        Args:
            kpi_id: KPI-koden att kontrollera
            municipality_id: Kommun-ID att kontrollera
            
        Returns:
            List[int]: Lista med tillgängliga år
        """
        try:
            response = self._make_request(
                "data/v1/kpi",
                params={
                    "kpi": kpi_id,
                    "municipality": municipality_id
                }
            )
            
            years = set()
            for item in response.get('values', []):
                # Check both 'year' and 'period' fields
                year = item.get('year') or item.get('period')
                if year:
                    years.add(int(year))
                    
            return sorted(list(years), reverse=True)
            
        except (KoladaError, httpx.HTTPError) as e:
            logger.error(f"Kunde inte hämta tillgängliga år: {str(e)}")
            return []
            
    def get_latest_available_year(self, kpi_id: str, municipality_id: str) -> Optional[int]:
        """
        Hitta det senaste året med tillgänglig data för ett KPI
        
        Args:
            kpi_id: KPI-koden att söka efter
            municipality_id: Kommun-ID
            
        Returns:
            Optional[int]: Senaste året med data, eller None om ingen data finns
        """
        try:
            years = sorted(self.get_available_years(kpi_id, municipality_id), reverse=True)
            for year in years:
                try:
                    data = self.get_municipality_data(kpi_id, municipality_id, year)
                    if data and data["value"] is not None:
                        return year
                except (NoDataError, ValidationError):
                    continue
            return None
        except KoladaError as e:
            logger.error(f"Fel vid datahämtning: {str(e)}")
            return None 