"""Turning agent output into files people can open."""

from .artifact import save_artifact, save_email_cadence_csv, save_markdown
from .deck import render_deck, template_path

__all__ = [
    "render_deck",
    "template_path",
    "save_artifact",
    "save_email_cadence_csv",
    "save_markdown",
]
