"""The list load, as a fixed four-step chain.

This is a `SequentialAgent` rather than one agent with four tools on purpose.
The SOP has a required order: you cannot validate before cleaning, and you must
never load before validating. A single agent would usually get that order right
and occasionally would not. A SequentialAgent gets it right every time, because
the order is code rather than a suggestion in a prompt.

Each step's real work happens in a tool. The model's only job is to report what
the step found in plain language.
"""

from __future__ import annotations

from google.adk.agents import LlmAgent, SequentialAgent
from mktg_core.settings import DEFAULT_MODEL
from tools.marketing_ops.mops_tools import (
    clean_lead_rows,
    load_cleaned_list,
    read_lead_file,
    validate_lead_rows,
)

from ..prompts import (
    MOPS_LIST_LOAD_CLEANER_DESCRIPTION,
    MOPS_LIST_LOAD_CLEANER_INSTRUCTION,
    MOPS_LIST_LOAD_DESCRIPTION,
    MOPS_LIST_LOAD_LOADER_DESCRIPTION,
    MOPS_LIST_LOAD_LOADER_INSTRUCTION,
    MOPS_LIST_LOAD_READER_DESCRIPTION,
    MOPS_LIST_LOAD_READER_INSTRUCTION,
    MOPS_LIST_LOAD_VALIDATOR_DESCRIPTION,
    MOPS_LIST_LOAD_VALIDATOR_INSTRUCTION,
)

reader = LlmAgent(
    model=DEFAULT_MODEL,
    name="mops_list_load_reader",
    description=MOPS_LIST_LOAD_READER_DESCRIPTION,
    instruction=MOPS_LIST_LOAD_READER_INSTRUCTION,
    tools=[read_lead_file],
    output_key="mops_list_load_read_report",
)

cleaner = LlmAgent(
    model=DEFAULT_MODEL,
    name="mops_list_load_cleaner",
    description=MOPS_LIST_LOAD_CLEANER_DESCRIPTION,
    instruction=MOPS_LIST_LOAD_CLEANER_INSTRUCTION,
    tools=[clean_lead_rows],
    output_key="mops_list_load_clean_report",
)

validator = LlmAgent(
    model=DEFAULT_MODEL,
    name="mops_list_load_validator",
    description=MOPS_LIST_LOAD_VALIDATOR_DESCRIPTION,
    instruction=MOPS_LIST_LOAD_VALIDATOR_INSTRUCTION,
    tools=[validate_lead_rows],
    output_key="mops_list_load_validation_report",
)

loader = LlmAgent(
    model=DEFAULT_MODEL,
    name="mops_list_load_loader",
    description=MOPS_LIST_LOAD_LOADER_DESCRIPTION,
    instruction=MOPS_LIST_LOAD_LOADER_INSTRUCTION,
    tools=[load_cleaned_list],
    output_key="mops_list_load_result",
)

list_load_pipeline = SequentialAgent(
    name="mops_list_load",
    description=MOPS_LIST_LOAD_DESCRIPTION,
    sub_agents=[reader, cleaner, validator, loader],
)
