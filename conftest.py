import pytest


@pytest.fixture
def base_url() -> str:
    return "http://localhost:8000"
