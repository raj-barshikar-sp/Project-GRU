"""RevOps reporting specialist."""

from agents.specialists.reporting.prompt import REVOPS_REPORTING_INSTRUCTION
from agents.specialists.reporting.tools import build_revops_pack
from agents.specialist_factory import make_specialist
from models.specialist_outputs import RevopsReportingOutput

revops_reporting_agent = make_specialist(
    name="revops_reporting",
    description="QBR decks, forecast reviews, pipeline reviews, and KPI packs.",
    instruction=REVOPS_REPORTING_INSTRUCTION,
    tools=[build_revops_pack],
    output_schema=RevopsReportingOutput,
    output_key="revops_reporting_result",
)
