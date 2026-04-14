---
name: triage
description: Interactive triage of completion-claim flags — decide per phrase whether to block, ignore, or leave alone. Uses AskUserQuestion buttons inside the chat.
allowed-tools: ["Read", "Edit", "Write", "Bash", "AskUserQuestion"]
---

# Claude Doctor Triage

Interactive workflow to process accumulated flags from the audit log. For each phrase the user decides: **Block** (future occurrences trigger Stop-hook), **Ignore** (future occurrences bypass detection), or **Skip** (come back next time).

You (Claude) execute this command. Follow the steps exactly.

## Step 1: Read the per-project config

Read `${CLAUDE_PROJECT_DIR}/.claude/claude-doctor.local.md` using the Read tool.

- If the file does not exist: copy `${CLAUDE_PLUGIN_ROOT}/templates/claude-doctor.local.md.example` to that path first, then re-read.
- Extract the YAML frontmatter values: `claim_phrases_blocking`, `claim_phrases_ignore`.
- `last_triage_timestamp` is **legacy in v0.2.1** — kept in the config schema for backward compatibility, but no longer used for filtering. Skipped phrases must come back in the next triage run; tying that to a timestamp caused them to disappear forever, which is wrong.
- If the frontmatter is malformed, tell the user, show what you read, and stop. Do not guess.

## Step 2: Parse the audit log

Invoke the parser via Bash. **Always set `PYTHONIOENCODING=utf-8`** — without it, Windows Python defaults to cp1252 stdout and crashes on non-ASCII phrases.

Preferred form:

```
PYTHONIOENCODING=utf-8 python3 -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/hooks'); sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts'); from review import parse_log; from lib.paths import log_file; import json; print(json.dumps(parse_log(log_file()), ensure_ascii=False))"
```

Cross-platform variant (`python3` fallback to `python`):

```
sh -c 'command -v python3 >/dev/null 2>&1 && PY=python3 || PY=python; PYTHONIOENCODING=utf-8 "$PY" -c "import sys; sys.path.insert(0, \"${CLAUDE_PLUGIN_ROOT}/hooks\"); sys.path.insert(0, \"${CLAUDE_PLUGIN_ROOT}/scripts\"); from review import parse_log; from lib.paths import log_file; import json; print(json.dumps(parse_log(log_file()), ensure_ascii=False))"'
```

Parse the JSON. Each entry has fields `ts`, `session`, `type` (`cc` or `v1`), `phrase`, `context`, `tools`.

## Step 3: Filter to actionable CC flags

Keep only entries where:

- `type == "cc"` (attribution v1 is out of scope in v0.2 — targeted for v0.3)
- `phrase` is not already in `claim_phrases_blocking`
- `phrase` is not already in `claim_phrases_ignore`

**Do not filter by `last_triage_timestamp`.** It's a legacy field. Skipped phrases are supposed to come back on the next triage run, so filtering them out by timestamp breaks the intent.

If the filtered list is empty, tell the user:

> All CC flags already resolved. Blocking list has N entries, ignore list has M entries.

Do not launch AskUserQuestion. Exit.

## Step 4: Group by phrase, decide bulk threshold

Count occurrences per phrase. Sort descending by count.

- Total ≤ 20 flags: skip straight to per-flag review (Step 6).
- Total 21–200: top 3 phrases get bulk treatment (Step 5), the rest go per-flag.
- Total > 200: top 10 phrases bulk, remainder gets a summary count only — do not ask per-flag.

## Step 5: Per-phrase bulk decision — with context samples

**Before each AskUserQuestion, print three real context samples for the phrase from the log.** Without them, users can't make an informed decision — «phrase X, N times» is not enough signal.

Sample selection: evenly spaced in time (first, middle, last occurrence of the phrase), so the user sees variety rather than three adjacent flags.

Format before the question:

```
Phrase «<phrase>» — N occurrences. Sample contexts:

1. [<ts>, session <sid>]
   "<first 200 chars of context>"
   Tools: <tools>

2. [<ts>, session <sid>]
   "<first 200 chars of context>"
   Tools: <tools>

3. [<ts>, session <sid>]
   "<first 200 chars of context>"
   Tools: <tools>
```

After printing samples — `AskUserQuestion`:

- **question:** `Phrase «<phrase>» — <N>×. What do you want to do?`
- **header:** `<phrase> (<N>×)`
- **multiSelect:** false
- **options:**
  - `label: "Ignore all"`, `description: "Drop this phrase from detection entirely. Pick this for words that are part of your normal vocabulary with no fabrication signal."`
  - `label: "Block all"`, `description: "Future occurrences without evidence-tool trigger Stop-hook exit 2. Pick this for phrases that usually mean unverified completion claims."`
  - `label: "Review individually"`, `description: "Expand into a per-flag loop with the full context of each occurrence."`
  - `label: "Skip"`, `description: "Leave the phrase unresolved — it will come back in the next /triage run."`

**Efficiency:** AskUserQuestion supports 1–4 questions per call. You can batch up to 4 phrases in one call. Always print context samples for all batched phrases **before** the AskUserQuestion call.

## Step 6: Per-flag individual review

For each remaining flag (or those selected via "Review individually"):

Before each AskUserQuestion, print the full context:

```
From <ts>, session <sid>:
  Context: <first 200 chars>
  Tools in response: <tools>
```

Then AskUserQuestion:

- **question:** `Flag from <formatted-ts>. Phrase «<phrase>» — what do you want to do?`
- **header:** `«<phrase>»`
- **multiSelect:** false
- **options:**
  - `label: "Ignore this phrase"`, `description: "Add to claim_phrases_ignore — all occurrences of this phrase stop being flagged."`
  - `label: "Block this phrase"`, `description: "Add to claim_phrases_blocking — future occurrences trigger Stop hook."`
  - `label: "Skip"`, `description: "Leave unresolved, comes back next run."`

Idempotent — if the phrase is already in the target list, don't duplicate.

## Step 7: Write the updated config back

After all questions are answered:

1. Read `.claude/claude-doctor.local.md` again.
2. Edit frontmatter:
   - `claim_phrases_blocking:` — updated list, `["phrase1", "phrase2"]` format.
   - `claim_phrases_ignore:` — same.
   - `last_triage_timestamp:` — **don't touch it**, leave whatever's there (legacy field).
3. Write via Edit tool.

## Step 8: Summary

Print to the user:

```
Triage complete.

Blocked: <N> phrases [<list>]
Ignored: <M> phrases [<list>]
Skipped: <K> phrases (come back next run)

Updated: .claude/claude-doctor.local.md
```

## Step 9: Edge cases

- **`.claude/claude-doctor.local.md` missing:** copy from template (Step 1), then continue.
- **Audit log missing or empty:** tell the user, exit.
- **Zero flags after filtering:** friendly message, exit without asking.
- **User cancels:** save whatever decisions were made so far. No timestamp to update.
- **Phrase already in blocking or ignore:** silent skip, don't ask again.
- **v1 attribution flags (`type == "v1"`):** do not triage. In summary: `N attribution flags present — not triaged in v0.2, use /claude-doctor:review to inspect.`
- **Malformed YAML:** stop, show the suspicious line. Do not try to auto-repair.

## Step 10: Reminder

> If the plugin flagged something that was a legitimate claim (false positive you'd rather ignore everywhere), open an issue at https://github.com/alenazaharovaux/claude-doctor/issues with the phrase and context — that's the feedback that drives default-list tuning.
