"""Knowledge base: Confluence / Rovo stand-in for product, personas and templates."""

from __future__ import annotations

from typing import Any, Protocol

from ..contracts import ICPDefinition, Persona, ProductFeature, RegulatoryGuide
from ._fixtures import load


class KBConnector(Protocol):
    def get_icp(self) -> dict[str, Any]: ...
    def list_product_features(self) -> list[ProductFeature]: ...
    def list_personas(self) -> list[Persona]: ...
    def list_regulations(self) -> list[RegulatoryGuide]: ...
    def get_brand_voice(self) -> dict[str, Any]: ...
    def get_templates(self) -> dict[str, list[str]]: ...
    def list_executive_voices(self) -> list[dict[str, Any]]: ...


class MockKB:
    def get_icp(self) -> dict[str, Any]:
        return load("icp.json")

    def list_product_features(self) -> list[ProductFeature]:
        rows = load("product_features.json")
        return [
            ProductFeature(
                id=r["id"],
                module=r.get("category", r.get("module", "Identity Security Cloud")),
                capability=r.get("name", r.get("capability", "")),
                description=r.get("summary", r.get("description", "")),
                addresses_gap=r["addresses_gap"],
                value_driver=r.get("value_lever", r.get("value_driver", "")),
            )
            for r in rows
        ]

    def list_personas(self) -> list[Persona]:
        rows = load("personas.json")
        return [
            Persona(
                id=r.get("key", r.get("id", f"P-{i}")),
                title=r["title"],
                seniority=r.get("seniority", "Director"),
                priorities=r.get("priorities", []),
                pain_points=r.get("pains", r.get("pain_points", [])),
                messaging_do=[r.get("messaging_angle", "")] + r.get("proof_points", []),
                messaging_dont=r.get("common_objections", []),
                preferred_proof=r.get("preferred_proof", "quantified ROI"),
            )
            for i, r in enumerate(rows)
        ]

    def list_regulations(self) -> list[RegulatoryGuide]:
        rows = load("regulatory_glossary.json")
        return [
            RegulatoryGuide(
                id=r.get("code", r.get("id", f"REG-{i}")),
                name=r["name"],
                region=r["region"],
                industries=r.get("industries", []),
                summary=r["summary"],
                identity_relevance=r.get(
                    "identity_relevance",
                    "Access governance and least-privilege controls.",
                ),
            )
            for i, r in enumerate(rows)
        ]

    def get_brand_voice(self) -> dict[str, Any]:
        return load("brand_voice.json")

    def get_templates(self) -> dict[str, list[str]]:
        return load("templates.json")

    def list_executive_voices(self) -> list[dict[str, Any]]:
        return load("executive_voices.json")
