"""Channel templates: Marketo, LinkedIn, Folloze, ad platforms (mocked deploys)."""

from __future__ import annotations

from typing import Any, Protocol


class ChannelsConnector(Protocol):
    def get_email_template_structure(self) -> dict[str, Any]: ...
    def get_folloze_template(self) -> dict[str, Any]: ...
    def draft_channel_package(
        self, channel: str, account: str, payload: dict[str, Any]
    ) -> dict[str, Any]: ...


class MockChannels:
    def get_email_template_structure(self) -> dict[str, Any]:
        return {
            "fields": ["Account", "Persona", "Touch", "Send Day",
                       "Subject", "Body", "CTA"],
            "recommended_touches": 4,
            "notes": "Export as CSV for Marketo bulk import.",
        }

    def get_folloze_template(self) -> dict[str, Any]:
        return {
            "module_types": ["video", "case_study", "product_brief", "whitepaper"],
            "max_modules": 4,
            "notes": "Personalize banner and CTA per account.",
        }

    def draft_channel_package(
        self, channel: str, account: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "channel": channel,
            "account": account,
            "status": "MOCK: draft package ready for review",
            "payload": payload,
        }
