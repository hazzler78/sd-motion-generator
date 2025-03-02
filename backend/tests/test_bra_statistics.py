"""Tests for the BRÅ statistics module."""
import pytest
from httpx import AsyncClient, ReadTimeout
from fastapi import HTTPException
from unittest.mock import Mock, patch
from bs4 import BeautifulSoup
from politik.bra_statistics import BRAStatistics
import asyncio

@pytest.fixture
def mock_html_response():
    """Create a mock HTML response for testing."""
    return """
    <html>
        <body>
            <main>
                <h1>Kriminalstatistik</h1>
                <p>Under 2024 anmäldes 1,48 miljoner brott, vilket är en minskning med 1 procent jämfört med året innan.</p>
                
                <h3>Våldsbrott</h3>
                <p>Under året anmäldes 95 000 våldsbrott.</p>
                
                <h3>Egendomsbrott</h3>
                <p>Totalt anmäldes 450 000 egendomsbrott.</p>
                
                <h3>Narkotikabrott</h3>
                <p>Antalet anmälda narkotikabrott uppgick till 125 000.</p>
            </main>
        </body>
    </html>
    """

@pytest.mark.asyncio
async def test_get_crime_statistics_success(mock_html_response):
    """Test successful retrieval of crime statistics."""
    async with BRAStatistics() as stats:
        with patch('httpx.Client.get') as mock_get:
            mock_get.return_value = Mock(
                status_code=200,
                text=mock_html_response,
                raise_for_status=lambda: None
            )
            
            result = await stats.get_crime_statistics(year=2024)
            
            assert result["total_crimes"] == 1480000
            assert result["crimes_by_category"]["Våldsbrott"] == 95000
            assert result["crimes_by_category"]["Egendomsbrott"] == 450000
            assert result["crimes_by_category"]["Narkotikabrott"] == 125000
            assert result["change_from_previous_year"] == -1.0
            assert result["data_quality"] == "preliminary"

@pytest.mark.asyncio
async def test_get_crime_statistics_with_type(mock_html_response):
    """Test getting statistics for a specific crime type."""
    async with BRAStatistics() as stats:
        with patch('httpx.Client.get') as mock_get:
            mock_get.return_value = Mock(
                status_code=200,
                text=mock_html_response,
                raise_for_status=lambda: None
            )
            
            result = await stats.get_crime_statistics(
                year=2024,
                crime_type="Våldsbrott"
            )
            
            assert result["crimes_by_category"]["Våldsbrott"] == 95000

@pytest.mark.asyncio
async def test_get_crime_statistics_connection_error():
    """Test handling of connection errors."""
    async with BRAStatistics() as stats:
        with patch('httpx.Client.get') as mock_get:
            mock_get.side_effect = Exception("Connection failed")
            
            with pytest.raises(HTTPException) as exc_info:
                await stats.get_crime_statistics(year=2024)
                
            assert exc_info.value.status_code == 500
            assert "Error fetching BRÅ statistics" in str(exc_info.value.detail)

@pytest.mark.asyncio
async def test_get_crime_statistics_timeout():
    """Test handling of timeout errors."""
    async with BRAStatistics() as stats:
        with patch('httpx.Client.get') as mock_get:
            mock_get.side_effect = ReadTimeout("Connection timed out")
            
            with pytest.raises(HTTPException) as exc_info:
                await stats.get_crime_statistics(year=2024)
                
            assert exc_info.value.status_code == 504
            assert "Timeout" in str(exc_info.value.detail)

@pytest.mark.asyncio
async def test_extract_number():
    """Test number extraction from Swedish text."""
    async with BRAStatistics() as stats:
        assert stats._extract_number("95 000") == 95000
        assert stats._extract_number("1,48 miljoner") == 1480000
        assert stats._extract_number("ingen siffra") == 0
        assert stats._extract_number("12,5%") == 12
        assert stats._extract_number("Under 2024 anmäldes") == 0  # Should ignore year
        assert stats._extract_number("5000 brott") == 5000
        assert stats._extract_number("cirka 10 000 fall") == 10000

