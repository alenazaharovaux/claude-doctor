---
name: review
description: Show recent Claude Doctor flags from audit log with full context (no need to open files)
---

# Claude Doctor Review

Steps:

1. Read the optional argument from the user. They may pass a number (e.g. `/claude-doctor:review 50`) to specify how many recent flags to show. Default is 20.

2. Run the review script via Bash:
   ```
   sh ${CLAUDE_PLUGIN_ROOT}/hooks/run.sh ../scripts/review [N]
   ```
   Replace `[N]` with the user-provided number, or omit if not provided.

   Note: `run.sh` is parameterized with hook script paths — for `scripts/review.py` use the explicit path:
   ```
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/review.py [N]
   ```
   or, for cross-platform Python detection:
   ```
   sh -c 'command -v python3 >/dev/null 2>&1 && exec python3 "$0" "$@" || exec python "$0" "$@"' ${CLAUDE_PLUGIN_ROOT}/scripts/review.py [N]
   ```

3. Show the script's stdout output to the user as a markdown response. The output is already formatted as markdown — no need to reformat or summarize.

4. If the script outputs «Audit log is empty», suggest to the user:
   - The Stop hook may not have fired yet (it runs only when Claude finishes a turn — happens after this current response)
   - To force a flag for testing: type a message and let Claude respond with «done» or «работает» without using any read tool, then run `/claude-doctor:review` again

5. After showing flags, remind the user that false positives can be reported as GitHub issues at https://github.com/alenazaharovaux/claude-doctor/issues with the context line copied. This feedback is what drives the decision to switch the detector from log-only to blocking mode.
