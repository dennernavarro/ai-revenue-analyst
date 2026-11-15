import pytest

from revenue_analyst.config import Settings
from revenue_analyst.pms.factory import build_provider
from revenue_analyst.pms.mock import MockPMS


def test_default_provider_is_the_mock():
    assert isinstance(build_provider(Settings()), MockPMS)


def test_unknown_provider_names_the_options():
    with pytest.raises(ValueError, match="available: mock, template"):
        build_provider(Settings(pms_provider="hotelx"))
