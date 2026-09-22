"""Load Vertex/ADC env defaults before agents are constructed."""

from __future__ import annotations

import os
import warnings

from dotenv import load_dotenv

load_dotenv()

from agents.activity import configure_logging

configure_logging()

_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
if _PROJECT and not os.environ.get("GOOGLE_CLOUD_QUOTA_PROJECT"):
    os.environ["GOOGLE_CLOUD_QUOTA_PROJECT"] = _PROJECT

warnings.filterwarnings(
    "ignore",
    message=r"Your application has authenticated using end user credentials.*",
)
