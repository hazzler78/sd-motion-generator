import pytest
from fastapi.testclient import TestClient
from politik.main import (
    app, MotionRequest, XAI_URL, 
    get_current_year, agent_3_improve, 
    health_check, generate_motion,
    fetch_statistics, get_crime_trends
)
from politik.statistics import StatisticsType
from politik.kolada_v2 import KoladaError, NoDataError, ValidationError, KoladaClient
import requests
from unittest import mock
from fastapi import HTTPException
import os
import importlib
from unittest.mock import patch
from bs4 import BeautifulSoup
from datetime import datetime
import httpx
from unittest.mock import AsyncMock

client = TestClient(app)

def test_motion_request_validation_valid_municipality():
    """Testa att giltiga kommunnamn accepteras"""
    request = MotionRequest(
        topic="trygghet",
        statistics=[StatisticsType.BEFOLKNING],
        year=2023,
        municipality="karlstad"
    )
    assert request.municipality == "karlstad"

    # Test med olika skiftlägen
    request = MotionRequest(
        topic="trygghet",
        statistics=[StatisticsType.BEFOLKNING],
        year=2023,
        municipality="ARVIKA"
    )
    assert request.municipality == "arvika"

def test_motion_request_validation_invalid_municipality():
    """Testa att ogiltiga kommunnamn avvisas"""
    with pytest.raises(ValueError) as exc_info:
        MotionRequest(
            topic="trygghet",
            statistics=[StatisticsType.BEFOLKNING],
            year=2023,
            municipality="stockholm"
        )
    assert "Okänd kommun" in str(exc_info.value)

def test_motion_request_default_municipality():
    """Testa att Karlstad är standardkommun"""
    request = MotionRequest(
        topic="trygghet",
        statistics=[StatisticsType.BEFOLKNING],
        year=2023
    )
    assert request.municipality == "karlstad"

