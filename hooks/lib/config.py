# -*- coding: utf-8 -*-
"""Parse per-project .local.md config for Claude Doctor.

Config file location: $CLAUDE_PROJECT_DIR/.claude/claude-doctor.local.md
Format: YAML frontmatter + optional markdown body (body ignored).

Schema:
    enabled: true | false              # master switch, default true
    language: "en" | "ru" | "both"     # inject language, default "en"
    prod_keywords_add: [str, ...]      # added to default list
    prod_keywords_replace: [str, ...]  # fully replaces defaults if non-empty
    architectural_enabled: true|false  # default true
    fabrication_enabled: true|false    # default true
    claim_phrases_add: [str, ...]
    claim_phrases_replace: [str, ...]
    claim_phrases_blocking: [str, ...] # v0.2: phrases that trigger Stop-hook exit 2
    claim_phrases_ignore: [str, ...]   # v0.2: phrases excluded from flagging entirely
    last_triage_timestamp: "ISO-8601"  # v0.2: auto-managed by /triage, do not edit
    scan_history: true | false         # default true, reads ~/.claude/history.jsonl
    monitoring_path: "path/to/file.md" # optional override

If file missing or invalid: return defaults. Never raise — hooks must be fault-tolerant.
"""
import re
from pathlib import Path


DEFAULTS = {
    "enabled": True,
    "language": "en",
    "prod_keywords_add": [],
    "prod_keywords_replace": [],
    "architectural_enabled": True,
    "fabrication_enabled": True,
    "claim_phrases_add": [],
    "claim_phrases_replace": [],
    "claim_phrases_blocking": [],
    "claim_phrases_ignore": [],
    "last_triage_timestamp": "",
    "scan_history": True,
    "monitoring_path": "",
}


def _parse_value(raw):
    """Minimal YAML value parser. Handles: true/false, strings, [list,items]."""
    s = raw.strip()
    if not s:
        return ""
    if s.lower() == "true":
        return True
    if s.lower() == "false":
        return False
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        if not inner:
            return []
        items = []
        for part in inner.split(","):
            p = part.strip().strip('"').strip("'")
            if p:
                items.append(p)
        return items
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    return s


def load(config_path):
    """Load config from Path. Return dict with DEFAULTS merged in.

    Never raises. Missing file → defaults. Parse error → defaults.
    """
    cfg = dict(DEFAULTS)

    if not isinstance(config_path, Path):
        config_path = Path(config_path)

    if not config_path.exists():
        return cfg

    try:
        text = config_path.read_text(encoding="utf-8")
    except (IOError, OSError):
        return cfg

    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?", text, re.DOTALL)
    if not m:
        return cfg

    fm = m.group(1)
    for line in fm.split("\n"):
        line = line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, raw = line.partition(":")
        key = key.strip()
        if key in DEFAULTS:
            cfg[key] = _parse_value(raw)

    return cfg


def is_enabled(cfg, feature_key):
    """Combine master switch with feature-specific switch."""
    if not cfg.get("enabled", True):
        return False
    return cfg.get(feature_key, True)
