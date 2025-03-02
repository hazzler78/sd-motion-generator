import pytest
from fastapi.testclient import TestClient
from politik.main import app, MotionRequest, XAI_URL
from politik.statistics import StatisticsType
import requests
from unittest import mock
from fastapi import HTTPException
import os
import importlib

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

def test_agent_1_suggestion():
    """Testa agent_1_suggestion funktionen"""
    from politik.main import agent_1_suggestion
    suggestion = agent_1_suggestion("trygghet")
    assert isinstance(suggestion, str)
    assert len(suggestion) > 0

def test_agent_2_draft():
    """Testa agent_2_draft funktionen"""
    from politik.main import agent_2_draft
    draft = agent_2_draft("Ett förslag om trygghet")
    assert isinstance(draft, str)
    assert len(draft) > 0
    assert "bakgrund" in draft.lower() or "att-satser" in draft.lower()

def test_agent_3_improve():
    """Testa agent_3_improve funktionen"""
    from politik.main import agent_3_improve
    statistics = [
        {
            "text": "Karlstad har 93 000 invånare (2023)",
            "trend": "Befolkningsutveckling: 92 000 (2022) → 93 000 (2023)",
            "data": {"value": 93000, "year": 2023}
        }
    ]
    improved = agent_3_improve("En motion om trygghet", statistics)
    assert isinstance(improved, str)
    assert len(improved) > 0
    assert "93 000" in improved

def test_fetch_statistics_no_data():
    """Testa fetch_statistics när data saknas"""
    from politik.main import fetch_statistics, StatisticsType
    result = fetch_statistics(StatisticsType.BEFOLKNING, 1900, "karlstad")  # Använder ett år långt tillbaka
    assert result["data"] is None
    assert "inte tillgänglig" in result["text"]

def test_fetch_statistics_invalid_municipality():
    """Testa fetch_statistics med ogiltig kommun"""
    from politik.main import fetch_statistics, StatisticsType
    result = fetch_statistics(StatisticsType.BEFOLKNING, 2023, "invalid")
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
async def test_health_check_detailed_errors(mocker):
    """Testa detaljerad felhantering i health check"""
    # Mock Kolada error
    kolada_error = Exception("Detailed Kolada error")
    mocker.patch('politik.main.kolada_client.get_municipality_data', side_effect=kolada_error)
    
    # Mock Grok error
    grok_error = Exception("Detailed Grok error")
    mocker.patch('politik.main.call_grok', side_effect=grok_error)
    
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    
    assert data["kolada"] == "unknown"
    assert data["ai_service"] == "unknown"
    assert "Detailed Kolada error" in data["error"]

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