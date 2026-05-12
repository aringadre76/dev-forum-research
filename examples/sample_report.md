# DevForum Research Report 20260512T224911000000Z

Generated at: 2026-05-12T22:49:11+00:00
Dry run: true
Documents indexed: 5

## Themes

### 1. cache invalidation

Gap score: 12.0
Signals: 2 unresolved high-reply threads, 2 repeated phrase hits, 2 workaround-language hits

- [AI codegen cache invalidation is still broken in monorepos](https://github.com/example/agent-build/issues/101) (github_issue): The workaround is hacky. Cache invalidation fails whenever generated packages move between workspaces, and we gave up on incremental builds.
- [Cache invalidation workaround breaks generated client builds](https://github.com/example/agent-build/issues/118) (github_issue): Still broken after pinning versions. The manual step works locally but fails again in CI on large workspaces.

### 2. token caps

Gap score: 12.0
Signals: 2 unresolved high-reply threads, 2 repeated phrase hits, 2 workaround-language hits

- [Evaluation runner costs spike without token caps](https://github.com/example/eval-runner/issues/44) (github_issue): We need cost caps per branch. The current workaround is a manual spreadsheet and skipped nightly evals.
- [Token caps for branch evals](https://github.com/example/eval-runner/issues/47) (github_issue): Branch evals need token caps and alerts. Teams are stuck disabling coverage because budgets are still broken.

## Idea briefs

No IdeaBrief objects were generated because LLM mode is disabled. Set OPENAI_API_KEY, optionally OPENAI_BASE_URL and OPENAI_MODEL, then rerun without --dry-run.

## Known limitations

- SQLite hashed embeddings are deterministic and local, but less semantic than hosted embeddings.
- RSS entries do not expose accepted answers, so resolution state is unknown.
- Gap scores are heuristics intended to prioritize review, not prove market demand.
