import pytest
from politik.statistics import (
    StatisticsType,
    get_municipality_id,
    format_statistic,
    format_trend,
    get_kpi_config,
    VARMLAND_MUNICIPALITIES,
    format_value
)

def test_get_municipality_id_valid():
    """Testa att hämta kommun-ID för giltiga kommuner"""
    assert get_municipality_id("karlstad") == "1715"
    assert get_municipality_id("ARVIKA") == "1784"  # Test case insensitive
    assert get_municipality_id("Säffle") == "1785"  # Test with Swedish characters

def test_get_municipality_id_invalid():
    """Testa att hämta kommun-ID för ogiltiga kommuner"""
    assert get_municipality_id("stockholm") is None
    assert get_municipality_id("") is None
    assert get_municipality_id("123") is None

def test_varmland_municipalities_completeness():
    """Testa att alla värmländska kommuner finns med"""
    expected_municipalities = {
        "arvika", "eda", "filipstad", "forshaga", "grums",
        "hagfors", "hammarö", "karlstad", "kil", "kristinehamn",
        "munkfors", "storfors", "sunne", "säffle", "torsby", "årjäng"
    }
    actual_municipalities = set(VARMLAND_MUNICIPALITIES.keys())
    assert actual_municipalities == expected_municipalities

def test_format_statistic_with_municipality():
    """Testa statistikformattering med olika kommuner"""
    # Test för befolkningsstatistik
    data = {
        "value": 93000,
        "year": 2023,
        "municipality": "Karlstad"
    }
    result = format_statistic(StatisticsType.BEFOLKNING, data)
    assert "Karlstad har 93 000 invånare" in result
    
    # Test för annan kommun
    data["municipality"] = "Arvika"
    data["value"] = 26000
    result = format_statistic(StatisticsType.BEFOLKNING, data)
    assert "Arvika har 26 000 invånare" in result

def test_format_trend_with_municipality():
    """Testa trendformattering med olika kommuner"""
    current_data = {
        "value": 93000,
        "year": 2023,
        "municipality": "Karlstad"
    }
    previous_data = {
        "value": 92000,
        "year": 2022,
        "municipality": "Karlstad"
    }
    
    result = format_trend(StatisticsType.BEFOLKNING, current_data, previous_data)
    assert "Befolkningsutveckling i Karlstad" in result
    assert "92 000 (2022) → 93 000 (2023)" in result

def test_format_statistic_with_special_chars():
    """Testa formattering med svenska tecken"""
    data = {
        "value": 15000,
        "year": 2023,
        "municipality": "Säffle"
    }
    result = format_statistic(StatisticsType.BEFOLKNING, data)
    assert "Säffle har 15 000 invånare" in result

def test_format_statistic_validation():
    """Testa validering av statistikdata"""
    # Test med saknade fält
    data = {"year": 2023}  # Saknar value
    result = format_statistic(StatisticsType.BEFOLKNING, data)
    assert "Kunde inte formatera statistik" in result

    # Test med ogiltigt värde
    data = {
        "value": "invalid",
        "year": 2023,
        "municipality": "Karlstad"
    }
    result = format_statistic(StatisticsType.BEFOLKNING, data)
    assert "Kunde inte formatera statistik" in result

def test_format_value_percent():
    """Testa formattering av procentvärden"""
    assert format_value(42.567, "percent") == "42.6"
    assert format_value(0.123, "percent") == "0.1"
    assert format_value(100.0, "percent") == "100.0"

def test_format_value_fallback():
    """Testa formattering med okänd format-typ"""
    assert format_value(42.567, "unknown") == "42.567"
    assert format_value(42, "unknown") == "42"

def test_format_trend_edge_cases():
    """Testa trend-formattering för edge cases"""
    # Test när värden är identiska
    current = {"value": 100, "year": 2023, "municipality": "Karlstad"}
    previous = {"value": 100, "year": 2022, "municipality": "Karlstad"}
    trend = format_trend(StatisticsType.BEFOLKNING, current, previous)
    assert "→" in trend  # Kontrollera att pilen finns
    assert "100" in trend  # Kontrollera att värdet finns
    
    # Test med mycket små skillnader
    current = {"value": 100.001, "year": 2023, "municipality": "Karlstad"}
    previous = {"value": 100, "year": 2022, "municipality": "Karlstad"}
    trend = format_trend(StatisticsType.BEFOLKNING, current, previous)
    assert "→" in trend
    assert "100" in trend

def test_invalid_statistics_type():
    """Testa felhantering för ogiltig statistiktyp"""
    # Skapa en ogiltig enum-medlem för test
    invalid_type = "INVALID_TYPE"
    assert get_kpi_config(invalid_type) is None 