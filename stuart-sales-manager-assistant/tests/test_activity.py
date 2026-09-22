"""Developer activity logger."""

from __future__ import annotations

import logging
from pathlib import Path

from agents.activity import configure_logging, log_activity, logger, preview


def test_preview_truncates_long_text() -> None:
    assert preview("hello") == "hello"
    assert preview("x" * 200).endswith("…")
    assert len(preview("x" * 200)) == 180


def test_log_activity_writes_event_and_fields(caplog) -> None:
    logger.propagate = True
    with caplog.at_level(logging.INFO, logger="stuart.activity"):
        log_activity("route.planner", specialists=["crm_intelligence_specialist"], query="east")
    assert "route.planner" in caplog.text
    assert "crm_intelligence_specialist" in caplog.text
    assert "east" in caplog.text


def test_configure_logging_writes_file(tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "stuart.log"
    monkeypatch.setenv("STUART_LOG_FILE", str(path))
    monkeypatch.setenv("STUART_LOG_LEVEL", "INFO")
    configure_logging(force=True)
    log_activity("session.create", session_id="abc")
    text = path.read_text(encoding="utf-8")
    assert "activity logger ready" in text
    assert "session.create" in text
    assert "abc" in text
