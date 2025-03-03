import pytest
import requests
from datetime import datetime
from politik.kolada_v2 import (
    KoladaClient,
    KoladaError,
    NoDataError,
    ValidationError,
    InvalidKPIError,
    KPIMetadata,
    DataType
)

@pytest.fixture
def kolada_client():
    return KoladaClient()

def get_mock_kpi_metadata(kpi_id: str = "N01900"):
    """Get mock metadata for a specific KPI"""
    kpi_data = {
        "N01900": {
            "id": "N01900",
            "title": "Befolkning",
            "description": "Antal invånare totalt",
            "municipality_type": True,
            "has_municipality_data": True,
            "is_numbered": True,
            "operating_area": "Befolkning",
            "perspective": "Demografi"
        },
        "N07403": {
            "id": "N07403",
            "title": "Våldsbrott",
            "description": "Antal anmälda våldsbrott per 100k invånare",
            "municipality_type": True,
            "has_municipality_data": True,
            "is_numbered": True,
            "operating_area": "Trygghet",
            "perspective": "Säkerhet"
        },
        "N03101": {
            "id": "N03101",
            "title": "Ekonomiskt resultat",
            "description": "Kommunens ekonomiska resultat i miljoner kronor",
            "municipality_type": True,
            "has_municipality_data": True,
            "is_numbered": True,
            "operating_area": "Ekonomi",
            "perspective": "Resultat"
        }
    }
    return {"values": [kpi_data.get(kpi_id, kpi_data["N01900"])]}

def get_mock_municipality_data(value: float, year: int = 2024):
    return {
        "values": [{
            "period": str(year),
            "values": [{
                "value": value,
                "gender": "T"
            }]
        }]
    }

def get_mock_municipality_data_old_format(value: float, year: int = 2024):
    """Mock data i gamla API-formatet"""
    return {
        "values": [{
            "value": value,
            "period": str(year),
            "gender": "T"
        }]
    }

def test_get_kpi_metadata(kolada_client, requests_mock):
    # Arrange
    kpi_id = "N01900"
    requests_mock.get(
        f"{KoladaClient.BASE_URL}/kpi/{kpi_id}",
        json=get_mock_kpi_metadata()
    )

    # Act
    metadata = kolada_client.get_kpi_metadata(kpi_id)

    # Assert
    assert isinstance(metadata, KPIMetadata)
    assert metadata.id == kpi_id
    assert metadata.title == "Befolkning"
    assert metadata.description == "Antal invånare totalt"

def test_get_municipality_data(kolada_client, requests_mock):
    # Arrange
    kpi_id = "N01900"
    municipality_id = "1715"
    year = 2024
    expected_value = 95000

    requests_mock.get(
        f"{KoladaClient.BASE_URL}/kpi/{kpi_id}",
        json=get_mock_kpi_metadata()
    )
    requests_mock.get(
        f"{KoladaClient.BASE_URL}/data/v1/kpi",
        json=get_mock_municipality_data(expected_value, year)
    )

    # Act
    result = kolada_client.get_municipality_data(kpi_id, municipality_id, year)

    # Assert
    assert result["value"] == expected_value
    assert result["year"] == year
    assert result["municipality"] == municipality_id
    assert result["kpi"] == kpi_id

def test_invalid_kpi(kolada_client, requests_mock):
    # Arrange
    kpi_id = "INVALID"
    requests_mock.get(
        f"{KoladaClient.BASE_URL}/kpi/{kpi_id}",
        json={"values": []}
    )

    # Act & Assert
    with pytest.raises(InvalidKPIError):
        kolada_client.get_kpi_metadata(kpi_id)

def test_no_data_available(kolada_client, requests_mock):
    # Arrange
    kpi_id = "N01900"
    municipality_id = "1715"
    year = 2024

    requests_mock.get(
        f"{KoladaClient.BASE_URL}/kpi/{kpi_id}",
        json=get_mock_kpi_metadata()
    )
    requests_mock.get(
        f"{KoladaClient.BASE_URL}/data/v1/kpi",
        json={"values": []}
    )

    # Act & Assert
    with pytest.raises(NoDataError):
        kolada_client.get_municipality_data(kpi_id, municipality_id, year)

def test_validation_error(kolada_client, requests_mock):
    # Arrange
    kpi_id = "N01900"  # Befolkning (ska vara mellan 50000-150000 för Karlstad)
    municipality_id = "1715"
    year = 2024
    invalid_value = 10000  # För lågt för Karlstad

    requests_mock.get(
        f"{KoladaClient.BASE_URL}/kpi/{kpi_id}",
        json=get_mock_kpi_metadata()
    )
    requests_mock.get(
        f"{KoladaClient.BASE_URL}/data/v1/kpi",
        json=get_mock_municipality_data(invalid_value, year)
    )

    # Act & Assert
    with pytest.raises(ValidationError):
        kolada_client.get_municipality_data(kpi_id, municipality_id, year)

