#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stop hook: detect fabrication patterns in assistant's last response.

Part of Claude Doctor plugin. Logs flagged patterns to $CLAUDE_PLUGIN_DATA/audit.log
(or ~/.claude/plugin-data/claude-doctor/audit.log as fallback). Log-only (exit 0).

Two detectors:
- v1: attribution fabrication — assistant claims user has «code words»
      that don't actually appear in user's messages (or only in questioning context).
- v2: completion-claim without evidence — assistant says «done/works/deployed»
      without any evidence-tool call (Read/Bash/Grep/...) in same response.

Both log-only. Upgrade to blocking later once FP rate is measured.
"""
import datetime
import io
import json
import os
import re
import sys
from pathlib import Path

from pathlib import Path as _Path
PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
if PLUGIN_ROOT:
    _hooks_dir = str(_Path(PLUGIN_ROOT) / "hooks")
    if _hooks_dir not in sys.path:
        sys.path.insert(0, _hooks_dir)

from lib.config import load as load_config, is_enabled  # noqa: E402
from lib.paths import (  # noqa: E402
    config_file, log_file, heartbeat_file, history_jsonl, plugin_root,
)


def _load_claim_phrases(cfg):
    """Load default phrases from templates, merge with config additions/replacements."""
    if cfg["claim_phrases_replace"]:
        return [p.lower() for p in cfg["claim_phrases_replace"] if p]

    defaults_path = plugin_root() / "templates" / "claim_phrases.default.txt"
    phrases = []
    if defaults_path.exists():
        try:
            with open(defaults_path, "r", encoding="utf-8") as f:
                for line in f:
                    s = line.strip()
                    if s and not s.startswith("#"):
                        phrases.append(s.lower())
        except (IOError, OSError):
            pass

    for extra in cfg["claim_phrases_add"]:
        if extra:
            phrases.append(extra.lower())

    return phrases


CLAIM_NEGATIONS = [
    "не ", "нет ", "если ", "?", "будет ", "станет ",
    "не могу", "не получается",
    "not ", "won't", "can't", "doesn't", "isn't",
]


EVIDENCE_TOOLS = {
    "Read", "Bash", "Grep", "Glob",
    "WebFetch", "WebSearch",
    "mcp__supabase__execute_sql", "mcp__supabase__list_tables",
    "mcp__supabase__get_logs",
    "mcp__exa__web_fetch_exa", "mcp__exa__web_search_exa",
}


def find_completion_claims(text, phrases):
    """Find completion-claim phrases in text. Returns [(phrase, sentence), ...]."""
    if not phrases:
        return []

    stripped = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    stripped = re.sub(r"`[^`\n]+`", "", stripped)
    stripped = "\n".join(
        line for line in stripped.split("\n") if not line.lstrip().startswith(">")
    )

    sentences = re.split(r"(?<=[.!?\n])", stripped)
    results = []
    for sent in sentences:
        s = sent.strip()
        if not s:
            continue
        s_lower = s.lower()
        if any(neg in s_lower for neg in CLAIM_NEGATIONS):
            continue
        for phrase in phrases:
            if phrase in s_lower:
                results.append((phrase, s[:200]))
                break
    return results


def has_evidence(tool_names):
    if not tool_names:
        return False
    return any(t in EVIDENCE_TOOLS for t in tool_names)


def extract_response_blocks(transcript_path):
    """Walk transcript backward, collect text + tool names from last assistant turn."""
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except (IOError, OSError):
        return "", []

    text_blocks = []
    tool_names = []
    for line in reversed(lines):
        try:
            d = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        msg = d.get("message", {})
        role = msg.get("role")
        if role == "user":
            break
        if role == "assistant":
            content = msg.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    btype = block.get("type")
                    if btype == "text":
                        text_blocks.append(block.get("text", ""))
                    elif btype == "tool_use":
                        name = block.get("name", "")
                        if name:
                            tool_names.append(name)

    return "\n".join(reversed(text_blocks)), list(reversed(tool_names))


QUESTIONING_MARKERS = [
    "?", "what is", "what's", "what does", "what do you mean by",
    "never said", "didn't say", "didn't mean",
    "откуда", "что значит", "что такое", "что это", "что за",
    "не понимаю", "не говорила", "не произносила", "впервые слышу",
]


def main():
    sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8")
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    transcript_path = data.get("transcript_path")
    stop_hook_active = data.get("stop_hook_active", False)

    cfg = load_config(config_file())
    if not is_enabled(cfg, "fabrication_enabled"):
        sys.exit(0)

    # Heartbeat (proves hook ran even without flags). Rotate at 1 MB.
    try:
        hb = heartbeat_file()
        if hb.exists() and hb.stat().st_size > 1_000_000:
            backup = hb.with_suffix(".log.1")
            if backup.exists():
                backup.unlink()
            hb.rename(backup)
        with open(heartbeat_file(), "a", encoding="utf-8") as hf:
            hf.write(
                f"{datetime.datetime.now().isoformat()} "
                f"session={data.get('session_id', 'unknown')} "
                f"stop_hook_active={stop_hook_active}\n"
            )
    except (IOError, OSError):
        pass

    if stop_hook_active or not transcript_path or not Path(transcript_path).exists():
        sys.exit(0)

    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except (IOError, OSError):
        sys.exit(0)

    # === v1: attribution fabrication check ===
    my_response_blocks = []
    for line in reversed(lines):
        try:
            d = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        msg = d.get("message", {})
        role = msg.get("role")
        if role == "user":
            break
        if role == "assistant":
            content = msg.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        my_response_blocks.append(block.get("text", ""))

    my_response = "\n".join(reversed(my_response_blocks))

    stripped = re.sub(r"```.*?```", "", my_response, flags=re.DOTALL)
    stripped = re.sub(r"`[^`\n]+`", "", stripped)

    ATTR_RU = re.compile(
        r"[Кк]одов(?:ое|ые)\s+слов(?:о|а)[:\s]*"
        r"[«\"\'][^»\"\'\n]{1,50}[»\"\']"
        r"(?:\s*(?:и|/|,)\s*[«\"\'][^»\"\'\n]{1,50}[»\"\'])*",
        re.IGNORECASE,
    )
    ATTR_EN = re.compile(
        r"(?:code\s+word|code\s+phrase|her\s+term|his\s+term|your\s+term)s?[:\s]*"
        r"[«\"\'][^»\"\'\n]{1,50}[»\"\']"
        r"(?:\s*(?:and|/|,)\s*[«\"\'][^»\"\'\n]{1,50}[»\"\'])*",
        re.IGNORECASE,
    )
    QUOTED = re.compile(r"[«\"\']([^»\"\'\n]{1,50})[»\"\']")

    candidates = []
    for pat in (ATTR_RU, ATTR_EN):
        for m in pat.finditer(stripped):
            ctx_start = max(0, m.start() - 100)
            ctx_end = min(len(stripped), m.end() + 200)
            context = stripped[ctx_start:ctx_end]
            for qm in QUOTED.finditer(m.group(0)):
                word = qm.group(1).strip()
                if word and 1 < len(word) < 50:
                    candidates.append((word, context))

    # Gather user sentences
    user_sentences = []
    if cfg["scan_history"]:
        hp = history_jsonl()
        if hp.exists():
            try:
                with open(hp, "r", encoding="utf-8") as f:
                    for hl in f:
                        try:
                            hd = json.loads(hl)
                        except (json.JSONDecodeError, ValueError):
                            continue
                        display = hd.get("display", "")
                        if display:
                            for s in re.split(r"(?<=[.!?\n])", display):
                                s = s.strip()
                                if s:
                                    user_sentences.append(s)
            except (IOError, OSError):
                pass

    for line in lines:
        try:
            d = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        msg = d.get("message", {})
        if msg.get("role") == "user":
            content = msg.get("content", [])
            text = ""
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text += block.get("text", "") + " "
            elif isinstance(content, str):
                text = content
            if text.strip():
                for s in re.split(r"(?<=[.!?\n])", text):
                    s = s.strip()
                    if s:
                        user_sentences.append(s)

    def has_declaring_use(word, sentences):
        wp = re.compile(r"\b" + re.escape(word) + r"\b", re.IGNORECASE)
        for s in sentences:
            if wp.search(s):
                sl = s.lower()
                if any(m in sl for m in QUESTIONING_MARKERS):
                    continue
                return True
        return False

    flagged = []
    for word, context in candidates:
        if not has_declaring_use(word, user_sentences):
            flagged.append((word, context))

    # === v2: completion-claim check ===
    response_text, response_tools = extract_response_blocks(transcript_path)
    phrases = _load_claim_phrases(cfg)
    cc_candidates = find_completion_claims(response_text, phrases)
    cc_flagged = cc_candidates if cc_candidates and not has_evidence(response_tools) else []

    if not flagged and not cc_flagged:
        sys.exit(0)

    try:
        with open(log_file(), "a", encoding="utf-8") as f:
            ts = datetime.datetime.now().isoformat()
            sid = data.get("session_id", "unknown")
            f.write(f"\n=== {ts} session={sid} ===\n")
            for word, context in flagged:
                f.write(f"FLAGGED: «{word}»\n")
                f.write(f"CONTEXT: {context.strip().replace(chr(10), ' ')[:300]}\n")
            for phrase, context in cc_flagged:
                f.write(f"[CC] FLAGGED: «{phrase}» (no evidence in same response)\n")
                f.write(f"[CC] CONTEXT: {context.strip().replace(chr(10), ' ')[:300]}\n")
                f.write(f"[CC] TOOLS_IN_RESPONSE: {response_tools or 'none'}\n")
    except (IOError, OSError):
        pass

    if flagged:
        print("🚫 CLAUDE DOCTOR: attribution fabrication — «code words» not found in user's messages.", file=sys.stderr)
        for w, _ in flagged:
            print(f"  - {w}", file=sys.stderr)
    if cc_flagged:
        print("⚠️  CLAUDE DOCTOR: completion claim without evidence in the same response.", file=sys.stderr)
        for p, _ in cc_flagged:
            print(f"  - {p}", file=sys.stderr)
        print(f"  Tools in response: {response_tools or 'none'}", file=sys.stderr)

    print(f"Log: {log_file()}", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
