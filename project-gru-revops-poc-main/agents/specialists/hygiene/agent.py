"""RevOps hygiene specialist."""

from agents.specialists.hygiene.prompt import REVOPS_HYGIENE_INSTRUCTION
from agents.specialists.hygiene.tools import inspect_deal_hygiene
from agents.specialist_factory import make_specialist
from models.specialist_outputs import RevopsHygieneOutput

revops_hygiene_agent = make_specialist(
    name="revops_hygiene",
    description="Inspect expected fields, participation, deal hygiene, and notes.",
    instruction=REVOPS_HYGIENE_INSTRUCTION,
    tools=[inspect_deal_hygiene],
    output_schema=RevopsHygieneOutput,
    output_key="revops_hygiene_result",
)
