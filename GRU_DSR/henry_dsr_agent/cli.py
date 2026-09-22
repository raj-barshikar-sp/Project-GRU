"""Command-line interface for Henry."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

from henry_dsr_agent.api.main import _dispatch, build_orchestrator

app = typer.Typer(help="Henry — your local-first digital sales representative copilot.")
console = Console()


def _render(value: Any) -> None:
    if isinstance(value, str):
        console.print(Markdown(value))
    elif isinstance(value, dict) and isinstance(value.get("markdown"), str):
        console.print(Markdown(value["markdown"]))
    else:
        console.print_json(json.dumps(value, default=str))


def _run(workflow: str, payload: dict[str, Any]) -> None:
    try:
        result = asyncio.run(_dispatch(build_orchestrator(), workflow, payload))
    except Exception as exc:
        console.print(f"[bold red]Henry could not complete that request:[/] {exc}")
        raise typer.Exit(1) from exc
    _render(result)


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Address to bind."),
    port: int = typer.Option(8000, min=1, max=65535, help="Port to bind."),
    reload: bool = typer.Option(False, help="Reload when source files change."),
) -> None:
    """Start the API and dashboard."""
    import uvicorn

    console.print(f"[bold purple]Henry is ready[/] at http://{host}:{port}")
    uvicorn.run("henry_dsr_agent.api.main:app", host=host, port=port, reload=reload)


@app.command()
def workflow(
    name: str = typer.Argument(
        help="territories, accounts, prospecting, discovery, outreach, deal-risk, or ask"
    ),
    message: str = typer.Option("", "--message", "-m", help="Instructions for Henry."),
    account: str | None = typer.Option(None, "--account", "-a", help="Account identifier."),
    action: str | None = typer.Option(None, help="Explicit DSR ask action identifier."),
    context: str = typer.Option("{}", help="Additional context as a JSON object."),
) -> None:
    """Run one sales workflow."""
    allowed = {
        "territories",
        "accounts",
        "prospecting",
        "discovery",
        "outreach",
        "deal-risk",
        "ask",
    }
    if name not in allowed:
        raise typer.BadParameter(f"name must be one of: {', '.join(sorted(allowed))}")
    try:
        parsed = json.loads(context)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter("context must be valid JSON") from exc
    if not isinstance(parsed, dict):
        raise typer.BadParameter("context must be a JSON object")
    _run(
        name,
        {
            "message": message,
            "action": action,
            "account_id": account,
            "context": parsed,
        },
    )


@app.command()
def chat(
    message: str | None = typer.Argument(
        None, help="A single question; omit for interactive mode."
    ),
    account: str | None = typer.Option(None, "--account", "-a", help="Account identifier."),
) -> None:
    """Chat with Henry once or in an interactive session."""
    if message:
        _run("chat", {"message": message, "account_id": account, "context": {}})
        return

    console.print(
        Panel.fit(
            "Ask about accounts, outreach, discovery, or deal risk.\nType [bold]exit[/] to finish.",
            title="🤿 Henry the DSR Minion",
            border_style="magenta",
        )
    )
    orchestrator = build_orchestrator()
    while True:
        prompt = Prompt.ask("[bold cyan]You[/]").strip()
        if prompt.lower() in {"exit", "quit", "/exit", "/quit"}:
            console.print("[purple]Henry:[/] See you on the next mission! 👋")
            return
        if not prompt:
            continue
        try:
            result = asyncio.run(
                _dispatch(
                    orchestrator,
                    "chat",
                    {"message": prompt, "account_id": account, "context": {}},
                )
            )
            console.print("[bold purple]Henry[/]")
            _render(result)
        except Exception as exc:
            console.print(f"[red]Could not respond:[/] {exc}")


if __name__ == "__main__":
    app()
