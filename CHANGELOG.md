# Changelog

All notable changes to Claude Doctor will be documented in this file.

## [0.1.1] — 2026-04-14

### Added
- `/claude-doctor:review [N]` slash command — pretty-prints the last N flags from the audit log directly in the chat, with full context lines, session IDs, and timestamps. No need to open the log file manually. Default N=20, max 200.
- `scripts/review.py` — standalone parser for the audit log, callable independently of the slash command.

### Why this exists
Closes a chicken-and-egg loop in v0.1.0: the `Stop` hook silently logged flagged completion claims, but users had no easy way to inspect them, which meant no false-positive feedback could come in to drive the decision about switching from log-only to blocking mode. With `/claude-doctor:review`, flags are visible without leaving Claude Code.

## [0.1.0] — 2026-04-14

### Added
- `UserPromptSubmit` hook: production-keyword detector (bilingual EN+RU defaults)
- `UserPromptSubmit` hook: architectural-question detector (bilingual EN+RU defaults)
- `Stop` hook: fabrication detector (attribution check + completion-claim check, log-only)
- `SessionStart` hook: 7-day audit aggregator with monitoring file output
- Per-project config via `.claude/claude-doctor.local.md` (YAML frontmatter, 10 fields)
- `/claude-doctor:setup` slash command for first-run config
- Cross-platform Python launcher (`hooks/run.sh`) — auto-detects `uv`, `python3`, `python` in order
- English README (`README.md`) and Russian README (`README.ru.md`)
- Philosophy document with external citations (4 GitHub issues, Karpathy, Huang et al. 2023)
- Unit tests for completion-claim detection (13 cases, all passing)

### Known limitations
- Completion-claim detector is log-only by design. Upgrade path to blocking documented in `references/philosophy.md`.
- `$CLAUDE_PLUGIN_DATA` env var is referenced in Anthropic docs but not confirmed in use by other plugins in the official marketplace as of release. Fallback to `~/.claude/plugin-data/claude-doctor/` handles unset case.
- No CI test runner configured yet.
- Windows requires Git Bash for the `sh` launcher (documented in README).
