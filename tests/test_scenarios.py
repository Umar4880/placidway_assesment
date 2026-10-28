"""
Basic validation tests for test suite scenarios and authorized target URLs.
"""

from src.ingestion.urls import AUTHORIZED_URLS
from tests.scenarios import MANDATORY_TEST_SCENARIOS


def test_authorized_urls_count():
    assert len(AUTHORIZED_URLS) == 7, "Must contain exactly 7 authorized PlacidWay URLs"


def test_mandatory_scenarios_count():
    assert len(MANDATORY_TEST_SCENARIOS) == 8, "Must contain exactly 8 mandatory test scenarios"
