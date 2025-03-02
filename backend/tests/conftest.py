import pytest

def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "timeout: mark test to set a timeout value"
    ) 