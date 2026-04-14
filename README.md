# Cloud Doctor

> Structural guardrails for Claude Code. Hook-based in-moment reminders for production actions, architectural questions, and completion claims without evidence.

[🇷🇺 Читать на русском](README.ru.md)

**Why this exists:** Rules in CLAUDE.md / AGENTS.md are post-hoc appeals — Claude reads them at session start, then drifts away from them mid-session. This plugin injects reminders at the exact event where the pattern would repeat (`UserPromptSubmit` / `Stop`), not as text that needs to be re-read. See [references/philosophy.md](references/philosophy.md) for the full rationale with external citations.

**Status:** v0.1.0, log-only detection for the Stop hook (tunable). Cross-platform (Linux / macOS / Windows with Git Bash).

---

## What it does

**Production-keyword detector** (UserPromptSubmit). Triggers when the user's message contains production-operation language — defaults are bilingual (`deploy`, `migrate`, `publish to`, `push to production`, plus Russian equivalents `деплой`, `миграци`, `опублик`). On match, injects a five-point self-check block the assistant must fill with concrete tool output before acting. Extend the default list via `prod_keywords_add` in your project config.

**Architectural-question detector** (UserPromptSubmit). Triggers on advisory phrasings (`how should I...`, `what's the best approach`, `which pattern`, `посоветуй`, `как лучше`). On match, requires at least one tool call on real files (Read / Bash / Grep / Glob) before the assistant generates any recommendation. Addresses Pattern B from the philosophy doc — advisory questions tend to be answered from auto-loaded context rather than from fresh file reads.

**Fabrication detector** (Stop). Scans the assistant's last response when it tries to stop. Two sub-checks: (1) attribution fabrication — assistant claims the user has «code words» that the user never actually used in declarative form; (2) completion claims without evidence — assistant says «done», «deployed», «works» in a response that made no evidence-producing tool call (Read, Bash, Grep, Glob, WebFetch, MCP reads). Log-only in v0.1; flagged patterns are written to `$CLAUDE_PLUGIN_DATA/audit.log` (or `~/.claude/plugin-data/cloud-doctor/audit.log` as fallback).

**Session-start analyzer** (SessionStart). Once per session, reads the last seven days of audit log, produces a concise summary, writes a human-readable monitoring file, and injects a one-line status into the session's initial context. Makes accumulated audit visible without requiring manual file inspection.

---

## Installation

Inside Claude Code:

```
/plugin marketplace add alenazaharovaux/cloud-doctor
/plugin install cloud-doctor@cloud-doctor
/cloud-doctor:setup
```

The `setup` command creates `.claude/cloud-doctor.local.md` in your current project with sensible defaults. Hooks will use built-in defaults even without this file, but per-project customization requires it.

### Prerequisites

- Python 3 available as `python3` or `python` (plugin auto-detects)
- **On Windows:** Git for Windows (bundles Git Bash, required for the shell launcher)
- No additional Python packages required (stdlib only)

---

## Configuration

Edit `.claude/cloud-doctor.local.md` in your project:

| Field | Type | Default | Meaning |
|---|---|---|---|
| `enabled` | bool | `true` | Master switch. When `false`, all Cloud Doctor hooks skip. |
| `language` | string | `"en"` | Injected-message language: `"en"`, `"ru"`, or `"both"` |
| `prod_keywords_add` | list[str] | `[]` | Words added to the default prod-keyword list |
| `prod_keywords_replace` | list[str] | `[]` | If non-empty, fully replaces defaults |
| `architectural_enabled` | bool | `true` | Enable architectural-question detector |
| `fabrication_enabled` | bool | `true` | Enable Stop-hook fabrication detector |
| `claim_phrases_add` | list[str] | `[]` | Extra completion-claim phrases |
| `claim_phrases_replace` | list[str] | `[]` | If non-empty, fully replaces defaults |
| `scan_history` | bool | `true` | Let fabrication-detector read `~/.claude/history.jsonl` |
| `monitoring_path` | string | `""` | Override SessionStart summary file location |

Example:

