---
name: triage
description: Interactive triage of completion-claim flags — decide per phrase whether to block, ignore, or leave alone. Uses AskUserQuestion buttons inside the chat.
allowed-tools: ["Read", "Edit", "Write", "Bash", "AskUserQuestion"]
---

# Claude Doctor Triage

Interactive workflow to process accumulated flags from the audit log. For each flagged phrase the user decides: **Block** (future occurrences trigger Stop-hook), **Ignore** (future occurrences bypass detection), or **Skip** (leave for later).

You (Claude) are the one executing this command. Follow the steps exactly — do not improvise.

## Step 1: Read the per-project config

Read `${CLAUDE_PROJECT_DIR}/.claude/claude-doctor.local.md` using the Read tool.

- If the file does not exist: copy `${CLAUDE_PLUGIN_ROOT}/templates/claude-doctor.local.md.example` to that path first, then re-read.
- Extract the YAML frontmatter values: `last_triage_timestamp`, `claim_phrases_blocking`, `claim_phrases_ignore`.
- If the frontmatter is malformed, tell the user, show what you read, and stop. Do not guess.

Keep the parsed lists in memory for the rest of the session. You will mutate them and write back at the end.

## Step 2: Parse the audit log

Run the parser from `${CLAUDE_PLUGIN_ROOT}/scripts/review.py` — but you need raw entries, not the markdown output. Do one of:

**Option A (preferred):** invoke the parser directly via Bash:

```
python3 -c "import sys; sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/hooks'); sys.path.insert(0, '${CLAUDE_PLUGIN_ROOT}/scripts'); from review import parse_log; from lib.paths import log_file; import json; print(json.dumps(parse_log(log_file()), ensure_ascii=False))"
```

Cross-platform variant (use if `python3` is not on PATH):

```
sh -c 'command -v python3 >/dev/null 2>&1 && PY=python3 || PY=python; "$PY" -c "import sys; sys.path.insert(0, \"${CLAUDE_PLUGIN_ROOT}/hooks\"); sys.path.insert(0, \"${CLAUDE_PLUGIN_ROOT}/scripts\"); from review import parse_log; from lib.paths import log_file; import json; print(json.dumps(parse_log(log_file()), ensure_ascii=False))"'
```

Parse the JSON output. Each entry has fields `ts`, `session`, `type` (`cc` or `v1`), `phrase`, `context`, `tools`.

**Option B (fallback):** if the Bash invocation fails for any reason, Read the log file directly at `~/.claude/plugin-data/claude-doctor/audit.log` and parse it with a short script. But Option A is canonical — report any failure to the user before falling back.

## Step 3: Filter to unprocessed CC flags

Keep only entries where:

