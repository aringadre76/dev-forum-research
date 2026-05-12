from __future__ import annotations

from pathlib import Path
from typing import Annotated, Literal

import typer

from devforum_research.config import load_config
from devforum_research.research.orchestrator import ResearchOrchestrator
from devforum_research.storage import SQLiteStore

app = typer.Typer(help="Run the DevForum Research ingestion and research pipeline.")


@app.command("run")
def run_report(
    config: Annotated[Path, typer.Option("--config", "-c")] = Path("config/example.yaml"),
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    embedding_mode: Annotated[
        Literal["local", "hosted"] | None,
        typer.Option("--embedding-mode"),
    ] = None,
) -> None:
    app_config = load_config(config)
    if embedding_mode is not None:
        app_config.embedding.mode = embedding_mode
    store = SQLiteStore(Path(app_config.storage_path))
    try:
        artifacts = ResearchOrchestrator(
            config=app_config,
            config_path=config,
            store=store,
        ).run(dry_run=dry_run)
    finally:
        store.close()
    typer.echo(f"Run complete: {artifacts.run_dir}")
    typer.echo(f"Markdown report: {artifacts.report_markdown}")
    typer.echo(f"JSON report: {artifacts.report_json}")


@app.command("latest")
def latest_report(
    runs_dir: Annotated[Path, typer.Option("--runs-dir")] = Path("runs"),
) -> None:
    run_dirs = sorted([path for path in runs_dir.glob("*") if path.is_dir()])
    if not run_dirs:
        raise typer.BadParameter(f"No runs found under {runs_dir}")
    latest = run_dirs[-1] / "report.md"
    typer.echo(latest.read_text())


if __name__ == "__main__":
    app()
