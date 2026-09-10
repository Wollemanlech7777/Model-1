from integrations.crm import CRMAdapter
from integrations.email import EmailAdapter
from integrations.legacy import LegacyAdapter
from integrations.portal import PortalAdapter


def test_adapter_interfaces_are_abstract() -> None:
    for cls in (CRMAdapter, LegacyAdapter, EmailAdapter, PortalAdapter):
        assert getattr(cls, "__abstractmethods__", None)
