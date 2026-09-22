"""RevOps quoting specialist."""

from agents.specialists.quoting.prompt import REVOPS_QUOTING_INSTRUCTION
from agents.specialists.quoting.tools import (
    analyze_quote_deviations,
    list_product_bundles,
    validate_quote_errors,
)
from agents.specialist_factory import make_specialist
from models.specialist_outputs import RevopsQuotingOutput

revops_quoting_agent = make_specialist(
    name="revops_quoting",
    description="Quote pricing deviations, quote errors, and product bundles.",
    instruction=REVOPS_QUOTING_INSTRUCTION,
    tools=[analyze_quote_deviations, validate_quote_errors, list_product_bundles],
    output_schema=RevopsQuotingOutput,
    output_key="revops_quoting_result",
)
