# Architecture Decisions

## ADR-001 — Per-phrase blocking via `claim_phrases_blocking` instead of a global toggle (2026-04-15)

**Decision.** v0.2 adds two list-typed config fields, `claim_phrases_blocking` and `claim_phrases_ignore`, populated through the interactive `/triage` command. The Stop hook checks each detected phrase against both lists; ignored phrases never reach the log, blocking phrases trigger `sys.exit(2)` with a stderr message.

**Rejected alternatives.**
- Global `fabrication_blocking: true/false` toggle — too coarse. Some phrases are real fabrication signals for one user and normal vocabulary for another.
- Severity-based ranking (HIGH/MEDIUM/LOW) — would require an upfront assessment from the user before they have data.
- ML-based ranking — overkill for v0.2; needs training data the project doesn't yet have.

**Why this design wins.** Each user trains the detector to their own writing style gradually. The blocking list ends up with the small number of phrases that genuinely predict trouble; the ignore list absorbs whatever overlaps with normal speech.

## ADR-002 — `AskUserQuestion` for interactive triage instead of TUI or copy-paste commands (2026-04-15)

**Decision.** `/claude-doctor:triage` runs an interactive loop using the built-in `AskUserQuestion` tool, which renders clickable buttons inside the chat. Per-phrase choices: Block all, Ignore all, Review individually, Skip.

**Rejected alternatives.**
- Copy-paste commands (`/claude-doctor:block "phrase"`) — six actions per flag, two focus zones.
- Standalone TUI script with arrow-key navigation — no way for a slash command to render a TUI inside Claude Code's chat.
- Bulk-only via manual `.local.md` editing — the v0.1.x state, the loop the redesign was meant to break.

**Why this design wins.** Buttons appear inline, no context switch. The tool is built into Claude Code; users need no extra install.

## ADR-003 — Drop `last_triage_timestamp` filtering in v0.2.1 (2026-04-15)

**Decision.** v0.2.0 advanced `last_triage_timestamp` on every processed flag and used it to filter what `/triage` showed on subsequent runs. This had a side effect: skipped phrases were excluded from the next run, because their timestamps became older than the cursor the moment skip was recorded. v0.2.1 removes the filter — only `claim_phrases_blocking` and `claim_phrases_ignore` act as filters. Skipped phrases come back every run until resolved. The `last_triage_timestamp` field stays in the config schema for backward compatibility but is not read.

**Rejected alternatives.**
- Per-flag signature list (`skipped_signatures: [hash1, hash2, ...]`) to track skipped flags individually — would bloat the config for users with hundreds of flags.
- Two timestamps (`last_seen` and `last_resolved`) — added complexity for a problem that disappears entirely if you stop using time as the cursor.

**Why this design wins.** The mental model becomes clean: a phrase is either resolved (in one of the two lists) or unresolved (everything else). Skip means «come back next run», which matches what users intuit. The cost is that triage shows the same skipped phrases until you make a decision, but that's the right pressure.

## ADR-004 — Personal config in `~/.claude/claude-doctor-personal.yaml`, separate from per-project `.local.md` (2026-04-15)

**Decision.** Alena's personal mirror in `~/.claude/` uses a single global YAML at `~/.claude/claude-doctor-personal.yaml` for blocking/ignore lists, separate from the plugin's per-project `.claude/claude-doctor.local.md` config.

**Rejected alternatives.**
- Hardcoded lists in `~/.claude/hooks/fabrication-detector.py` — every change requires editing Python.
- Reuse `.local.md` format globally in `~/.claude/` — inconsistent with its per-project nature.

**Why this design wins.** Personal hooks fire across every project Alena works in, so per-project config doesn't fit. A single global YAML is the simplest store with the right scope. The plugin and the personal mirror keep symmetric semantics: both have `claim_phrases_blocking` and `claim_phrases_ignore`, just at different scopes (project vs global).