def test_api_timeout(kolada_client, requests_mock):
    # Arrange
    kpi_id = "N01900"
    requests_mock.get(
        f"{KoladaClient.BASE_URL}/kpi/{kpi_id}",
        exc=requests.exceptions.Timeout
    )

    # Act & Assert
    with pytest.raises(KoladaError):
        kolada_client.get_kpi_metadata(kpi_id)

def test_get_municipality_data_with_fallback(kolada_client, requests_mock):
    # Arrange
    kpi_id = "N01900"
    municipality_id = "1715"
    target_year = 2024
    fallback_year = 2023
    expected_value = 95000

    # Mock metadata request
    requests_mock.get(
        f"{KoladaClient.BASE_URL}/kpi/{kpi_id}",
        json=get_mock_kpi_metadata()
    )
    
    # Mock target year (no data)
    requests_mock.get(
        f"{KoladaClient.BASE_URL}/data/v1/kpi",
        [
            {'json': {"values": []}, 'status_code': 200},  # First call (2024)
            {'json': get_mock_municipality_data(expected_value, fallback_year), 'status_code': 200}  # Second call (2023)
        ]
    )

    # Act
    result = kolada_client.get_municipality_data_with_fallback(kpi_id, municipality_id, target_year)

    # Assert
    assert result["value"] == expected_value
    assert result["year"] == fallback_year
    assert result["municipality"] == municipality_id
    assert result["kpi"] == kpi_id

def test_metadata_caching(kolada_client, requests_mock):
    # Arrange
    kpi_id = "N01900"
    requests_mock.get(
        f"{KoladaClient.BASE_URL}/kpi/{kpi_id}",
        json=get_mock_kpi_metadata()
    )

    # Act
    metadata1 = kolada_client.get_kpi_metadata(kpi_id)
    metadata2 = kolada_client.get_kpi_metadata(kpi_id)

    # Assert
    assert metadata1 == metadata2
    assert requests_mock.call_count == 1  # Should only make one request due to caching 

def test_old_api_format(kolada_client, requests_mock):
    # Arrange
    kpi_id = "N01900"
    municipality_id = "1715"
    year = 2024
    expected_value = 95000

    requests_mock.get(
        f"{KoladaClient.BASE_URL}/kpi/{kpi_id}",
        json=get_mock_kpi_metadata()
    )
    requests_mock.get(
        f"{KoladaClient.BASE_URL}/data/v1/kpi",
        json=get_mock_municipality_data_old_format(expected_value, year)
    )

    # Act
    result = kolada_client.get_municipality_data(kpi_id, municipality_id, year)

    # Assert
    assert result["value"] == expected_value
    assert result["year"] == year

def test_validation_error_violent_crimes(kolada_client, requests_mock):
    # Arrange
    kpi_id = "N07403"  # Våldsbrott (ska vara mellan 0-2000 per 100k inv)
    municipality_id = "1715"
    year = 2024
    invalid_value = 2500  # För högt

    requests_mock.get(
        f"{KoladaClient.BASE_URL}/kpi/{kpi_id}",
        json=get_mock_kpi_metadata(kpi_id)
    )
    requests_mock.get(
        f"{KoladaClient.BASE_URL}/data/v1/kpi",
        json=get_mock_municipality_data(invalid_value, year)
    )

    # Act & Assert
    with pytest.raises(ValidationError):
        kolada_client.get_municipality_data(kpi_id, municipality_id, year)

def test_validation_error_economic_result(kolada_client, requests_mock):
    # Arrange
    kpi_id = "N03101"  # Ekonomiskt resultat (ska vara mellan -1000 och 1000 mkr)
    municipality_id = "1715"
    year = 2024
    invalid_value = -1500  # För lågt

    requests_mock.get(
        f"{KoladaClient.BASE_URL}/kpi/{kpi_id}",
        json=get_mock_kpi_metadata(kpi_id)
    )
    requests_mock.get(
        f"{KoladaClient.BASE_URL}/data/v1/kpi",
        json=get_mock_municipality_data(invalid_value, year)
    )

    # Act & Assert
    with pytest.raises(ValidationError):
        kolada_client.get_municipality_data(kpi_id, municipality_id, year)

def test_valid_values_pass_validation(kolada_client, requests_mock):
    # Test cases för olika KPI:er med giltiga värden
    test_cases = [
        ("N01900", 100000),  # Befolkning
        ("N07403", 1500),    # Våldsbrott
        ("N03101", 500),     # Ekonomiskt resultat
        ("P01234", 75),      # Procentvärde
        ("N99999", 1000)     # Generiskt numeriskt värde
    ]

    for kpi_id, valid_value in test_cases:
        # Arrange
        requests_mock.get(
            f"{KoladaClient.BASE_URL}/kpi/{kpi_id}",
            json=get_mock_kpi_metadata()
        )
        requests_mock.get(
            f"{KoladaClient.BASE_URL}/data/v1/kpi",
            json=get_mock_municipality_data(valid_value, 2024)
        )

        # Act
        result = kolada_client.get_municipality_data(kpi_id, "1715", 2024)

        # Assert
        assert result["value"] == valid_value

