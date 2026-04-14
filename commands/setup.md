---
name: setup
description: Create Cloud Doctor per-project config from template
---

# Cloud Doctor Setup

Steps:

1. Check if `.claude/cloud-doctor.local.md` exists in the current project (use `Read` tool or `ls`). If yes, tell the user it's already configured and offer to show current settings with a `Read` tool call.

2. If not, read the template from `${CLAUDE_PLUGIN_ROOT}/templates/cloud-doctor.local.md.example`.

3. Create `.claude/` directory in project if missing (`mkdir -p .claude`).

4. Copy the template to `.claude/cloud-doctor.local.md` using the `Write` tool.

5. Tell the user:
   - File created at `.claude/cloud-doctor.local.md`
   - Add `.claude/*.local.md` to `.gitignore` (don't commit personal config)
   - Hooks already use defaults; edit the file to customize (no restart needed)
   - Key switches: `enabled`, `language`, `prod_keywords_add`

6. Remind: if hooks aren't firing, run `claude --debug` once to see hook registration. On Windows, ensure Git Bash is installed (bundled with Git for Windows).
