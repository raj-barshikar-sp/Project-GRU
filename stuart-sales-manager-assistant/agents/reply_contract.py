"""Shared output contract injected into every specialist."""

REPLY_CONTRACT = """
OUTPUT CONTRACT
Return only SpecialistReport. Answer the part you own, retain the concrete
facts Stuart needs, and recommend only actions supported by the supplied data.
Do not address the manager directly; Stuart writes the final response.
""".strip()
