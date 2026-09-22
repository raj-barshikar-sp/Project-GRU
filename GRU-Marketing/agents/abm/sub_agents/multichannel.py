"""Multi-channel ABM package: email, LinkedIn, Folloze, playbook."""

from __future__ import annotations

from google.adk.agents import LlmAgent
from mktg_core.settings import DEFAULT_MODEL
from tools.abm.abm_tools import save_abm_artifact

from ..prompts import (
    ABM_MULTICHANNEL_PACKAGE_DESCRIPTION,
    ABM_MULTICHANNEL_PACKAGE_INSTRUCTION,
)

package_builder = LlmAgent(
    model=DEFAULT_MODEL,
    name="abm_multichannel_package",
    description=ABM_MULTICHANNEL_PACKAGE_DESCRIPTION,
    instruction=ABM_MULTICHANNEL_PACKAGE_INSTRUCTION,
    tools=[save_abm_artifact],
    output_key="abm_multichannel_package",
)

multichannel_package = package_builder
