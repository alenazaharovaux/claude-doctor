# Changelog

All notable changes to Claude Doctor will be documented in this file.

## [0.2.2] — 2026-04-15

### Documentation
- Added a paragraph to the «Triaging flags interactively» section in both `README.md` and `README.ru.md` explaining when to pick **Review individually** over bulk (when the three sample contexts disagree) and how the per-flag loop exits as soon as you make a block/ignore decision.
- Updated the status line at the top of both READMEs from `v0.1.0, log-only detection` to reflect the actual v0.2.x behavior: log-only by default, with selective blocking available through `/triage`.
- Rewrote the «False positives on fabrication-detector» troubleshooting entry. It previously described the v0.1 workflow (edit `claim_phrases_replace` by hand) without mentioning that `/triage` now handles this through buttons. The new text points users to the correct workflow first.

## [0.2.1] — 2026-04-15

### Fixed
- `/claude-doctor:triage` now prints three real context samples per phrase before asking for a decision. Phrases alone (just a word and a count) did not give users enough signal to choose between block and ignore — the context around the flag is where the signal lives. Without it, every phrase looked like «maybe» and users ended up skipping everything.
- `PYTHONIOENCODING=utf-8` is now set in the triage command's bash invocations. Windows Python defaults to cp1252 for stdout, which crashes on Cyrillic or other non-ASCII phrases. The first real `/triage` run surfaced this — the parser succeeded but the formatted print failed with a `UnicodeEncodeError`.

### Changed
- `/claude-doctor:triage` no longer filters by `last_triage_timestamp`. The previous design advanced the timestamp on every processed flag, which had a side effect: skipped phrases were permanently excluded from the next run, because their own timestamps were now older than `last_triage_timestamp`. The user had no way to say «come back to this later» without losing the phrase. New behavior: filter is based only on `claim_phrases_blocking` and `claim_phrases_ignore`. Skipped phrases come back automatically in the next triage run. The `last_triage_timestamp` field remains in the config schema for backward compatibility but is no longer read.

### Migration
- If you ran `/claude-doctor:triage` on v0.2.0 and have entries in `last_triage_timestamp`: no action needed. The field is simply ignored now. Skipped phrases from your v0.2.0 run will reappear on the next triage.

## [0.2.0] — 2026-04-15

### Added
- `/claude-doctor:triage` slash command — interactive triage of accumulated flags through `AskUserQuestion` buttons inside the chat. For every phrase you decide: **Block** (future occurrences trigger the Stop hook and require correction), **Ignore** (future occurrences bypass detection entirely), or **Skip** (leave for later). Closes the remaining loop from v0.1.x: users can act on flags without editing config files by hand.
- New config fields in `.claude/claude-doctor.local.md`: `claim_phrases_blocking` (list of phrases that trigger `sys.exit(2)` when detected without evidence tool), `claim_phrases_ignore` (list of phrases excluded from flagging entirely), `last_triage_timestamp` (auto-managed, prevents re-asking about already-processed flags).
- Bulk operations in `/triage`: «Block all X» and «Ignore all X» buttons that resolve every occurrence of a phrase in one click. Critical for skewed flag distributions — the top few phrases typically account for most of the volume, so per-phrase bulk collapses hundreds of clicks into a handful.
- Hint at the bottom of `/claude-doctor:review` output pointing users to `/triage` or the manual-edit alternative.

### Changed
- `hooks/fabrication_detector.py` now reads `claim_phrases_blocking` and `claim_phrases_ignore` from config. Ignored phrases are filtered out before the log is written. If any surviving flagged phrase matches the blocking list, the hook exits with code 2 and writes a stderr message that Claude Code feeds back into the conversation as Stop-hook protocol output — Claude must then verify the claim or retract it.
- `.claude-plugin/plugin.json` — version bumped from `0.1.1` to `0.2.0`.

### Why this exists
v0.1.x was log-only. Users could inspect flags through `/claude-doctor:review`, but the only way to act on them was to open `.claude/claude-doctor.local.md` and edit YAML lists by hand — high friction, and the config schema had no fields for per-phrase block/ignore decisions anyway. v0.2 adds both the config schema and the interactive triage loop, so the feedback path becomes: see flag in review → run triage → click button → next occurrence either blocks or gets ignored. No restart, no file editing.

Attribution fabrication (the v1 check) is deliberately not part of `/triage` in this release — the decision surface is different (the phrase appears inside quoted attribution, so blocking is riskier). Attribution triage is scoped for v0.3.

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
