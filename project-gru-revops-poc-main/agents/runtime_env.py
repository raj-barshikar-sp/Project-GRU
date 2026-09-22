"""Load .env and Vertex/ADK defaults before any agent or runner is constructed."""

from __future__ import annotations

import logging
import os
import warnings

from dotenv import load_dotenv

load_dotenv()

_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
if _PROJECT and not os.environ.get("GOOGLE_CLOUD_QUOTA_PROJECT"):
    os.environ["GOOGLE_CLOUD_QUOTA_PROJECT"] = _PROJECT

# JSON-schema tool declarations can cause MALFORMED_FUNCTION_CALL on Vertex.
os.environ.setdefault("ADK_DISABLE_JSON_SCHEMA_FOR_FUNC_DECL", "1")

warnings.filterwarnings(
    "ignore",
    message=r"Your application has authenticated using end user credentials.*",
)


class _DropAfcWarning(logging.Filter):
    """Drop google-genai automatic function calling noise when tools are enabled."""

    def filter(self, record: logging.LogRecord) -> bool:
        return "automatic function calling" not in record.getMessage().lower()


logging.getLogger("google.genai.models").addFilter(_DropAfcWarning())