@pytest.mark.asyncio
async def test_extract_percentage():
    """Test percentage extraction from Swedish text."""
    async with BRAStatistics() as stats:
        assert stats._extract_percentage("en ökning med 2,5 procent") == 2.5
        assert stats._extract_percentage("minskade med 1 procent") == -1.0
        assert stats._extract_percentage("ingen förändring") == 0.0
        assert stats._extract_percentage("en minskning med 1 procent") == -1.0
        assert stats._extract_percentage("minskning på 1 procent") == -1.0

@pytest.mark.asyncio
async def test_get_crime_trends(mock_html_response):
    """Test crime trends analysis."""
    async with BRAStatistics() as stats:
        with patch('httpx.Client.get') as mock_get:
            mock_get.return_value = Mock(
                status_code=200,
                text=mock_html_response,
                raise_for_status=lambda: None
            )
            
            result = stats.get_crime_trends(2020, 2024)
            
            assert len(result["years"]) == 5
            assert result["years"][0] == 2020
            assert result["years"][-1] == 2024
            assert "trend" in result
            assert isinstance(result["values"], list)

@pytest.mark.asyncio
async def test_context_manager(mock_html_response):
    """Test the async context manager functionality."""
    with patch('httpx.Client.get') as mock_get:
        mock_get.return_value = Mock(
            status_code=200,
            text=mock_html_response,
            raise_for_status=lambda: None
        )
        
        async with BRAStatistics() as stats:
            assert isinstance(stats, BRAStatistics)
            result = await stats.get_crime_statistics(year=2024)
            assert isinstance(result, dict)
            assert result["total_crimes"] == 1480000

@pytest.mark.asyncio
async def test_cache_functionality(mock_html_response):
    """Test that caching works correctly."""
    async with BRAStatistics() as stats:
        with patch('httpx.Client.get') as mock_get:
            mock_get.return_value = Mock(
                status_code=200,
                text=mock_html_response,
                raise_for_status=lambda: None
            )
            
            # First call should hit the network
            stats._fetch_cached_stats(2024)
            assert mock_get.call_count == 1
            
            # Second call should use cache
            stats._fetch_cached_stats(2024)
            assert mock_get.call_count == 1  # Still 1, not 2 

@pytest.mark.asyncio
async def test_empty_response_handling():
    """Test handling of empty response from BRÅ website."""
    bra = BRAStatistics()
    try:
        # Create empty soup object
        soup = BeautifulSoup("", 'html.parser')
        stats = bra._extract_statistics(soup, 2024)
        
        assert stats["total_crimes"] == 0
        assert stats["crimes_by_category"] == {}
        assert stats["crimes_per_100k"] == 0
        assert stats["change_from_previous_year"] == 0
        assert stats["data_quality"] == "preliminary"
    finally:
        await bra.close()

@pytest.mark.asyncio
async def test_cache_expiration():
    """Test that cache works and can handle multiple requests."""
    bra = BRAStatistics()
    try:
        # First request should hit the website
        stats1 = await bra.get_crime_statistics(2023)
        cache_key = "2023_None"
        assert cache_key in bra.cache
        
        # Second request should use cache
        stats2 = await bra.get_crime_statistics(2023)
        assert stats1 == stats2
        
        # Different year should create new cache entry
        await bra.get_crime_statistics(2022)
        assert "2022_None" in bra.cache
    finally:
        await bra.close()

