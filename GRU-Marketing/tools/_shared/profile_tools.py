"""Tool that exposes the current user ("me") to the agents.

Use this whenever a request talks in the first person -- "my accounts", "my
region", "campaigns I own" -- or needs a default campaign owner. It resolves to
Omkar Patil, Senior Marketing Manager, from ``dummy_data/me.json``.
"""

from __future__ import annotations

from mktg_core.profile import current_user


def get_current_user() -> str:
    """Return the current user (you): name, title, region and email.

    Call this whenever the request uses "me", "my" or "I", or when a tool needs
    a campaign owner and none was named. Default the campaign owner email and
    the working region to this user unless the request explicitly names someone
    else or another region.

    Returns:
        A short profile of the current user.
    """
    me = current_user()
    return (
        "Current user (default owner / region for first-person requests):\n"
        f"- Name: {me['full_name']}\n"
        f"- Title: {me['title']}\n"
        f"- Email: {me['email']}\n"
        f"- Region: {me['region']}\n"
        f"- Team: {me['team']}"
    )
