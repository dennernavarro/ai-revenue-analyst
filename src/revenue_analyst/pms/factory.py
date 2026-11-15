"""Provider selection: which PMS backs this process.

`RA_PMS_PROVIDER` picks the adapter (default "mock"). Integrating a real PMS
is three steps:

1. Implement the PMSProvider protocol in a new module — copy
   pms/template.py and fill in its TODOs.
2. Register the adapter in PROVIDERS below.
3. Add it to the `provider` fixture in tests/test_pms_contract.py: the same
   suite that validates the mock validates your integration. When it passes,
   you are done — agents, analytics, API and UI need zero changes.
"""

from __future__ import annotations

from revenue_analyst.config import Settings
from revenue_analyst.pms.mock import MockPMS
from revenue_analyst.pms.provider import PMSProvider


def _mock(settings: Settings) -> PMSProvider:
    return MockPMS(settings.data_dir)


def _template(settings: Settings) -> PMSProvider:
    from revenue_analyst.pms.template import TemplatePMSAdapter

    return TemplatePMSAdapter()


PROVIDERS = {
    "mock": _mock,
    "template": _template,
}


def build_provider(settings: Settings) -> PMSProvider:
    try:
        factory = PROVIDERS[settings.pms_provider]
    except KeyError:
        available = ", ".join(sorted(PROVIDERS))
        raise ValueError(
            f"Unknown PMS provider {settings.pms_provider!r} "
            f"(RA_PMS_PROVIDER) — available: {available}"
        ) from None
    return factory(settings)