- `type == "cc"` (v0.2 does not triage attribution flags — that's deferred to v0.3)
- `ts > last_triage_timestamp` (ISO-8601 string comparison is correct here because both are `datetime.isoformat()` output)
- `phrase` is not already in `claim_phrases_blocking` (don't re-ask about things already blocked)
- `phrase` is not already in `claim_phrases_ignore` (don't re-ask about things already ignored)

If the filtered list is empty, tell the user:

> Nothing new to triage since `<last_triage_timestamp>`. Your blocking list has N entries, ignore list has M entries.

Do not launch AskUserQuestion. Exit the command.

If `last_triage_timestamp` is empty (first run ever), use the empty string — it compares less than any real timestamp, so all CC entries stay.

## Step 4: Group by phrase, show top phrases first

Count occurrences per phrase. Sort descending by count.

- If the total number of unprocessed flags is ≤ 20: skip straight to per-flag review (Step 6).
- If total is 21–200: take the top 3 phrases by frequency, handle them as bulk (Step 5), then handle the rest per-flag.
- If total is > 200: take the top 10 phrases by frequency, handle them as bulk, and for the remainder show only a summary count — do not ask per-flag questions.

## Step 5: Per-phrase bulk decision

For each high-frequency phrase:

Use the `AskUserQuestion` tool with one question:

- **question:** `Phrase «<phrase>» flagged <N> times. What do you want to do?`
- **header:** `<phrase> (<N>×)`
- **multiSelect:** false
- **options:**
  - `label: "Block all"`, `description: "Future occurrences without evidence-tool will trigger the Stop hook and require correction."`
  - `label: "Ignore all"`, `description: "Future occurrences bypass flagging entirely. Best for phrases that legitimately appear in your writing."`
  - `label: "Review individually"`, `description: "Show each flag one by one with full context so you can decide per case."`
  - `label: "Skip"`, `description: "Leave all flags for this phrase for later."`

Process the answer:

- **Block all:** append the phrase (lowercased) to the in-memory `claim_phrases_blocking` list if not already present.
- **Ignore all:** append the phrase (lowercased) to `claim_phrases_ignore`.
- **Review individually:** run Step 6 for the occurrences of just this phrase.
- **Skip:** do nothing for this phrase, move to the next one.

After each decision update a local counter: blocked N phrases, ignored M phrases, skipped K, reviewed-individually R (with sub-counts).

## Step 6: Per-flag individual review

For each remaining flag, use `AskUserQuestion`:

- **question:** `Flag from <formatted-ts>, session <short-session>. Phrase «<phrase>» — what do you want to do?`
- **header:** `«<phrase>»`
- **multiSelect:** false
- **options:**
  - `label: "Block this phrase"`, `description: "Add «<phrase>» to blocking list. Future occurrences without evidence-tool trigger Stop hook."`
  - `label: "Ignore this phrase"`, `description: "Add «<phrase>» to ignore list. Future occurrences are not flagged."`
  - `label: "Skip"`, `description: "Leave this flag unresolved for later."`

Before asking, show the context and tools in the current message text (not as part of the question):

```
From <ts>, session <sid>:
  Context: <first 200 chars of context>
  Tools in response: <tools>
```

Process the answer the same way as Step 5. Idempotent — if the phrase is already in the target list, don't duplicate it.

## Step 7: Write the updated config back

After all questions are answered (or the user cancels mid-loop — see Step 9):

1. Read the current `.claude/claude-doctor.local.md` again (fresh, in case something changed).
2. Edit the frontmatter:
   - Update `claim_phrases_blocking:` with the new list, formatted as `["phrase1", "phrase2"]`. Quote phrases that contain commas or special characters.
   - Update `claim_phrases_ignore:` the same way.
   - Update `last_triage_timestamp:` to the ISO-8601 timestamp of the **last flag you actually processed** (either blocked, ignored, or individually reviewed — skipped flags do NOT advance the timestamp). If the user cancelled before processing anything, do not update the timestamp.
3. Write the file back via the Edit tool.

The timestamp rule comes from the plan's open question 2: using the last-processed timestamp means skipped flags come back on the next `/triage` run, which is the honest behavior.

## Step 8: Summary

After writing the config, print a summary to the user:

```
Triage complete.

Blocked: <N> phrases [<list>]
Ignored: <M> phrases [<list>]
Skipped: <K> flags
Reviewed individually: <R> flags (<blocked>/<ignored>/<skipped>)

Updated: .claude/claude-doctor.local.md
Next triage will show flags after <new_last_triage_timestamp>.
```

## Step 9: Edge cases

- **`.claude/claude-doctor.local.md` missing:** copy from template (see Step 1), then continue.
- **Audit log missing or empty:** tell the user there's nothing to triage and exit.
- **Zero unprocessed flags after filtering:** friendly message, exit without asking.
- **User cancels** (closes the prompt, sends a different message): stop asking more questions. Save whatever decisions were made so far. Timestamp = last processed flag's `ts` if any was processed, otherwise leave `last_triage_timestamp` unchanged.
- **Phrase already in blocking or ignore list:** don't ask again, silently skip.
- **Attribution flags (`type == "v1"`) in the log:** do not triage them. Mention in the summary: `N attribution flags present — not triaged in v0.2, use /claude-doctor:review to inspect.`
- **Malformed YAML in config:** stop and tell the user exactly what line looks wrong. Do not try to repair it silently.

## Step 10: Reminder to the user

At the very end, add:

> If this plugin flagged something that was a legitimate claim (false positive you'd rather ignore everywhere), open an issue at https://github.com/alenazaharovaux/claude-doctor/issues with the phrase and context — that's the feedback that drives future default-list tuning.
