#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Claude Doctor — review tool.

Reads $CLAUDE_PLUGIN_DATA/audit.log (or fallback ~/.claude/plugin-data/claude-doctor/audit.log)
and prints last N flagged entries as readable markdown for the chat.

Usage:
    python scripts/review.py [N]
    N: number of most recent flags to show (default 20)

Output: markdown to stdout. Always exits 0.
"""
import datetime
import io
import os
import re
import sys
from pathlib import Path

# Make lib importable (review.py is in scripts/, lib is in hooks/lib/)
PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
if not PLUGIN_ROOT:
    PLUGIN_ROOT = str(Path(__file__).resolve().parent.parent)
HOOKS_DIR = str(Path(PLUGIN_ROOT) / "hooks")
if HOOKS_DIR not in sys.path:
    sys.path.insert(0, HOOKS_DIR)

from lib.paths import log_file  # noqa: E402


SESSION_HEADER_RE = re.compile(r"^=== (\S+) session=(\S+) ===$")
CC_FLAGGED_RE = re.compile(r"^\[CC\] FLAGGED: «(.+?)»")
CC_CONTEXT_RE = re.compile(r"^\[CC\] CONTEXT: (.*)$")
CC_TOOLS_RE = re.compile(r"^\[CC\] TOOLS_IN_RESPONSE: (.*)$")
V1_FLAGGED_RE = re.compile(r"^FLAGGED: «(.+?)»")
V1_CONTEXT_RE = re.compile(r"^CONTEXT: (.*)$")


def parse_log(path):
    """Return list of dicts with keys: ts, session, type, phrase, context, tools."""
    if not path.exists():
        return []

    entries = []
    cur_ts = None
    cur_session = None
    pending = None

    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")

                m = SESSION_HEADER_RE.match(line)
                if m:
                    cur_ts = m.group(1)
                    cur_session = m.group(2)
                    pending = None
                    continue

                if cur_ts is None:
                    continue

                m = CC_FLAGGED_RE.match(line)
                if m:
                    if pending:
                        entries.append(pending)
                    pending = {
                        "ts": cur_ts, "session": cur_session, "type": "cc",
                        "phrase": m.group(1), "context": "", "tools": "",
                    }
                    continue

                m = CC_CONTEXT_RE.match(line)
                if m and pending and pending["type"] == "cc":
                    pending["context"] = m.group(1)
                    continue

                m = CC_TOOLS_RE.match(line)
                if m and pending and pending["type"] == "cc":
                    pending["tools"] = m.group(1)
                    entries.append(pending)
                    pending = None
                    continue

                m = V1_FLAGGED_RE.match(line)
                if m:
                    if pending:
                        entries.append(pending)
                    pending = {
                        "ts": cur_ts, "session": cur_session, "type": "v1",
                        "phrase": m.group(1), "context": "", "tools": "",
                    }
                    continue

                m = V1_CONTEXT_RE.match(line)
                if m and pending and pending["type"] == "v1":
                    pending["context"] = m.group(1)
                    entries.append(pending)
                    pending = None
                    continue

        if pending:
            entries.append(pending)
    except (IOError, OSError):
        return []

    return entries


def format_ts(ts_iso):
    """Format ISO timestamp to «YYYY-MM-DD HH:MM»."""
    try:
        dt = datetime.datetime.fromisoformat(ts_iso)
        return dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return ts_iso


def short_session(sid):
    """Short session id (first 8 chars)."""
    if not sid:
        return "?"
    return sid[:8]


def format_markdown(entries, limit):
    """Format last N entries as markdown."""
    if not entries:
        return (
            "# Claude Doctor — Review\n\n"
            "_Audit log is empty._ This means either:\n"
            "- The Stop hook hasn't fired yet (you've never finished a Claude turn since install)\n"
            "- Nothing has been flagged so far (good!)\n"
            "- The plugin's data directory hasn't been created yet — check `~/.claude/plugin-data/claude-doctor/`\n"
        )

    recent = entries[-limit:][::-1]  # newest first
    cc = [e for e in recent if e["type"] == "cc"]
    v1 = [e for e in recent if e["type"] == "v1"]

    lines = [
        "# Claude Doctor — Review",
        "",
        f"Showing last **{len(recent)}** flags from audit log "
        f"(of {len(entries)} total).",
        "",
        f"- **Completion-claim flags (`[CC]`):** {len(cc)}",
        f"- **Attribution flags (v1):** {len(v1)}",
        "",
        "If a flag below was a legitimate claim/attribution (false positive), please open an issue at "
        "https://github.com/alenazaharovaux/claude-doctor/issues with the context line — this is the "
        "feedback that drives v0.2 tuning.",
        "",
    ]

    if cc:
        lines.append("---")
        lines.append("")
        lines.append("## Completion-claim flags")
        lines.append("")
        for i, e in enumerate(cc, 1):
            ctx = e["context"] or "_(no context)_"
            tools = e["tools"] or "_(none)_"
            lines.append(f"### {i}. [{format_ts(e['ts'])}] · session `{short_session(e['session'])}`")
            lines.append("")
            lines.append(f"**Phrase:** «{e['phrase']}»")
            lines.append("")
            lines.append(f"**Context:** {ctx}")
            lines.append("")
            lines.append(f"**Tools in response:** {tools}")
            lines.append("")

    if v1:
        lines.append("---")
        lines.append("")
        lines.append("## Attribution flags")
        lines.append("")
        for i, e in enumerate(v1, 1):
            ctx = e["context"] or "_(no context)_"
            lines.append(f"### {i}. [{format_ts(e['ts'])}] · session `{short_session(e['session'])}`")
            lines.append("")
            lines.append(f"**Word:** «{e['phrase']}»")
            lines.append("")
            lines.append(f"**Context:** {ctx}")
            lines.append("")

    return "\n".join(lines) + "\n"


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    limit = 20
    if len(sys.argv) > 1:
        try:
            limit = max(1, min(200, int(sys.argv[1])))
        except ValueError:
            pass

    entries = parse_log(log_file())
    print(format_markdown(entries, limit))
    sys.exit(0)


if __name__ == "__main__":
    main()
