"""RevOps pricing analytics specialist."""

from agents.specialists.pricing.prompt import REVOPS_PRICING_INSTRUCTION
from agents.specialists.pricing.tools import run_pricing_analytics
from agents.specialist_factory import make_specialist
from models.specialist_outputs import RevopsPricingOutput

revops_pricing_agent = make_specialist(
    name="revops_pricing",
    description="Pricing waterfall, floor checks, and peer discount bands.",
    instruction=REVOPS_PRICING_INSTRUCTION,
    tools=[run_pricing_analytics],
    output_schema=RevopsPricingOutput,
    output_key="revops_pricing_result",
)
