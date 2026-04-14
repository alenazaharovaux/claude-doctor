#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SessionStart hook: aggregate last 7 days of fabrication-detector logs,
write monitoring summary, inject short status to Claude's context.
"""
import datetime
import io
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

from pathlib import Path as _Path
PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
if PLUGIN_ROOT:
    _hooks_dir = str(_Path(PLUGIN_ROOT) / "hooks")
    if _hooks_dir not in sys.path:
        sys.path.insert(0, _hooks_dir)

from lib.config import load as load_config  # noqa: E402
from lib.paths import (  # noqa: E402
    config_file, log_file, monitoring_file,
)


WINDOW_DAYS = 7


def _parse_log(path):
    """Yield dicts: {ts, session, type (flag|cc), phrase, context}."""
    if not path.exists():
        return
    cutoff = datetime.datetime.now() - datetime.timedelta(days=WINDOW_DAYS)

    cur_ts = None
    cur_session = None
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.rstrip("\n")
                m = re.match(r"^=== (\S+) session=(\S+) ===$", line)
                if m:
                    try:
                        cur_ts = datetime.datetime.fromisoformat(m.group(1))
                    except ValueError:
                        cur_ts = None
                    cur_session = m.group(2)
                    continue
                if cur_ts is None or cur_ts < cutoff:
                    continue
                mcc = re.match(r"^\[CC\] FLAGGED: «([^»]+)».*", line)
                if mcc:
                    yield {
                        "ts": cur_ts, "session": cur_session,
                        "type": "cc", "phrase": mcc.group(1), "context": "",
                    }
                    continue
                mfl = re.match(r"^FLAGGED: «([^»]+)»", line)
                if mfl:
                    yield {
                        "ts": cur_ts, "session": cur_session,
                        "type": "flag", "phrase": mfl.group(1), "context": "",
                    }
    except (IOError, OSError):
        return


def _build_summary(entries, lang):
    if not entries:
        if lang == "ru":
            return "Cloud Doctor: за 7 дней 0 срабатываний. Хорошо или хуки выключены."
        return "Cloud Doctor: 0 flags in last 7 days. Good or hooks disabled."
    total = len(entries)
    sessions = len({e["session"] for e in entries})
    phrases = Counter(e["phrase"] for e in entries).most_common(5)
    top = ", ".join(f"{p}({c})" for p, c in phrases)
    if lang == "ru":
        return f"Cloud Doctor — 7 дней: {total} flagов в {sessions} сессиях. Топ: {top}."
    return f"Cloud Doctor — 7d: {total} flags across {sessions} sessions. Top: {top}."


def _build_monitoring_md(entries, lang):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    if lang == "ru":
        header = "# Мониторинг Cloud Doctor\n\n"
        header += f"> Обновлено: {ts}  |  Окно: последние {WINDOW_DAYS} дней\n\n"
        no_flags = "_За окно срабатываний нет._\n"
        total_label = "Всего срабатываний"
        sessions_label = "Уникальных сессий"
        top_header = "## Топ фраз"
    else:
        header = "# Cloud Doctor Monitoring\n\n"
        header += f"> Updated: {ts}  |  Window: last {WINDOW_DAYS} days\n\n"
        no_flags = "_No flags in window._\n"
        total_label = "Total flags"
        sessions_label = "Unique sessions"
        top_header = "## Top phrases"

    if not entries:
        return header + no_flags

    counter = Counter(e["phrase"] for e in entries)
    sessions = len({e["session"] for e in entries})
    lines = [
        header,
        f"**{total_label}:** {len(entries)}  ",
        f"**{sessions_label}:** {sessions}",
        "",
        top_header,
        "",
    ]
    for phrase, n in counter.most_common(20):
        lines.append(f"- `{phrase}` — {n}")

    return "\n".join(lines) + "\n"


def main():
    sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8")
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        data = {}

    cfg = load_config(config_file())
    if not cfg["enabled"]:
        sys.exit(0)

    entries = list(_parse_log(log_file()))
    summary_text = _build_summary(entries, cfg["language"])
    md = _build_monitoring_md(entries, cfg["language"])

    mon_path = monitoring_file(cfg["monitoring_path"])
    try:
        mon_path.parent.mkdir(parents=True, exist_ok=True)
        mon_path.write_text(md, encoding="utf-8")
    except (IOError, OSError):
        pass

    print(f"📊 {summary_text}  (details: {mon_path})")
    sys.exit(0)


if __name__ == "__main__":
    main()