@pytest.mark.asyncio
async def test_concurrent_requests():
    """Test handling of concurrent requests."""
    async with BRAStatistics() as bra:
        # Make multiple concurrent requests
        tasks = [
            bra.get_crime_statistics(year)
            for year in [2022, 2023, 2024]
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check that all requests completed
        assert len(results) == 3
        # Verify no exceptions were raised
        assert not any(isinstance(r, Exception) for r in results)

@pytest.mark.asyncio
async def test_alternative_percentage_formats():
    """Test extraction of percentages from various text formats."""
    bra = BRAStatistics()
    try:
        # Test various formats
        assert bra._extract_percentage("en minskning med 5 procent") == -5.0
        assert bra._extract_percentage("ökade med 3,5 procent") == 3.5
        assert bra._extract_percentage("minskade på 2,5 procent") == -2.5
        assert bra._extract_percentage("en ökning med 7%") == 7.0
        assert bra._extract_percentage("invalid text") == 0.0
    finally:
        await bra.close()

@pytest.mark.asyncio
async def test_crime_trends_edge_cases():
    """Test edge cases in crime trends analysis."""
    bra = BRAStatistics()
    try:
        # Test with invalid years
        trends = bra.get_crime_trends(2025, 2024)
        assert trends["values"] == []
        assert trends["trend"] == "stable"
        
        # Test with single year
        trends = bra.get_crime_trends(2024, 2024)
        assert len(trends["years"]) == 1
        assert trends["trend"] == "stable"
        
        # Test trend thresholds
        # Mock _fetch_cached_stats to return a regular dict instead of coroutine
        def mock_fetch(year, crime_type=None):
            if year == 2022:
                return {"total_crimes": 1000}
            return {"total_crimes": 1060}  # 6% increase
            
        bra._fetch_cached_stats = mock_fetch
        trends = bra.get_crime_trends(2022, 2023)
        assert trends["trend"] == "increasing"
    finally:
        await bra.close()

@pytest.mark.asyncio
async def test_parse_crime_categories():
    """Test parsing of different crime category formats."""
    bra = BRAStatistics()
    try:
        html = """
        <main>
            <div class="main-content">
                <h3>Våldsbrott</h3>
                <p>Totalt 5000 brott</p>
                <h3>Egendomsbrott</h3>
                <p>Cirka 10 000 anmälda fall</p>
            </div>
        </main>
        """
        soup = BeautifulSoup(html, 'html.parser')
        stats = bra._extract_statistics(soup, 2024)
        
        assert "Våldsbrott" in stats["crimes_by_category"]
        assert stats["crimes_by_category"]["Våldsbrott"] == 5000
        assert "Egendomsbrott" in stats["crimes_by_category"]
        assert stats["crimes_by_category"]["Egendomsbrott"] == 10000
    finally:
        await bra.close()

@pytest.mark.asyncio
async def test_error_handling_in_extract_statistics():
    """Test error handling in _extract_statistics method."""
    bra = BRAStatistics()
    try:
        # Test with malformed HTML that should trigger error handling
        html = """
        <main>
            <div class="main-content">
                <h3>Våldsbrott</h3>
                <p>Invalid number format</p>
                <script>Some script that might cause parsing errors</script>
                <h3>Narkotikabrott</h3>
                <p>Not a number at all</p>
            </div>
        </main>
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        # Test error handling in _extract_statistics
        stats = bra._extract_statistics(soup, 2024)
        assert stats["total_crimes"] == 0  # Should default to 0 on error
        assert stats["crimes_by_category"] == {"Våldsbrott": 0, "Narkotikabrott": 0}  # Categories should exist with 0 values
        
        # Test with completely invalid HTML
        invalid_soup = BeautifulSoup("<invalid>", 'html.parser')
        stats = bra._extract_statistics(invalid_soup, 2024)
        assert stats["total_crimes"] == 0
        assert stats["crimes_by_category"] == {}  # No categories should be found
        
        # Test with None values
        stats = bra._extract_statistics(None, 2024)
        assert stats["total_crimes"] == 0
        assert stats["crimes_by_category"] == {}
        
    finally:
        await bra.close()

@pytest.mark.asyncio
async def test_extract_statistics_exception_handling():
    """Test that _extract_statistics handles exceptions gracefully."""
    bra = BRAStatistics()
    try:
        # Create a mock BeautifulSoup object that raises an exception when accessed
        class ExceptionSoup:
            def find(self, *args, **kwargs):
                raise Exception("Simulated parsing error")
            
            def find_all(self, *args, **kwargs):
                raise Exception("Simulated parsing error")
        
        # Test with soup that raises exceptions
        stats = bra._extract_statistics(ExceptionSoup(), 2024)
        assert stats["total_crimes"] == 0
        assert stats["crimes_by_category"] == {}
        assert stats["crimes_per_100k"] == 0
        assert stats["change_from_previous_year"] == 0
    finally:
        await bra.close()

@pytest.mark.asyncio
async def test_extract_statistics_alternative_html():
    """Test extraction from alternative HTML structures."""
    bra = BRAStatistics()
    try:
        # Test with alternative HTML structure using strong tags instead of h3
        html = """
        <div class="main-content">
            <p>Under 2024 anmäldes knappt 150 000 brott, vilket är en ökning med 5 procent.</p>
            <strong>Våldsbrott</strong>
            <p>5000 anmälda fall</p>
            <strong>Egendomsbrott</strong>
            <p>10000 brott</p>
        </div>
        """
        soup = BeautifulSoup(html, 'html.parser')
        stats = bra._extract_statistics(soup, 2024)
        
        assert stats["total_crimes"] == 150000
        assert stats["crimes_by_category"]["Våldsbrott"] == 5000
        assert stats["crimes_by_category"]["Egendomsbrott"] == 10000
        assert stats["change_from_previous_year"] == 5.0
        
        # Test with div.main-content but no main tag
        html = """
        <div class="main-content">
            <p>Under 2024 anmäldes knappt 150 000 brott</p>
            <h3>Våldsbrott</h3>
            <p>5000 anmälda fall</p>
        </div>
        """
        soup = BeautifulSoup(html, 'html.parser')
        stats = bra._extract_statistics(soup, 2024)
        
        assert stats["total_crimes"] == 150000
        assert stats["crimes_by_category"]["Våldsbrott"] == 5000
        
    finally:
        await bra.close()

@pytest.mark.asyncio
async def test_get_crime_trends_error_handling():
    """Test error handling in get_crime_trends."""
    bra = BRAStatistics()
    try:
        # Mock _fetch_cached_stats to raise an exception
        def mock_fetch_error(*args, **kwargs):
            return None  # Simulate failed fetch
            
        original_fetch = bra._fetch_cached_stats
        bra._fetch_cached_stats = mock_fetch_error
        
        # Test with failing fetch
        trends = bra.get_crime_trends(2020, 2024)
        assert trends["values"] == []
        assert trends["trend"] == "stable"
        assert len(trends["years"]) == 5
        
        # Test with mixed success/failure
        def mock_fetch_mixed(year, crime_type=None):
            if year % 2 == 0:
                return {"total_crimes": 1000}
            return None  # Simulate failed fetch for odd years
            
        bra._fetch_cached_stats = mock_fetch_mixed
        trends = bra.get_crime_trends(2020, 2024)
        assert len([v for v in trends["values"] if v == 1000]) == 3  # Should have data for 2020, 2022, 2024
        assert trends["trend"] == "stable"
        
        # Restore original method
        bra._fetch_cached_stats = original_fetch
        
    finally:
        await bra.close()

@pytest.mark.asyncio
async def test_fetch_cached_stats_error_handling():
    """Test error handling in _fetch_cached_stats."""
    bra = BRAStatistics()
    try:
        # Test with failing HTTP request
        with patch('httpx.Client.get') as mock_get:
            mock_get.side_effect = Exception("Network error")
            result = bra._fetch_cached_stats(2024)
            assert result is None
            
        # Test with invalid response
        with patch('httpx.Client.get') as mock_get:
            mock_get.return_value = Mock(
                status_code=500,
                raise_for_status=lambda: exec('raise Exception("Bad status")')
            )
            result = bra._fetch_cached_stats(2024)
            assert result is None
            
        # Verify that cache is used even after error
        assert "2024_None" not in bra.cache
        
    finally:
        await bra.close()

@pytest.mark.asyncio
async def test_get_crime_statistics_error_handling():
    """Test error handling in get_crime_statistics and _extract_statistics methods."""
    bra = BRAStatistics()
    try:
        # Test with invalid HTML structure
        with patch('httpx.Client.get') as mock_get:
            mock_get.return_value = Mock(
                status_code=200,
                text="<html><body>Invalid structure without main or statistics</body></html>",
                raise_for_status=lambda: None
            )
            
            # This should not raise an exception but return default values
            stats = await bra.get_crime_statistics(2024)
            assert stats["total_crimes"] == 0
            assert stats["crimes_by_category"] == {}
            assert stats["data_quality"] == "preliminary"
            
        # Test with malformed numbers in HTML
        with patch('httpx.Client.get') as mock_get:
            mock_get.return_value = Mock(
                status_code=200,
                text="""
                <html><body><main>
                    <p>Under 2024 anmäldes invalid number brott</p>
                    <h3>Våldsbrott</h3>
                    <p>not a number</p>
                </main></body></html>
                """,
                raise_for_status=lambda: None
            )
            
            stats = await bra.get_crime_statistics(2024)
            assert stats["total_crimes"] == 0
            # Verify that either the category doesn't exist or has value 0
            assert "Våldsbrott" not in stats["crimes_by_category"] or stats["crimes_by_category"]["Våldsbrott"] == 0
            
        # Test with missing content sections
        with patch('httpx.Client.get') as mock_get:
            mock_get.return_value = Mock(
                status_code=200,
                text="<html><body><main></main></body></html>",
                raise_for_status=lambda: None
            )
            
            stats = await bra.get_crime_statistics(2024)
            assert stats["total_crimes"] == 0
            assert stats["change_from_previous_year"] == 0
            
    finally:
        await bra.close()

@pytest.mark.asyncio
async def test_extract_number_exception_handling():
    """Test that _extract_number handles exceptions gracefully."""
    bra = BRAStatistics()
    try:
        # Test with text that would cause float conversion to fail
        assert bra._extract_number("abc") == 0  # No numbers at all
        assert bra._extract_number("") == 0  # Empty string
        assert bra._extract_number(None) == 0  # None value
        
        # Test with invalid number formats that should be caught
        assert bra._extract_number("abc,23 brott") == 23  # Should extract 23
        assert bra._extract_number("xyz miljoner") == 0  # No numbers with miljoner
        assert bra._extract_number("2024 xyz") == 0  # Should ignore year
        
        # Test with valid but complex formats
        assert bra._extract_number("1.2.3.4") == 1  # Should extract first valid number
        assert bra._extract_number("1,2,3,4") == 1  # Should extract first valid number
        assert bra._extract_number("1e6") == 1  # Should extract 1 from scientific notation
        
        # Test with brott/fall suffix
        assert bra._extract_number("3,4 brott") == 3  # Should extract number before brott
        assert bra._extract_number("5,6 fall") == 5  # Should extract number before fall
    finally:
        await bra.close()

@pytest.mark.asyncio
async def test_extract_statistics_percentage_formats():
    """Test extraction of statistics with various percentage formats."""
    bra = BRAStatistics()
    try:
        # Test with different percentage formats in HTML
        html = """
        <div class="main-content">
            <p>Under 2024 anmäldes totalt 100 000 brott, en minskning med 2,5 procent</p>
            <h3>Våldsbrott</h3>
            <p>Minskade på 3,5 procent till 5000 fall</p>
            <h3>Egendomsbrott</h3>
            <p>Visade en ökning med 4 % till 10000 brott</p>
            <h3>Narkotikabrott</h3>
            <p>Ökade med 1,5 procents förändring, totalt 2000 brott</p>
        </div>
        """
        soup = BeautifulSoup(html, 'html.parser')
        stats = bra._extract_statistics(soup, 2024)
        
        assert stats["total_crimes"] == 100000
        assert stats["change_from_previous_year"] == -2.5  # First percentage found
        assert "Våldsbrott" in stats["crimes_by_category"]
        assert stats["crimes_by_category"]["Våldsbrott"] == 5000
        assert "Egendomsbrott" in stats["crimes_by_category"]
        assert stats["crimes_by_category"]["Egendomsbrott"] == 10000
        assert "Narkotikabrott" in stats["crimes_by_category"]
        assert stats["crimes_by_category"]["Narkotikabrott"] == 2000
        
    finally:
        await bra.close()

@pytest.mark.asyncio
async def test_get_crime_trends_calculation_error():
    """Test error handling during trend calculation in get_crime_trends."""
    bra = BRAStatistics()
    try:
        # Mock _fetch_cached_stats to return invalid data that will cause calculation errors
        def mock_fetch_invalid(year, crime_type=None):
            if year == 2022:
                return {"total_crimes": "invalid"}  # This will cause a calculation error
            return {"total_crimes": 1000}
            
        original_fetch = bra._fetch_cached_stats
        bra._fetch_cached_stats = mock_fetch_invalid
        
        # Test with data that will cause calculation errors
        trends = bra.get_crime_trends(2022, 2023)
        assert trends["values"] == []  # Should be empty due to error
        assert trends["trend"] == "stable"  # Should default to stable
        assert len(trends["years"]) == 2  # Years should still be present
        
        # Test with data that causes comparison errors
        def mock_fetch_none_value(year, crime_type=None):
            if year == 2022:
                return {"total_crimes": None}  # This will cause comparison errors
            return {"total_crimes": 1000}
            
        bra._fetch_cached_stats = mock_fetch_none_value
        trends = bra.get_crime_trends(2022, 2023)
        assert trends["values"] == []
        assert trends["trend"] == "stable"
        
        # Restore original method
        bra._fetch_cached_stats = original_fetch
        
    finally:
        await bra.close()

@pytest.mark.asyncio
async def test_extract_percentage_error_handling():
    """Test error handling in _extract_percentage method."""
    bra = BRAStatistics()
    try:
        # Test with invalid number format that will cause float conversion to fail
        assert bra._extract_percentage("en ökning med abc procent") == 0.0
        assert bra._extract_percentage("minskade med ..,, procent") == 0.0
        assert bra._extract_percentage("ökade med ,. %") == 0.0
        
        # Test with malformed percentage strings
        assert bra._extract_percentage("en minskning med procent") == 0.0  # No number
        assert bra._extract_percentage("") == 0.0  # Empty string
        assert bra._extract_percentage(None) == 0.0  # None value
        
        # Test with complex formats that should still extract valid numbers
        assert bra._extract_percentage("minskade med 2,5,6 procent") == -5.6  # Extracts 5.6 and makes it negative
        assert bra._extract_percentage("ökade med 2..5 procent") == 5.0  # Takes first valid number (5)
        
        # Test alternative percentage formats with various decrease indicators
        assert bra._extract_percentage("en minskning med 3,5 procent") == -3.5  # Alternative format with "en minskning med"
        assert bra._extract_percentage("på 2,5 procent") == 2.5  # Alternative format with "på"
        assert bra._extract_percentage("ned med 4,2%") == -4.2  # Alternative format with "ned" and %
        assert bra._extract_percentage("ner på 1,8 procents") == -1.8  # Alternative format with "ner" and "procents"
        assert bra._extract_percentage("mindre än 2,5 procent") == -2.5  # Alternative format with "mindre"
        assert bra._extract_percentage("lägre med 3,0 procent") == -3.0  # Alternative format with "lägre"
        assert bra._extract_percentage("en minskning på 5,5 procent") == -5.5  # Alternative format with both "minskning" and "på"
        
        # Test alternative formats with invalid numbers that should trigger exception handling
        assert bra._extract_percentage("en minskning med abc,def procent") == 0.0  # Invalid number in alternative format
        assert bra._extract_percentage("lägre med ,,,, procent") == 0.0  # Invalid number with decrease indicator
        assert bra._extract_percentage("mindre än .. procent") == 0.0  # Invalid number with decrease indicator
        assert bra._extract_percentage("ned med procent") == 0.0  # Missing number with decrease indicator
        
    finally:
        await bra.close()

@pytest.mark.asyncio
async def test_get_crime_trends_decreasing():
    """Test detection of decreasing trend in crime statistics."""
    bra = BRAStatistics()
    try:
        # Mock _fetch_cached_stats to return decreasing values
        def mock_fetch_decreasing(year, crime_type=None):
            # Return values that show a clear decrease (more than 5%)
            if year == 2022:
                return {"total_crimes": 1000}
            return {"total_crimes": 900}  # 10% decrease
            
        original_fetch = bra._fetch_cached_stats
        bra._fetch_cached_stats = mock_fetch_decreasing
        
        # Test with decreasing trend
        trends = bra.get_crime_trends(2022, 2023)
        assert trends["trend"] == "decreasing"
        assert trends["values"] == [1000, 900]
        
        # Restore original method
        bra._fetch_cached_stats = original_fetch
        
    finally:
        await bra.close() 