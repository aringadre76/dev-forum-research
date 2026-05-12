import pytest
from pydantic import ValidationError

from devforum_research.models import Evidence, IdeaBrief, validate_citations


def test_idea_brief_schema_accepts_required_fields_and_known_citations():
    idea = IdeaBrief(
        title="Trace-first AI build debugger",
        one_liner="Pinpoints flaky AI build failures with reproducible traces.",
        target_user="AI tooling teams running CI in monorepos",
        constraints=["monorepo", "cost caps"],
        pain_hypothesis=(
            "If teams can replay failing tool calls, flaky build triage time drops by 30%."
        ),
        evidence=[
            Evidence(
                source_type="github_issue",
                url="https://github.com/acme/tool/issues/7",
                why_it_matters="The issue shows repeated failed workarounds.",
                excerpt="still broken after splitting packages",
            )
        ],
        why_existing_tools_fail="GitHub Actions logs expose failures but not AI tool call state.",
        mvp_scope_1week="Collect failing command traces and attach them to CI job summaries.",
        mvp_scope_4weeks="Add replay, redaction, and repository-level pattern dashboards.",
        differentiation="Focused on AI tool execution traces, not generic CI observability.",
        risks=["Teams may avoid sending traces off-prem."],
        validation_plan=["Interview five maintainers with flaky AI build pipelines."],
    )

    validate_citations([idea], {"https://github.com/acme/tool/issues/7"})

    assert idea.evidence[0].source_type == "github_issue"


def test_idea_brief_schema_rejects_missing_required_fields():
    with pytest.raises(ValidationError):
        IdeaBrief(
            title="Incomplete",
            one_liner="Missing most required fields.",
            target_user="Founders",
            constraints=[],
            pain_hypothesis="Teams need this.",
            evidence=[],
            why_existing_tools_fail="Existing tools are generic.",
            mvp_scope_1week="Build demo.",
            mvp_scope_4weeks="Add dashboard.",
            differentiation="Sharper scope.",
            risks=[],
        )


def test_citation_validation_rejects_invented_urls():
    idea = IdeaBrief(
        title="Trace-first AI build debugger",
        one_liner="Pinpoints flaky AI build failures with reproducible traces.",
        target_user="AI tooling teams running CI in monorepos",
        constraints=["monorepo"],
        pain_hypothesis=(
            "If teams can replay failing tool calls, flaky build triage time drops by 30%."
        ),
        evidence=[
            Evidence(
                source_type="github_issue",
                url="https://github.com/acme/tool/issues/999",
                why_it_matters="The issue shows repeated failed workarounds.",
                excerpt="still broken after splitting packages",
            )
        ],
        why_existing_tools_fail="GitHub Actions logs expose failures but not AI tool call state.",
        mvp_scope_1week="Collect failing command traces and attach them to CI job summaries.",
        mvp_scope_4weeks="Add replay, redaction, and repository-level pattern dashboards.",
        differentiation="Focused on AI tool execution traces, not generic CI observability.",
        risks=["Teams may avoid sending traces off-prem."],
        validation_plan=["Interview five maintainers with flaky AI build pipelines."],
    )

    with pytest.raises(ValueError, match="not present in ingested documents"):
        validate_citations([idea], {"https://github.com/acme/tool/issues/7"})
