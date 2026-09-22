"""RevOps forecast specialist."""

from agents.specialists.forecast.prompt import REVOPS_FORECAST_INSTRUCTION
from agents.specialists.forecast.tools import (
    list_forecast_gaps,
    list_forecast_risks,
    rollup_forecast,
)
from agents.specialist_factory import make_specialist
from models.specialist_outputs import RevopsForecastOutput

revops_forecast_agent = make_specialist(
    name="revops_forecast",
    description="Regional forecast rollups, missing number fields, and commit risk.",
    instruction=REVOPS_FORECAST_INSTRUCTION,
    tools=[rollup_forecast, list_forecast_gaps, list_forecast_risks],
    output_schema=RevopsForecastOutput,
    output_key="revops_forecast_result",
)