def test_generate_motion_with_municipality():
    """Testa att generera motion för specifik kommun"""
    response = client.post(
        "/api/generate-motion",
        json={
            "topic": "trygghet",
            "statistics": ["befolkning", "trygghet"],
            "year": 2023,
            "municipality": "arvika"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["metadata"]["municipality"] == "arvika"

def test_generate_motion_invalid_municipality():
    """Testa felhantering för ogiltig kommun"""
    response = client.post(
        "/api/generate-motion",
        json={
            "topic": "trygghet",
            "statistics": ["befolkning"],
            "year": 2023,
            "municipality": "stockholm"
        }
    )
    assert response.status_code == 422  # Validation error
    assert "Okänd kommun" in response.json()["detail"][0]["msg"]

def test_generate_motion_with_special_chars():
    """Testa hantering av svenska tecken i kommunnamn"""
    response = client.post(
        "/api/generate-motion",
        json={
            "topic": "trygghet",
            "statistics": ["befolkning"],
            "year": 2023,
            "municipality": "säffle"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["metadata"]["municipality"] == "säffle"

def test_generate_motion_municipality_case_insensitive():
    """Testa att kommunnamn är case-insensitive"""
    response = client.post(
        "/api/generate-motion",
        json={
            "topic": "trygghet",
            "statistics": ["befolkning"],
            "year": 2023,
            "municipality": "KARLSTAD"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["metadata"]["municipality"] == "karlstad"

def test_health_check():
    """Testa health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "api" in data
    assert "kolada" in data
    assert "ai_service" in data
    assert data["api"] == "healthy"

@pytest.mark.asyncio
async def test_health_check_kolada_error(mocker):
    """Testa health check när Kolada är nere"""
    mocker.patch('politik.main.kolada_client.get_municipality_data', side_effect=Exception("Kolada error"))
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["kolada"] == "unknown"
    assert "error" in data

def test_root_endpoint():
    """Testa root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "docs" in data
    assert "endpoints" in data
    assert "/api/generate-motion" in data["endpoints"]["generate_motion"]

def test_generate_motion_no_statistics():
    """Testa att generera motion utan statistik"""
    response = client.post(
        "/api/generate-motion",
        json={
            "topic": "trygghet",
            "statistics": [],
            "year": 2023,
            "municipality": "karlstad"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "motion" in data
    assert data["metadata"]["statistics"] == []

def test_generate_motion_invalid_statistics():
    """Testa felhantering för ogiltig statistiktyp"""
    response = client.post(
        "/api/generate-motion",
        json={
            "topic": "trygghet",
            "statistics": ["invalid_stat"],
            "year": 2023,
            "municipality": "karlstad"
        }
    )
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_generate_motion_kolada_error(mocker):
    """Testa felhantering när Kolada-API:et returnerar fel"""
    mocker.patch('politik.main.kolada_client.get_municipality_data', side_effect=Exception("Kolada error"))
    response = client.post(
        "/api/generate-motion",
        json={
            "topic": "trygghet",
            "statistics": ["befolkning"],
            "year": 2023,
            "municipality": "karlstad"
        }
    )
    assert response.status_code == 200
    data = response.json()
    # Verifiera att statistiken finns i metadata men är tom
    assert len(data["metadata"]["statistics"]) == 0

@pytest.mark.asyncio
async def test_generate_motion_grok_timeout(mocker):
    """Testa felhantering när Grok-API:et timeout:ar"""
    def mock_post(*args, **kwargs):
        raise requests.Timeout("Timeout")
    
    mocker.patch('requests.post', mock_post)
    response = client.post(
        "/api/generate-motion",
        json={
            "topic": "trygghet",
            "statistics": [],
            "year": 2023,
            "municipality": "karlstad"
        }
    )
    assert response.status_code == 500
    assert "Ett fel uppstod vid generering av motionen" in response.json()["detail"]

@patch('politik.main.call_grok')
def test_agent_3_improve(mock_call_grok):
    """Testa agent_3_improve funktionen"""
    from politik.main import agent_3_improve
    
    # Mock Grok API response
    mock_call_grok.return_value = "Improved motion text"
    
    statistics = [
        {
            "text": "Karlstad har 93 000 invånare (2023)",
            "trend": "Befolkningsutveckling: 92 000 (2022) → 93 000 (2023)",
            "data": {"value": 93000, "year": 2023}
        }
    ]
    
    improved = agent_3_improve("En motion om trygghet", statistics)
    assert improved == "Improved motion text"
    mock_call_grok.assert_called_once()

def test_fetch_statistics_no_data():
    """Testa fetch_statistics när data saknas"""
    from politik.main import fetch_statistics, StatisticsType
    result = fetch_statistics(StatisticsType.BEFOLKNING, 1900, "karlstad")  # Använder ett år långt tillbaka
    assert result["data"] is None
    assert "inte tillgänglig" in result["text"]

@pytest.mark.asyncio
async def test_fetch_statistics_invalid_municipality():
    """Testa fetch_statistics med ogiltig kommun"""
    result = await fetch_statistics(StatisticsType.BEFOLKNING, 2023, "invalid")
    assert result["data"] is None
    assert "Ett fel uppstod vid hämtning av statistik för befolkning i invalid" in result["text"]

@pytest.mark.asyncio
async def test_call_grok_invalid_response(mocker):
    """Testa felhantering när Grok API returnerar ogiltig respons"""
    def mock_post(*args, **kwargs):
        class MockResponse:
            def __init__(self):
                self.status_code = 200
            def json(self):
                return {"invalid": "response"}
        return MockResponse()
    
    mocker.patch('requests.post', mock_post)
    with pytest.raises(HTTPException) as exc_info:
        from politik.main import call_grok
        call_grok("test", "test role")
    assert "Grok API Error" in str(exc_info.value.detail)

@pytest.mark.asyncio
async def test_call_grok_api_error(mocker):
    """Testa felhantering när Grok API returnerar felstatus"""
    def mock_post(*args, **kwargs):
        class MockResponse:
            def __init__(self):
                self.status_code = 400
                self.text = "Bad Request"
        return MockResponse()
    
    mocker.patch('requests.post', mock_post)
    with pytest.raises(HTTPException) as exc_info:
        from politik.main import call_grok
        call_grok("test", "test role")
    assert "Grok API Error" in str(exc_info.value.detail)

def test_fetch_statistics_validation_error():
    """Testa felhantering när Kolada returnerar ogiltig data"""
    from politik.main import fetch_statistics, StatisticsType
    from politik.kolada_v2 import ValidationError
    
    def mock_get_data(*args, **kwargs):
        raise ValidationError("Ogiltig data")
    
    with mock.patch('politik.kolada_v2.KoladaClient.get_municipality_data', mock_get_data):
        result = fetch_statistics(StatisticsType.BEFOLKNING, 2023, "karlstad")
        assert result["data"] is None
        assert "kunde inte valideras" in result["text"]

def test_fetch_statistics_with_trend():
    """Testa hämtning av statistik med trend"""
    from politik.main import fetch_statistics, StatisticsType
    
    def mock_get_data(*args, **kwargs):
        if kwargs.get('year') == 2023:
            return {"value": 93000, "year": 2023}
        return {"value": 92000, "year": 2022}
    
    with mock.patch('politik.kolada_v2.KoladaClient.get_municipality_data', mock_get_data):
        result = fetch_statistics(StatisticsType.BEFOLKNING, 2023, "karlstad")
        assert result["data"] is not None
        assert "trend" in result
        assert "92 000" in result["trend"]
        assert "93 000" in result["trend"]

@pytest.mark.asyncio
async def test_health_check_all_services_down(mocker):
    """Testa health check när alla tjänster är nere"""
    mocker.patch('politik.main.kolada_client.get_municipality_data', side_effect=Exception("Kolada error"))
    mocker.patch('politik.main.call_grok', side_effect=Exception("Grok error"))
    
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["kolada"] == "unknown"
    assert data["ai_service"] == "unknown"
    assert "error" in data

@pytest.mark.asyncio
async def test_health_check_services_ok(mocker):
    """Testa health check när alla tjänster fungerar"""
    def mock_get_data(*args, **kwargs):
        return {"value": 93000, "year": 2023}
    
    mocker.patch('politik.main.kolada_client.get_municipality_data', mock_get_data)
    mocker.patch('politik.main.call_grok', return_value="OK")
    
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["kolada"] == "ok"
    assert data["ai_service"] == "ok"
    assert "error" not in data

def test_missing_api_key(mocker):
    """Testa felhantering för saknad API-nyckel"""
    # Spara original miljövariabel
    original_key = os.getenv("XAI_API_KEY")
    
    try:
        # Ta bort API-nyckeln
        os.environ["XAI_API_KEY"] = ""
        
        # Testa att modulen inte kan laddas utan API-nyckel
        with pytest.raises(ValueError) as exc_info:
            import politik.main
            importlib.reload(politik.main)
        
        assert "XAI_API_KEY saknas" in str(exc_info.value)
    finally:
        # Återställ original API-nyckel
        if original_key:
            os.environ["XAI_API_KEY"] = original_key

@pytest.mark.asyncio
async def test_health_check_detailed():
    """Test health check endpoint with detailed error scenarios."""
    # Test when Kolada fails but AI service works
    with patch('politik.main.kolada_client.get_municipality_data') as mock_kolada, \
         patch('politik.main.call_grok') as mock_grok:
        mock_kolada.side_effect = Exception("Kolada error")
        mock_grok.return_value = "OK"
        
        response = await health_check()
        assert response["kolada"] == "unknown"
        assert response["ai_service"] == "unknown"
        assert "Kolada error" in response.get("error", "")

    # Test when both services fail
    with patch('politik.main.kolada_client.get_municipality_data') as mock_kolada, \
         patch('politik.main.call_grok') as mock_grok:
        mock_kolada.side_effect = Exception("Kolada error")
        mock_grok.side_effect = Exception("AI service error")
        
        response = await health_check()
        assert response["kolada"] == "unknown"
        assert response["ai_service"] == "unknown"
        assert "error" in response

@pytest.mark.asyncio
async def test_generate_motion_with_retries(mocker):
    """Testa att API-anrop görs om vid fel"""
    call_count = 0
    success_after = 3  # Succeed after this many attempts for each call
    attempts_per_call = {}  # Track attempts for each unique call

    def mock_post_with_retry(*args, **kwargs):
        nonlocal call_count
        nonlocal attempts_per_call

        # Only count calls to the x.ai API
        if XAI_URL in args[0]:
            call_count += 1
            
            # Use the prompt as a unique identifier for each call
            call_id = kwargs['json']['messages'][1]['content']
            attempts_per_call[call_id] = attempts_per_call.get(call_id, 0) + 1
            
            if attempts_per_call[call_id] < success_after:
                raise requests.exceptions.RequestException("API Error")
            
            # Succeed on third attempt
            class MockResponse:
                status_code = 200
                def json(self):
                    return {
                        "choices": [
                            {"message": {"content": "Success after retry"}}
                        ]
                    }
            return MockResponse()

        # For non-x.ai calls (like Kolada), return success
        class MockResponse:
            status_code = 200
            def json(self):
                return {"values": [{"value": 42.5}]}
        return MockResponse()

    # Mock requests.post
    mocker.patch('requests.post', side_effect=mock_post_with_retry)

    # Mock Kolada client to avoid those calls
    mocker.patch('politik.kolada_v2.KoladaClient.get_municipality_data',
                return_value={"value": 42, "year": 2023})

    response = client.post(
        "/api/generate-motion",
        json={
            "topic": "test",
            "statistics": ["befolkning"],
            "year": 2023,
            "municipality": "karlstad"
        }
    )

    assert response.status_code == 200
    # We make 3 API calls (agent_1, agent_2, agent_3) and each one retries twice
    # So total calls should be 3 * success_after
    assert call_count == 3 * success_after  # Verify total number of retries
    assert len(attempts_per_call) == 3  # Verify we made 3 unique API calls 

@pytest.mark.asyncio
async def test_get_current_year():
    """Test that get_current_year returns the current year."""
    current_year = datetime.now().year
    assert get_current_year() == current_year

@pytest.mark.asyncio
async def test_motion_request_municipality_validation():
    """Test municipality validation in MotionRequest."""
    # Test valid municipality
    request = MotionRequest(topic="test", municipality="karlstad")
    assert request.municipality == "karlstad"
    
    # Test municipality case insensitivity
    request = MotionRequest(topic="test", municipality="KARLSTAD")
    assert request.municipality == "karlstad"
    
    # Test invalid municipality
    with pytest.raises(ValueError, match="Okänd kommun"):
        MotionRequest(topic="test", municipality="invalid")
    
    # Test empty municipality defaults to karlstad
    request = MotionRequest(topic="test")
    assert request.municipality == "karlstad"

@pytest.mark.asyncio
async def test_agent_3_improve_with_crime_stats():
    """Test agent_3_improve with crime statistics."""
    draft = "Test motion"
    statistics = [{
        "text": "Test statistic",
        "data": {
            "crimes_per_100k": 1000,
            "total_crimes": 5000,
            "change_from_previous_year": -2.5,
            "crimes_by_category": {
                "Våldsbrott": 100,
                "Egendomsbrott": 200
            }
        }
    }]
    
    with patch('politik.main.call_grok') as mock_grok:
        mock_grok.return_value = "Improved motion"
        result = agent_3_improve(draft, statistics)
        
        # Verify that the call to Grok includes crime statistics analysis
        call_args = mock_grok.call_args[0][0]
        assert "Fördjupad brottsanalys" in call_args
        assert "Totalt antal anmälda brott: 5 000" in call_args
        assert "Brott per 100 000 invånare: 1000.0" in call_args
        assert "Förändring från föregående år: -2.5%" in call_args
        assert "Våldsbrott: 100" in call_args
        assert "Egendomsbrott: 200" in call_args

@pytest.mark.asyncio
async def test_health_check_detailed():
    """Test health check endpoint with detailed error scenarios."""
    # Test when Kolada fails but AI service works
    with patch('politik.main.kolada_client.get_municipality_data') as mock_kolada, \
         patch('politik.main.call_grok') as mock_grok:
        mock_kolada.side_effect = Exception("Kolada error")
        mock_grok.return_value = "OK"
        
        response = await health_check()
        assert response["kolada"] == "unknown"
        assert response["ai_service"] == "unknown"
        assert "Kolada error" in response.get("error", "")

    # Test when both services fail
    with patch('politik.main.kolada_client.get_municipality_data') as mock_kolada, \
         patch('politik.main.call_grok') as mock_grok:
        mock_kolada.side_effect = Exception("Kolada error")
        mock_grok.side_effect = Exception("AI service error")
        
        response = await health_check()
        assert response["kolada"] == "unknown"
        assert response["ai_service"] == "unknown"
        assert "error" in response

@pytest.mark.asyncio
async def test_generate_motion_with_crime_stats():
    """Test generate_motion endpoint with crime statistics."""
    request = MotionRequest(
        topic="trygghet",
        statistics=[StatisticsType.BRA_STATISTIK],
        year=2024,
        municipality="karlstad"
    )
    
    with patch('politik.main.agent_1_suggestion') as mock_agent1, \
         patch('politik.main.agent_2_draft') as mock_agent2, \
         patch('politik.main.agent_3_improve') as mock_agent3, \
         patch('politik.main.fetch_statistics') as mock_fetch:
        
        mock_agent1.return_value = "Initial suggestion"
        mock_agent2.return_value = "Draft motion"
        mock_agent3.return_value = "Final motion"
        mock_fetch.return_value = {
            "text": "Crime stats",
            "data": {
                "crimes_per_100k": 1000,
                "total_crimes": 5000
            }
        }
        
        response = await generate_motion(request)
        
        assert response["motion"] == "Final motion"
        assert response["metadata"]["statistics"][0]["type"] == "bra_statistik"
        assert response["metadata"]["statistics"][0]["data"]["total_crimes"] == 5000 

@pytest.mark.asyncio
async def test_fetch_statistics_bra():
    """Test fetching BRÅ statistics with trend data."""
    current_stats = {
        "total_crimes": 5000,
        "crimes_per_100k": 1000,
        "change_from_previous_year": 5.2
    }
    prev_stats = {
        "total_crimes": 4750,
        "crimes_per_100k": 950
    }
    trend_stats = {
        "trend": "stable",
        "values": [4500, 4750, 5000]
    }
    
    mock_get_crime_statistics = AsyncMock(side_effect=lambda year, crime_type=None: current_stats if year == 2024 else prev_stats)
    mock_get_crime_trends = AsyncMock(return_value=trend_stats)
    
    with patch('politik.main.BRAStatistics') as MockBRA:
        mock_bra = MockBRA.return_value
        mock_bra.__aenter__.return_value = mock_bra
        mock_bra.__aexit__.return_value = None
        mock_bra.get_crime_statistics = mock_get_crime_statistics
        mock_bra.get_crime_trends = mock_get_crime_trends
        
        result = await fetch_statistics(StatisticsType.BRA_STATISTIK, 2024, "karlstad")
        
        assert result["data"]["skadegörelse"] == current_stats
        assert result["trends"]["skadegörelse"]["trend"] == "stable"
        assert "1000.0" in result["text"]
        assert "skadegörelse" in result["text"]
        assert "5.2% förändring" in result["text"]

@pytest.mark.asyncio
async def test_fetch_statistics_bra_no_trend():
    current_stats = {
        'crimes_per_100k': 1000,
        'total_crimes': 5000,
        'change_from_previous_year': None
    }
    
    async def mock_get_crime_statistics(year, category):
        if year == 2024:
            return current_stats
        return None
    
    async def mock_get_crime_trends(start_year, end_year, category):
        return None
    
    with patch('politik.main.get_municipality_id', return_value="1780") as mock_get_id, \
         patch('politik.main.BRAStatistics') as mock_bra:
        mock_bra_instance = AsyncMock()
        mock_bra_instance.get_crime_statistics = AsyncMock(side_effect=mock_get_crime_statistics)
        mock_bra_instance.get_crime_trends = AsyncMock(side_effect=mock_get_crime_trends)
        mock_bra.return_value.__aenter__.return_value = mock_bra_instance
        
        result = await fetch_statistics(StatisticsType.BRA_STATISTIK, 2024, "Stockholm")
        
        assert result["data"] is not None
        assert result["data"]["skadegörelse"] == current_stats
        assert "1000.0" in result["text"]
        assert "skadegörelse" in result["text"]
        assert "förändring" not in result["text"]

@pytest.mark.asyncio
async def test_fetch_statistics_kolada_error_handling():
    """Test error handling when fetching Kolada statistics."""
    with patch('politik.main.kolada_client.get_municipality_data') as mock_get_data:
        # Test when current year data is available but previous year fails
        mock_get_data.side_effect = [
            {"value": 42, "year": 2024},  # Current year succeeds
            KoladaError("Failed to fetch previous year")  # Previous year fails
        ]
        
        result = await fetch_statistics(StatisticsType.BEFOLKNING, 2024, "karlstad")
        
        assert result["data"] is not None
        assert "trend" not in result

        # Test when both current and previous year fail
        mock_get_data.side_effect = KoladaError("Failed to fetch data")
        
        result = await fetch_statistics(StatisticsType.BEFOLKNING, 2024, "karlstad")
        assert result["data"] is None

@pytest.mark.asyncio
async def test_get_crime_trends():
    """Test the get_crime_trends endpoint."""
    with patch('politik.main.BRAStatistics') as MockBRA:
        trend_data = {
            "2023": {"total_crimes": 5000},
            "2024": {"total_crimes": 5200}
        }
        
        mock_bra = MockBRA.return_value
        mock_bra.__aenter__.return_value = mock_bra
        mock_bra.__aexit__.return_value = None
        mock_bra.get_crime_statistics = AsyncMock(side_effect=lambda year, crime_type=None: trend_data[str(year)])
        mock_bra.close = AsyncMock()
        
        response = await get_crime_trends(2023, 2024)
        assert response == {
            "years": [2023, 2024],
            "values": [5000, 5200],
            "trend": "stable"  # 4% increase is considered stable
        }
        
        # Test with specific crime type
        response = await get_crime_trends(2023, 2024, "våldsbrott")
        assert response == {
            "years": [2023, 2024],
            "values": [5000, 5200],
            "trend": "stable"  # 4% increase is considered stable
        }

@pytest.mark.asyncio
async def test_fetch_statistics_no_data():
    """Testa fetch_statistics när data saknas"""
    with patch('politik.main.kolada_client.get_municipality_data') as mock_get_data:
        mock_get_data.side_effect = NoDataError("No data available")
        result = await fetch_statistics(StatisticsType.BEFOLKNING, 1900, "karlstad")
        assert result["data"] is None
        assert "inte tillgänglig" in result["text"]

@pytest.mark.asyncio
async def test_fetch_statistics_validation_error():
    """Testa fetch_statistics med ogiltig data"""
    with patch('politik.main.kolada_client.get_municipality_data') as mock_get_data:
        mock_get_data.side_effect = ValidationError("Invalid data")
        result = await fetch_statistics(StatisticsType.BEFOLKNING, 2024, "karlstad")
        assert result["data"] is None
        assert "kunde inte valideras" in result["text"]

@pytest.mark.asyncio
async def test_fetch_statistics_with_trend():
    """Testa hämtning av statistik med trend"""
    with patch('politik.main.kolada_client.get_municipality_data') as mock_get_data:
        def mock_get_data_func(*args, **kwargs):
            if kwargs.get('year') == 2023:
                return {"value": 93000, "year": 2023}
            return {"value": 92000, "year": 2022}
        
        mock_get_data.side_effect = mock_get_data_func
        result = await fetch_statistics(StatisticsType.BEFOLKNING, 2023, "karlstad")
        assert result["data"] is not None
        assert "trend" in result
        assert "92 000" in result["trend"]
        assert "93 000" in result["trend"] 

@pytest.mark.asyncio
async def test_bra_statistics_extract_number():
    """Test the _extract_number method in BRAStatistics."""
    from politik.main import BRAStatistics
    
    bra = BRAStatistics()
    
    # Test various number formats
    assert bra._extract_number("1500 brott") == 1500
    assert bra._extract_number("1,5 miljoner brott") == 1500000
    assert bra._extract_number("Det anmäldes 42 500 fall") == 42500
    assert bra._extract_number("2024 var ett år med 1337 brott") == 1337  # Should ignore year
    assert bra._extract_number("Ingen siffra här") == 0  # Default case
    
@pytest.mark.asyncio
async def test_bra_statistics_extract_percentage():
    """Test the _extract_percentage method in BRAStatistics."""
    from politik.main import BRAStatistics
    
    bra = BRAStatistics()
    
    # Test various percentage formats
    assert bra._extract_percentage("en ökning med 5,2 procent") == 5.2
    assert bra._extract_percentage("minskade med 3,7%") == -3.7
    assert bra._extract_percentage("ökade 10 procent") == 10.0
    assert bra._extract_percentage("en minskning på 2,5 procent") == -2.5
    assert bra._extract_percentage("ingen procent här") == 0.0  # Default case

@pytest.mark.asyncio
async def test_bra_statistics_extract_statistics():
    """Test the _extract_statistics method in BRAStatistics."""
    from politik.main import BRAStatistics
    from bs4 import BeautifulSoup
    
    html = """
    <main>
        <p>Under 2024 anmäldes 1,5 miljoner brott, en minskning med 5,2 procent</p>
        <h3>Våldsbrott</h3>
        <p>42500 fall anmäldes</p>
        <h3>Egendomsbrott</h3>
        <p>85000 brott anmäldes</p>
    </main>
    """
    
    bra = BRAStatistics()
    soup = BeautifulSoup(html, 'html.parser')
    stats = bra._extract_statistics(soup, 2024)
    
    assert stats["total_crimes"] == 1500000
    assert stats["change_from_previous_year"] == -5.2  # Ändrat till -5.2 eftersom texten anger "minskning"
    assert stats["crimes_by_category"]["Våldsbrott"] == 42500
    assert stats["crimes_by_category"]["Egendomsbrott"] == 85000
    assert stats["crimes_per_100k"] > 0
    assert stats["year"] == 2024
    assert stats["data_quality"] == "preliminary"

@pytest.mark.asyncio
async def test_bra_statistics_get_crime_trends():
    """Test the get_crime_trends method with mocked data."""
    from politik.main import BRAStatistics
    from unittest.mock import patch
    
    mock_stats = {
        "2023": {"total_crimes": 1000000},
        "2024": {"total_crimes": 1100000}  # Ändrat till 10% ökning för att säkerställa "increasing" trend
    }
    
    def mock_fetch_cached_stats(year, crime_type=None):
        year_str = str(year)
        if year_str in mock_stats:
            return mock_stats[year_str]
        return None
    
    with patch.object(BRAStatistics, '_fetch_cached_stats', side_effect=mock_fetch_cached_stats):
        bra = BRAStatistics()
        trends = bra.get_crime_trends(2023, 2024)
        
        assert trends["years"] == [2023, 2024]
        assert trends["values"] == [1000000, 1100000]
        assert trends["trend"] == "increasing"  # Nu borde detta stämma med 10% ökning

@pytest.mark.asyncio
async def test_bra_statistics_context_manager():
    """Test the async context manager functionality."""
    from politik.main import BRAStatistics
    
    async with BRAStatistics() as bra:
        assert isinstance(bra, BRAStatistics)
        # Verify that we can make a request
        stats = await bra.get_crime_statistics(2024)
        assert isinstance(stats, dict)
        assert "total_crimes" in stats

@pytest.mark.asyncio
async def test_fetch_statistics_with_trend():
    """Testa hämtning av statistik med trend"""
    with patch('politik.main.kolada_client.get_municipality_data') as mock_get_data:
        def mock_get_data_func(*args, **kwargs):
            if kwargs.get('year') == 2023:
                return {"value": 93000, "year": 2023}
            return {"value": 92000, "year": 2022}
        
        mock_get_data.side_effect = mock_get_data_func
        result = await fetch_statistics(StatisticsType.BEFOLKNING, 2023, "karlstad")
        assert result["data"] is not None
        assert "trend" in result
        assert "92 000" in result["trend"]
        assert "93 000" in result["trend"] 

@pytest.mark.asyncio
async def test_bra_statistics_error_handling():
    """Test error handling in BRAStatistics."""
    from politik.main import BRAStatistics
    
    # Test timeout error
    with patch('httpx.Client.get', side_effect=httpx.ReadTimeout("Connection timed out")):
        bra = BRAStatistics()
        with pytest.raises(HTTPException) as exc_info:
            await bra.get_crime_statistics(2024)
        assert exc_info.value.status_code == 504
        assert "Timeout" in str(exc_info.value.detail)
    
    # Test general HTTP error
    with patch('httpx.Client.get', side_effect=httpx.HTTPError("HTTP Error")):
        bra = BRAStatistics()
        with pytest.raises(HTTPException) as exc_info:
            await bra.get_crime_statistics(2024)
        assert exc_info.value.status_code == 500
        assert "Error fetching BRÅ statistics" in str(exc_info.value.detail)

@pytest.mark.asyncio
async def test_bra_statistics_caching():
    """Test caching functionality in BRAStatistics."""
    from politik.main import BRAStatistics
    
    html = """
    <main>
        <p>Under 2024 anmäldes 1,5 miljoner brott</p>
    </main>
    """
    
    class MockResponse:
        def __init__(self):
            self.text = html
            self.status_code = 200
        def raise_for_status(self):
            pass
    
    with patch('httpx.Client.get', return_value=MockResponse()):
        bra = BRAStatistics()
        
        # First call should hit the network
        stats1 = await bra.get_crime_statistics(2024)
        assert stats1["total_crimes"] == 1500000
        
        # Second call should use cache
        stats2 = await bra.get_crime_statistics(2024)
        assert stats2["total_crimes"] == 1500000
        
        # Verify we only made one HTTP request
        assert len(bra.cache) == 1
        assert "2024_None" in bra.cache

@pytest.mark.asyncio
async def test_bra_statistics_invalid_html():
    """Test handling of invalid HTML structure."""
    from politik.main import BRAStatistics
    
    # Test with empty HTML
    html = "<html></html>"
    
    class MockResponse:
        def __init__(self):
            self.text = html
            self.status_code = 200
        def raise_for_status(self):
            pass
    
    with patch('httpx.Client.get', return_value=MockResponse()):
        bra = BRAStatistics()
        stats = await bra.get_crime_statistics(2024)
        
        # Should return default values when HTML is invalid
        assert stats["total_crimes"] == 0
        assert stats["crimes_by_category"] == {}
        assert stats["crimes_per_100k"] == 0
        assert stats["change_from_previous_year"] == 0

@pytest.mark.asyncio
async def test_bra_statistics_trend_scenarios():
    """Test different trend scenarios in get_crime_trends."""
    from politik.main import BRAStatistics
    
    def create_mock_stats(values):
        return {str(2020 + i): {"total_crimes": v} for i, v in enumerate(values)}
    
    # Test increasing trend (>5% increase)
    mock_stats_increasing = create_mock_stats([1000, 1100])  # 10% increase
    
    # Test decreasing trend (>5% decrease)
    mock_stats_decreasing = create_mock_stats([1000, 900])  # 10% decrease
    
    # Test stable trend (<5% change)
    mock_stats_stable = create_mock_stats([1000, 1020])  # 2% increase
    
    # Test with missing data
    mock_stats_missing = {"2020": {"total_crimes": 1000}}  # 2021 missing
    
    scenarios = [
        (mock_stats_increasing, "increasing"),
        (mock_stats_decreasing, "decreasing"),
        (mock_stats_stable, "stable"),
        (mock_stats_missing, "stable")  # Default when data is missing
    ]
    
    for mock_stats, expected_trend in scenarios:
        def mock_fetch_cached_stats(year, crime_type=None):
            year_str = str(year)
            return mock_stats.get(year_str)
        
        with patch.object(BRAStatistics, '_fetch_cached_stats', side_effect=mock_fetch_cached_stats):
            bra = BRAStatistics()
            trends = bra.get_crime_trends(2020, 2021)
            assert trends["trend"] == expected_trend

@pytest.mark.asyncio
async def test_fetch_statistics_with_trend():
    """Testa hämtning av statistik med trend"""
    with patch('politik.main.kolada_client.get_municipality_data') as mock_get_data:
        def mock_get_data_func(*args, **kwargs):
            if kwargs.get('year') == 2023:
                return {"value": 93000, "year": 2023}
            return {"value": 92000, "year": 2022}
        
        mock_get_data.side_effect = mock_get_data_func
        result = await fetch_statistics(StatisticsType.BEFOLKNING, 2023, "karlstad")
        assert result["data"] is not None
        assert "trend" in result
        assert "92 000" in result["trend"]
        assert "93 000" in result["trend"] 

@pytest.mark.asyncio
async def test_bra_statistics_extract_percentage_error():
    """Test error handling in _extract_percentage method."""
    from politik.main import BRAStatistics
    
    bra = BRAStatistics()
    
    # Test with invalid number format
    assert bra._extract_percentage("en ökning med abc procent") == 0.0
    
    # Test with missing number
    assert bra._extract_percentage("en ökning med procent") == 0.0
    
    # Test with completely invalid format
    assert bra._extract_percentage("") == 0.0
    
    # Test with None
    assert bra._extract_percentage(None) == 0.0
    
    # Test with invalid decimal format - should not extract number from invalid format
    assert bra._extract_percentage("en ökning med 5..2 procent") == 0.0

@pytest.mark.asyncio
async def test_kolada_api_format_handling():
    """Test handling of different API response formats."""
    with patch('politik.kolada_v2.KoladaClient.get_municipality_data', new_callable=AsyncMock) as mock_get:
        # Mock successful response with new format
        mock_get.return_value = {"value": 42.5, "year": 2024}
        
        client = KoladaClient()
        result = await client.get_municipality_data('1234', 'N00945', 2024)
        assert result["value"] == 42.5
        assert result["year"] == 2024
        
        # Test invalid format
        mock_get.side_effect = NoDataError("No data available")
        with pytest.raises(NoDataError):
            await client.get_municipality_data('1234', 'N00945', 2024)

@pytest.mark.asyncio
async def test_kolada_fallback_exhaustion():
    """Test when no data is available within fallback period."""
    from politik.kolada_v2 import KoladaClient, NoDataError
    
    client = KoladaClient()
    
    with pytest.raises(NoDataError) as exc_info:
        await client.get_municipality_data_with_fallback("N00945", "1780", 2024, max_fallback_years=1)
    assert "Ingen data tillgänglig" in str(exc_info.value)

@pytest.mark.asyncio
async def test_kolada_available_years_error():
    """Test error handling when fetching available years."""
    def mock_get(*args, **kwargs):
        raise httpx.HTTPError("API Error")
        
    with patch('politik.kolada_v2.KoladaClient._make_request', side_effect=mock_get):
        client = KoladaClient()
        years = client.get_available_years('1234', 'N00945')
        assert years == []

@pytest.mark.asyncio
async def test_kolada_latest_year_not_found():
    """Test when no latest year with data is found."""
    from politik.kolada_v2 import KoladaClient
    
    client = KoladaClient()
    
    with patch.object(client, 'get_municipality_data', side_effect=NoDataError("No data")):
        latest_year = client.get_latest_available_year("N00945", "1780")
        assert latest_year is None 

@pytest.mark.asyncio
async def test_motion_request_empty_topic():
    """Test that empty topic raises ValidationError."""
    with pytest.raises(ValueError) as exc_info:
        MotionRequest(topic="", municipality="karlstad")
    
    error_msg = str(exc_info.value)
    assert "String should have at least 1 character" in error_msg

@pytest.mark.asyncio
async def test_grok_all_retries_failed():
    """Test when all Grok API retries fail."""
    from politik.main import call_grok
    
    with patch('requests.post', side_effect=requests.exceptions.RequestException("API Error")):
        with pytest.raises(HTTPException) as exc_info:
            await call_grok("test", "test role")
        assert "API Error (attempt 3/3)" in str(exc_info.value.detail)

@pytest.mark.asyncio
async def test_crime_trends_endpoint_error():
    """Test error handling in get_crime_trends endpoint."""
    from fastapi import HTTPException
    from datetime import datetime
    
    # Test invalid year range
    with pytest.raises(HTTPException) as exc_info:
        await get_crime_trends(2024, 2020)  # end year before start year
    assert exc_info.value.status_code == 400
    assert "End year cannot be before start year" in str(exc_info.value.detail)
    
    # Test future years
    current_year = datetime.now().year
    with pytest.raises(HTTPException) as exc_info:
        await get_crime_trends(current_year + 1, current_year + 2)
    assert exc_info.value.status_code == 400
    assert "Cannot fetch statistics for future years" in str(exc_info.value.detail)
    
    # Test BRÅ API error
    with patch('politik.bra_statistics.BRAStatistics.get_crime_statistics', side_effect=HTTPException(status_code=500, detail="BRÅ API error")):
        with pytest.raises(HTTPException) as exc_info:
            await get_crime_trends(2020, 2022)
        assert exc_info.value.status_code == 500
        assert "BRÅ API error" in str(exc_info.value.detail)

@pytest.mark.asyncio
async def test_format_trend_missing_values():
    """Test trend formatting when values are missing."""
    from politik.statistics import format_trend, StatisticsType
    
    # Test with missing current value
    result = format_trend(
        StatisticsType.BEFOLKNING,
        {"year": 2024},
        {"value": 92000, "year": 2023}
    )
    assert "saknar värden eller år" in result
    
    # Test with missing previous value
    result = format_trend(
        StatisticsType.BEFOLKNING,
        {"value": 93000, "year": 2024},
        {"year": 2023}
    )
    assert "saknar värden eller år" in result
    
    # Test with missing years
    result = format_trend(
        StatisticsType.BEFOLKNING,
        {"value": 93000},
        {"value": 92000}
    )
    assert "saknar värden eller år" in result

@pytest.mark.asyncio
async def test_format_trend_general_error():
    """Test general error handling in trend formatting."""
    from politik.statistics import format_trend, StatisticsType
    
    # Test with invalid value type
    result = format_trend(
        StatisticsType.BEFOLKNING,
        {"value": "not a number", "year": 2024},
        {"value": 92000, "year": 2023}
    )
    assert "Kunde inte formatera trend för befolkning" in result
    
    # Test with invalid statistic type
    result = format_trend(
        StatisticsType.BRA_STATISTIK,  # BRÅ statistik har annat format
        {"value": 93000, "year": 2024},
        {"value": 92000, "year": 2023}
    )
    assert "Kunde inte formatera trend för bra_statistik" in result 

@pytest.mark.asyncio
async def test_fetch_statistics_bra_error_handling():
    """Test error handling in fetch_statistics for BRÅ statistics."""
    with patch('politik.main.BRAStatistics') as MockBRA:
        mock_bra = MockBRA.return_value
        mock_bra.__aenter__.return_value = mock_bra
        mock_bra.__aexit__.return_value = None
        mock_bra.get_crime_statistics = AsyncMock(side_effect=HTTPException(status_code=500, detail="BRÅ API error"))
        
        result = await fetch_statistics(StatisticsType.BRA_STATISTIK, 2024, "karlstad")
        
        assert result["data"] is None
        assert "ej tillgänglig" in result["text"]
        assert "bra_statistik" in result["text"] 