"""Marketing Operations orchestrator.

The simplest of the three, and the only one that writes anything. Three
single-shot actions hang directly off the router as tools, because putting a
sub-agent in front of a one-call action would just add a hop. Only the list
load, which has a required order of steps, gets its own chain.

Note what the router does and does not decide. For a segment request it works
out the filters from plain English, which is genuine reasoning. It never
decides what to write into Salesforce; that is fixed by the tool.
"""

from __future__ import annotations

from google.adk.agents import LlmAgent
from mktg_core.settings import DEFAULT_MODEL, thinking_planner
from tools._shared.profile_tools import get_current_user
from tools.marketing_ops.mops_tools import (
    build_6sense_segment,
    create_sfdc_campaign,
    deploy_segment_to_marketo,
)

from .prompts import (
    MOPS_ORCHESTRATOR_DESCRIPTION,
    MOPS_ORCHESTRATOR_INSTRUCTION,
)
from .sub_agents import list_load_pipeline

marketing_ops_orchestrator = LlmAgent(
    model=DEFAULT_MODEL,
    name="mops_orchestrator",
    description=MOPS_ORCHESTRATOR_DESCRIPTION,
    instruction=MOPS_ORCHESTRATOR_INSTRUCTION,
    planner=thinking_planner(),
    tools=[
        create_sfdc_campaign,
        build_6sense_segment,
        deploy_segment_to_marketo,
        get_current_user,
    ],
    sub_agents=[list_load_pipeline],
)

root_agent = marketing_ops_orchestrator
