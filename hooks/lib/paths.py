# -*- coding: utf-8 -*-
"""Path resolution helpers for Claude Doctor hooks.

Handles:
- CLAUDE_PLUGIN_DATA env var with fallback to ~/.claude/plugin-data/claude-doctor/
- CLAUDE_PROJECT_DIR for reading .local.md from user's project
- CLAUDE_PLUGIN_ROOT for accessing plugin's own files (templates, libs)

All paths returned as pathlib.Path. Directories created on demand.
"""
import os
from pathlib import Path


def plugin_root():
    """Return plugin installation directory. Required env var."""
    root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if not root:
        raise RuntimeError(
            "CLAUDE_PLUGIN_ROOT not set — hook invoked outside Claude Code?"
        )
    return Path(root)


def plugin_data():
    """Return persistent data dir. Uses CLAUDE_PLUGIN_DATA if set, else fallback."""
    data = os.environ.get("CLAUDE_PLUGIN_DATA")
    if data:
        p = Path(data)
    else:
        p = Path(os.path.expanduser("~")) / ".claude" / "plugin-data" / "claude-doctor"
    p.mkdir(parents=True, exist_ok=True)
    return p


def project_dir():
    """Return user's project root if available. Falls back to CWD."""
    proj = os.environ.get("CLAUDE_PROJECT_DIR")
    if proj:
        return Path(proj)
    return Path.cwd()


def config_file():
    """Return path to user's .local.md in their project."""
    return project_dir() / ".claude" / "claude-doctor.local.md"


def log_file():
    """Return path to persistent audit log."""
    return plugin_data() / "audit.log"


def heartbeat_file():
    """Return path to hook-ran heartbeat."""
    return plugin_data() / "heartbeat.log"


def monitoring_file(override=None):
    """Return path to SessionStart monitoring summary.

    If override provided (from .local.md), use that (expands ~).
    Else default to plugin_data / monitoring.md.
    """
    if override:
        return Path(os.path.expanduser(override))
    return plugin_data() / "monitoring.md"


def history_jsonl():
    """Return path to user's Claude Code history. Standard location."""
    return Path(os.path.expanduser("~")) / ".claude" / "history.jsonl"
