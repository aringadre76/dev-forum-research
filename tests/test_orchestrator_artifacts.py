import json
from pathlib import Path

from devforum_research.config import load_config
from devforum_research.research.orchestrator import ResearchOrchestrator
from devforum_research.storage import SQLiteStore


def test_orchestrator_report_records_indexed_corpus_urls_and_stage_counts(tmp_path):
    config_path = Path("config/example.yaml")
    config = load_config(config_path)
    config.storage_path = str(tmp_path / "research.sqlite")
    config.research.output_dir = str(tmp_path / "runs")

    store = SQLiteStore(tmp_path / "research.sqlite")
    try:
        artifacts = ResearchOrchestrator(config, config_path, store).run(dry_run=True)
    finally:
        store.close()

    report = json.loads(artifacts.report_json.read_text())
    logs = [
        json.loads(line) for line in artifacts.logs_path.read_text().splitlines() if line.strip()
    ]

    assert "indexed_corpus_urls" in report
    assert "https://github.com/example/agent-build/issues/101" in report["indexed_corpus_urls"]
    assert any(log["stage"] == "index" and log.get("embedded_count") == 5 for log in logs)
    assert any(log["stage"] == "ingest" and log.get("github_issue_count") == 4 for log in logs)
    assert any(
        log["stage"] == "evidence_compilation" and log.get("retrieved_count", 0) >= 1
        for log in logs
    )
    assert any(log["stage"] == "idea_generation" and log["generated_count"] == 0 for log in logs)