@pytest.mark.asyncio
async def test_api_format_handling(requests_mock):
    """Testa hantering av olika API-format"""
    client = KoladaClient()
    
    # Mock metadata request
    requests_mock.get(
        f"{KoladaClient.BASE_URL}/kpi/test",
        json=get_mock_kpi_metadata()
    )
    
    # Test new API format
    new_format_data = {
        "values": [{
            "period": "2023",
            "values": [{"value": "42.5"}]
        }]
    }
    requests_mock.get(
        f"{KoladaClient.BASE_URL}/data/v1/kpi",
        json=new_format_data
    )
    result = client.get_municipality_data("test", "1715", 2023)
    assert result["value"] == 42.5
    
    # Test old API format
    old_format_data = {
        "values": [{
            "value": "42.5",
            "period": "2023"
        }]
    }
    requests_mock.get(
        f"{KoladaClient.BASE_URL}/data/v1/kpi",
        json=old_format_data
    )
    result = client.get_municipality_data("test", "1715", 2023)
    assert result["value"] == 42.5

@pytest.mark.asyncio
async def test_value_validation(requests_mock):
    """Testa validering av värden"""
    client = KoladaClient()
    
    # Mock metadata request
    requests_mock.get(
        f"{KoladaClient.BASE_URL}/kpi/N01900",
        json=get_mock_kpi_metadata()
    )
    
    # Test valid value for population (N01900)
    requests_mock.get(
        f"{KoladaClient.BASE_URL}/data/v1/kpi",
        json=get_mock_municipality_data(95000)  # Valid population for Karlstad
    )
    result = client.get_municipality_data("N01900", "1715", 2023)
    assert result["value"] == 95000
    
    # Test negative value for economic result (N03101)
    requests_mock.get(
        f"{KoladaClient.BASE_URL}/kpi/N03101",
        json=get_mock_kpi_metadata()
    )
    requests_mock.get(
        f"{KoladaClient.BASE_URL}/data/v1/kpi",
        json=get_mock_municipality_data(-10.0)
    )
    result = client.get_municipality_data("N03101", "1715", 2023)
    assert result["value"] == -10.0

@pytest.mark.asyncio
async def test_latest_available_year(requests_mock):
    # Arrange
    client = KoladaClient()
    
    # Mock metadata request
    requests_mock.get(
        f"{KoladaClient.BASE_URL}/kpi/test",
        json=get_mock_kpi_metadata("test")
    )
    
    # Mock data request
    requests_mock.get(
        f"{KoladaClient.BASE_URL}/data/v1/kpi",
        json={
            "values": [
                {
                    "period": "2023",
                    "values": [{
                        "value": 43.5,
                        "gender": "T"
                    }]
                },
                {
                    "period": "2022",
                    "values": [{
                        "value": 42.5,
                        "gender": "T"
                    }]
                }
            ]
        }
    )
    
    # Test getting latest year
    latest = client.get_latest_available_year("test", "1715")
    assert latest == 2023 

def test_latest_data_handling(requests_mock):
    """Test att systemet kan hantera och hitta senaste tillgängliga data."""
    client = KoladaClient()
    kpi_id = "N01900"
    municipality_id = "1715"
    
    # Simulera att bara 2023 data finns tillgänglig först
    requests_mock.get(
        f"{KoladaClient.BASE_URL}/kpi/{kpi_id}",
        json=get_mock_kpi_metadata(kpi_id)
    )
    
    # Mock för get_available_years och get_municipality_data
    requests_mock.get(
        f"{KoladaClient.BASE_URL}/data/v1/kpi",
        [
            # Första anropet - bara 2023 data
            {
                'json': {
                    "values": [
                        {
                            "period": "2023",
                            "values": [{"value": "95000", "gender": "T"}]
                        }
                    ]
                }
            },
            # Andra anropet - 2023 och 2024 data
            {
                'json': {
                    "values": [
                        {
                            "period": "2024",
                            "values": [{"value": "96000", "gender": "T"}]
                        },
                        {
                            "period": "2023",
                            "values": [{"value": "95000", "gender": "T"}]
                        }
                    ]
                }
            },
            # Tredje anropet - för get_municipality_data
            {
                'json': {
                    "values": [
                        {
                            "period": "2024",
                            "values": [{"value": "96000", "gender": "T"}]
                        }
                    ]
                }
            }
        ]
    )
    
    # Verifiera att systemet hittar 2023 data
    latest_year = client.get_latest_available_year(kpi_id, municipality_id)
    assert latest_year == 2023
    
    # Verifiera att systemet hittar den nya 2024 datan
    latest_year = client.get_latest_available_year(kpi_id, municipality_id)
    assert latest_year == 2024
    
    # Verifiera att get_municipality_data_with_fallback använder senaste tillgängliga data
    data = client.get_municipality_data_with_fallback(kpi_id, municipality_id, 2025)
    assert data["year"] == 2024
    assert data["value"] == 96000 