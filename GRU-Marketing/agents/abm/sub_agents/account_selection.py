"""Account selection and tiering."""

from __future__ import annotations

from google.adk.agents import LlmAgent
from mktg_core.settings import DEFAULT_MODEL
from tools._shared.profile_tools import get_current_user
from tools.abm.abm_tools import get_top_accounts

from ..prompts import (
    ABM_ACCOUNT_SELECTION_DESCRIPTION,
    ABM_ACCOUNT_SELECTION_INSTRUCTION,
)

account_selection_agent = LlmAgent(
    model=DEFAULT_MODEL,
    name="abm_account_selection",
    description=ABM_ACCOUNT_SELECTION_DESCRIPTION,
    instruction=ABM_ACCOUNT_SELECTION_INSTRUCTION,
    tools=[get_top_accounts, get_current_user],
    output_key="abm_account_selection",
)
