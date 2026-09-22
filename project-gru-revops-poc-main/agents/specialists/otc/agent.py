"""RevOps OTC specialist."""

from agents.specialists.otc.prompt import REVOPS_OTC_INSTRUCTION
from agents.specialists.otc.tools import calculate_credit_arr
from agents.specialist_factory import make_specialist
from models.specialist_outputs import RevopsOtcOutput

revops_otc_agent = make_specialist(
    name="revops_otc",
    description="Credit exposure and ARR calculator for the filtered book.",
    instruction=REVOPS_OTC_INSTRUCTION,
    tools=[calculate_credit_arr],
    output_schema=RevopsOtcOutput,
    output_key="revops_otc_result",
)
