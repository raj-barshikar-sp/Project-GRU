"""Landing → dashboard → chat routes used by Get started."""

from fastapi.testclient import TestClient

from ui.app import create_app


def test_get_started_opens_dashboard() -> None:
    client = TestClient(create_app())
    home = client.get("/")
    assert home.status_code == 200
    assert 'href="/dashboard"' in home.text

    dash = client.get("/dashboard")
    assert dash.status_code == 200
    assert "text/html" in dash.headers["content-type"]
    assert 'id="dashboard"' in dash.text
    assert "<h1>Pipeline</h1>" in dash.text
    assert "SailPoint · RevOps" in dash.text
    assert "AE workspace" not in dash.text
    assert "Your book" not in dash.text
    assert "<h2>Opportunities</h2>" in dash.text
    assert 'id="sidebar-artifacts"' not in dash.text
    assert 'href="/chat"' in dash.text
    assert 'href="/chat?view=library"' in dash.text
    assert "\n            Chat\n" in dash.text
    assert "\n            Artifacts\n" in dash.text
    assert "New chat" not in dash.text
    assert 'id="toggle-sidebar"' in dash.text
    assert "collapse-sidebar" not in dash.text
    assert "dash-connectors" not in dash.text
    assert ">Tasks<" in dash.text
    assert "Alerts" in dash.text
    assert "Slack" in dash.text
    assert "Artifacts from chat" not in dash.text
    assert "<select" in dash.text
    assert 'id="filter-sizes"' in dash.text
    assert "data-theme-toggle" in dash.text
    assert "mock" not in dash.text.lower()
    assert "dummy" not in dash.text.lower()

    chat = client.get("/chat")
    assert chat.status_code == 200
    assert 'id="workspace"' in chat.text
    assert 'id="composer"' in chat.text
    assert "What should Bob work on?" in chat.text
    assert 'id="filter-sizes"' in chat.text
    assert 'id="filter-stages"' in chat.text
    assert 'id="sidebar-artifacts"' not in chat.text
    assert 'id="open-library"' in chat.text
    assert 'id="library"' in chat.text
    assert 'id="sidebar-pinned"' in chat.text
    assert 'id="recents-dialog"' in chat.text
    assert 'id="selected-chips"' in chat.text
    assert 'id="toggle-sidebar"' in chat.text
    assert "collapse-sidebar" not in chat.text
    assert "New chat" in chat.text
    assert 'id="filter-windows"' in chat.text
    assert "data-theme-toggle" in chat.text
    assert "<select" in chat.text

    app_page = client.get("/app")
    assert app_page.status_code == 200
    assert 'id="dashboard"' in app_page.text