```yaml
---
enabled: true
language: "both"
prod_keywords_add: ["kubectl apply", "terraform apply", "helm upgrade"]
architectural_enabled: true
fabrication_enabled: true
scan_history: false
monitoring_path: "~/notes/claude-audit.md"
---

# Notes (free-form, ignored by plugin)
Configured for infra project — added K8s/TF/Helm verbs to prod triggers.
Turned off history scan for privacy.
```

Changes take effect on the **next** hook invocation. No Claude Code restart required — the config file is read per event.

---

## Philosophy

Why does this need to be a hook instead of just another rule in CLAUDE.md? Short answer: rules in CLAUDE.md activate post-hoc, hooks activate in-moment. Long answer, with external citations (four GitHub issues on anthropics/claude-code, Andrej Karpathy's public comments, Huang et al. 2023 on LLM self-correction, Anthropic alignment-faking research), in [references/philosophy.md](references/philosophy.md).

---

## Troubleshooting

**Hooks silent — nothing happens on trigger words.** Run `claude --debug` and watch the output for hook registration messages. If hooks aren't registered, check that the plugin is enabled via `/plugin` menu. If hooks are registered but not firing, check that `python3` or `python` is in your `PATH`.

**Windows: `sh: command not found`.** The plugin's launcher (`hooks/run.sh`) needs `sh` available. On Windows this comes from Git Bash. Install [Git for Windows](https://git-scm.com/download/win) — Git Bash is bundled and adds `sh` to your PATH automatically.

**Configuration changes don't take effect.** Config is re-read per hook invocation, but you need to trigger a hook event to see the new behavior. Send a new user message with a trigger word. If still no effect, check that you saved the file and that YAML frontmatter is syntactically valid (starts and ends with `---` on their own lines).

**`/plugin update` says «already at latest version» but I see a new release on GitHub.** Known Claude Code bug — see [anthropics/claude-code issue #25244](https://github.com/anthropics/claude-code/issues/25244). The plugin manager doesn't `git pull` the marketplace clone before checking versions. Workaround:

```bash
cd ~/.claude/plugins/marketplaces/cloud-doctor && git pull
# then back in Claude Code:
/plugin update cloud-doctor@cloud-doctor
```

**Where are the logs?** Audit log: `$CLAUDE_PLUGIN_DATA/audit.log` if that env var is set by Claude Code, otherwise `~/.claude/plugin-data/cloud-doctor/audit.log`. Heartbeat log (proves hook ran even without flags): same directory, `heartbeat.log`. Monitoring summary: same directory, `monitoring.md`, unless you override `monitoring_path`.

**How do I turn it off without uninstalling?** Two options. (1) `/plugin disable cloud-doctor@cloud-doctor` — disables until you re-enable. (2) In `.claude/cloud-doctor.local.md`, set `enabled: false` — disables per-project. Per-project setting is preferred when you want the plugin on globally but off in a specific repo.

**False positives on fabrication-detector.** The v0.1 release is log-only, so false positives don't block work — they accumulate in the log. Review flagged phrases and adjust `claim_phrases_replace` to exclude ones that cause noise in your writing style. Report patterns of systematic false positives as an issue.

---

## Contributing

Issues and PRs welcome at [github.com/alenazaharovaux/cloud-doctor](https://github.com/alenazaharovaux/cloud-doctor). The most useful contributions for v0.2:

- Keyword list suggestions for additional languages
- False-positive reports from fabrication-detector with examples from your transcripts
- New detectors for patterns not yet covered (proposals via issue first)
- Test cases — `tests/test_completion_claims.py` currently covers 13 cases; more are welcome

---

## License

MIT — see [LICENSE](LICENSE).

---

## Credits

Author: Alena Zakharova ([github.com/alenazaharovaux](https://github.com/alenazaharovaux)).

Origin: project «Анализ Клода — апрель», April 2026 — a collection of concrete incidents where rule-following broke down mid-session, which led to the observation that CLAUDE.md rules activate post-hoc while hooks can activate in-moment.

Implementation co-authored by Claude Opus 4.6 with empirical verification at each step (see commit history).
