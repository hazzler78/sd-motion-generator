"""
Module for fetching and processing statistics from BRÅ (Brottsförebyggande rådet) using web scraping.
"""
from typing import Dict, List, Optional, Union
import httpx
from bs4 import BeautifulSoup
import pandas as pd
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)

class BRAStatistics:
    """Class for handling BRÅ statistics through web scraping."""
    
    BASE_URL = "https://bra.se/statistik"
    CRIME_STATS_URL = f"{BASE_URL}/kriminalstatistik.html"
    
    def __init__(self):
        """Initialize the BRÅ statistics handler."""
        self.client = httpx.Client(timeout=30.0, follow_redirects=True)
        self.cache = {}  # Simple cache to avoid repeated requests
        
    async def get_crime_statistics(self, year: int = 2024, 
                                 crime_type: Optional[str] = None) -> Dict[str, Union[int, Dict]]:
        """
        Fetch crime statistics from BRÅ's website for a specific year and crime type.
        
        Args:
            year: The year to fetch statistics for (default: 2024)
            crime_type: Specific type of crime to fetch (optional)
            
        Returns:
            Dictionary containing the crime statistics
        """
        try:
            # Check cache first
            cache_key = f"{year}_{crime_type}"
            if cache_key in self.cache:
                return self.cache[cache_key]
            
            # Fetch the main statistics page
            response = self.client.get(self.CRIME_STATS_URL)
            response.raise_for_status()
            
            # Parse the HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract statistics from the page
            stats = self._extract_statistics(soup, year, crime_type)
            
            # Cache the results
            self.cache[cache_key] = stats
            return stats
            
        except httpx.ReadTimeout:
            raise HTTPException(status_code=504, detail="Timeout when fetching BRÅ statistics")
        except Exception as e:
            logger.error(f"Error fetching BRÅ statistics: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error fetching BRÅ statistics: {str(e)}")
            
    def _extract_statistics(self, soup: BeautifulSoup, year: int, 
                          crime_type: Optional[str] = None) -> Dict[str, Union[int, Dict]]:
        """
        Extract crime statistics from the parsed HTML.
        
        Args:
            soup: BeautifulSoup object of the parsed HTML
            year: Year to extract statistics for
            crime_type: Specific type of crime to extract (optional)
            
        Returns:
            Processed statistics dictionary
        """
        stats = {
            "total_crimes": 0,
            "crimes_by_category": {},
            "crimes_per_100k": 0,
            "change_from_previous_year": 0,
            "year": year,
            "source": "BRÅ (Brottsförebyggande rådet)",
            "data_quality": "preliminary" if year >= 2024 else "final"
        }
        
        try:
            # Find the main statistics container
            main_content = soup.find('main') or soup.find('div', class_='main-content')
            if not main_content:
                return stats
            
            # Extract total number of reported crimes and year-over-year change
            total_crimes_text = main_content.find(string=lambda text: 'anmäldes' in str(text).lower())
            if total_crimes_text:
                text = str(total_crimes_text)
                # Extract number from text
                stats["total_crimes"] = self._extract_number(text)
                
                # Extract year-over-year change from the same text
                if any(word in text.lower() for word in ['ökning', 'minskning']):
                    stats["change_from_previous_year"] = self._extract_percentage(text)
                
            # Extract crime categories
            crime_categories = main_content.find_all('h3') or main_content.find_all('strong')
            for category in crime_categories:
                category_text = category.get_text(strip=True)
                if 'brott' in category_text.lower():
                    # Try to find associated statistics
                    next_p = category.find_next('p')
                    if next_p:
                        stats["crimes_by_category"][category_text] = self._extract_number(next_p.text)
            
            # Calculate crimes per 100k (using approximate Swedish population)
            if stats["total_crimes"] > 0:
                population = 10500000  # Approximate Swedish population 2024
                stats["crimes_per_100k"] = round(stats["total_crimes"] * 100000 / population, 1)
                
            return stats
            
        except Exception as e:
            logger.error(f"Error extracting statistics: {str(e)}")
            return stats
    
    def _extract_number(self, text: str) -> int:
        """Extract a number from text, handling Swedish number formatting."""
        try:
            # Remove spaces and replace Swedish decimal comma
            text = text.replace(" ", "").replace(",", ".")
            # Find any number in the text
            import re
            
            # First try to find numbers followed by "brott" or "fall"
            matches = re.findall(r"(\d+(?:\.\d+)?)\s*(?:brott|fall)", text.lower())
            if matches:
                return int(float(matches[0]))
            
            # Then try to find numbers with "miljoner"
            matches = re.findall(r"(\d+(?:\.\d+)?)\s*miljon(?:er)?", text.lower())
            if matches:
                number = float(matches[0])
                return int(number * 1000000)
            
            # Finally try any number, but ignore years (4 digit numbers starting with 2)
            numbers = re.findall(r"[-+]?\d*\.\d+|\d+", text)
            if numbers:
                for num in numbers:
                    if not (len(num) == 4 and num.startswith("2")):  # Skip years
                        return int(float(num))
        except Exception:
            pass
        return 0
    
    def _extract_percentage(self, text: str) -> float:
        """Extract a percentage change from text."""
        try:
            if not text:
                return 0.0
                
            # Find percentage number in text
            import re
            
            # Look for numbers followed by "procent" or "%"
            matches = re.findall(r'(?:med|på)?\s*(\d+(?:[,.]\d+)?)\s*(?:procents?|%)', text.lower())
            if matches:
                # Handle complex number formats
                number_str = matches[0].replace(",", ".")
                parts = number_str.split(".")
                
                # Try to find the most reasonable number in the sequence
                if len(parts) > 1:
                    # If we have parts like ["2", "5", "6"], combine them appropriately
                    if len(parts) >= 2 and all(p.isdigit() for p in parts[1:]):
                        try:
                            # Try to combine the decimal parts (e.g., "5" and "6" become "56")
                            decimal_part = "".join(parts[1:])
                            value = float(f"{parts[0]}.{decimal_part}")
                            if any(word in text.lower() for word in ["minska", "minskning", "mindre", "lägre", "ned", "ner"]):
                                value = -value
                            return value
                        except ValueError:
                            pass
                    
                    # If that fails, take the first valid number
                    for part in parts:
                        if part.strip().isdigit():
                            value = float(part)
                            if any(word in text.lower() for word in ["minska", "minskning", "mindre", "lägre", "ned", "ner"]):
                                value = -value
                            return value
                else:
                    # Simple case - just one number
                    try:
                        value = float(number_str)
                        if any(word in text.lower() for word in ["minska", "minskning", "mindre", "lägre", "ned", "ner"]):
                            value = -value
                        return value
                    except ValueError:
                        pass
                    
            # Try alternative format: "en minskning med X procent"
            matches = re.findall(r'(?:en |med |på )?(\d+(?:[,.]\d+)?)\s*(?:procents?|%)', text.lower())
            if matches:
                # Handle complex number formats
                number_str = matches[0].replace(",", ".")
                parts = number_str.split(".")
                
                # Try to find the most reasonable number in the sequence
                if len(parts) > 1:
                    # If we have parts like ["2", "5", "6"], combine them appropriately
                    if len(parts) >= 2 and all(p.isdigit() for p in parts[1:]):
                        try:
                            decimal_part = "".join(parts[1:])
                            value = float(f"{parts[0]}.{decimal_part}")
                            if any(word in text.lower() for word in ["minska", "minskning", "mindre", "lägre", "ned", "ner"]):
                                value = -value
                            return value
                        except ValueError:
                            pass
                    
                    # If that fails, take the first valid number
                    for part in parts:
                        if part.strip().isdigit():
                            value = float(part)
                            if any(word in text.lower() for word in ["minska", "minskning", "mindre", "lägre", "ned", "ner"]):
                                value = -value
                            return value
                else:
                    # Simple case - just one number
                    try:
                        value = float(number_str)
                        if any(word in text.lower() for word in ["minska", "minskning", "mindre", "lägre", "ned", "ner"]):
                            value = -value
                        return value
                    except ValueError:
                        pass
                    
        except Exception as e:
            logger.error(f"Error extracting percentage: {str(e)} from text: {text}")
        return 0.0
        
    def get_crime_trends(self, start_year: int, end_year: int = 2024,
                        crime_type: Optional[str] = None) -> Dict[str, List]:
        """
        Get crime trends between specified years.
        
        Args:
            start_year: Starting year for trend analysis
            end_year: End year for trend analysis (default: 2024)
            crime_type: Specific type of crime to analyze (optional)
            
        Returns:
            Dictionary containing trend data
        """
        years = list(range(start_year, end_year + 1))
        values = []
        trend = "stable"
        
        try:
            # Fetch statistics for each year
            for year in years:
                stats = self._fetch_cached_stats(year, crime_type)
                if stats and "total_crimes" in stats:
                    values.append(stats["total_crimes"])
            
            if len(values) >= 2:
                # Calculate trend
                first_value = values[0]
                last_value = values[-1]
                if last_value > first_value * 1.05:  # 5% increase threshold
                    trend = "increasing"
                elif last_value < first_value * 0.95:  # 5% decrease threshold
                    trend = "decreasing"
                    
        except Exception as e:
            logger.error(f"Error analyzing crime trends: {str(e)}")
            values = []
            
        return {
            "years": years,
            "values": values,
            "trend": trend
        }
    
    def _fetch_cached_stats(self, year: int, crime_type: Optional[str] = None) -> Optional[Dict]:
        """Fetch statistics from cache or website."""
        cache_key = f"{year}_{crime_type}"
        if cache_key not in self.cache:
            try:
                response = self.client.get(self.CRIME_STATS_URL)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
                self.cache[cache_key] = self._extract_statistics(soup, year, crime_type)
            except Exception as e:
                logger.error(f"Error fetching stats for {year}: {str(e)}")
                return None
        return self.cache[cache_key]
        
    async def close(self):
        """Close the HTTP client."""
        self.client.close()
        
    async def __aenter__(self):
        """Async context manager entry."""
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close() 