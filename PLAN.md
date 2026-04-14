# Cloud Doctor Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package three working Claude Code hooks (prod-keyword-detector, architectural-question-detector, fabrication-detector + SessionStart analyzer) as a cross-platform Claude Code plugin published via GitHub marketplace, with bilingual EN/RU defaults and per-project configuration via `.local.md`.

**Architecture:** Single-plugin marketplace repo. Hooks written in Python, invoked via `sh` launcher that auto-detects `python3|python|uv`. Per-project user config lives in `.claude/cloud-doctor.local.md` (YAML + markdown). Persistent data (logs, monitoring file) goes to `$CLAUDE_PLUGIN_DATA` with fallback to `~/.claude/plugin-data/cloud-doctor/`. Plugin hooks don't replace user hooks — they merge.

**Tech Stack:** Python 3 (stdlib only, no deps), Bash/sh launcher, JSON manifests, Markdown documentation.

**Philosophy:** Rules in CLAUDE.md are post-hoc appeals — not in-moment guardrails. Hooks run inside Claude Code itself and inject context reminders at the exact event where the pattern would repeat. Three event points: `UserPromptSubmit` (prevent before acting), `Stop` (audit after), `SessionStart` (aggregate audit history for visibility). Source: project «Анализ Клода — апрель», confirmed independently by 4 bug reports on anthropics/claude-code (#37818, #36492, #29564, #37297), Karpathy, and Huang et al. 2023.

**Target repo:** `C:\ObsidianVault\_repos\cloud-doctor\` → `alenazaharovaux/cloud-doctor` on GitHub.

---

## File Structure

```
cloud-doctor/
├── .claude-plugin/
│   ├── marketplace.json              # Single-plugin marketplace manifest
│   └── plugin.json                   # Plugin manifest
├── hooks/
│   ├── hooks.json                    # Event declarations
│   ├── run.sh                        # Python auto-detect launcher
│   ├── prod_keyword_detector.py
│   ├── architectural_question_detector.py
│   ├── fabrication_detector.py
│   ├── session_start_analyzer.py
│   └── lib/
│       ├── __init__.py
│       ├── paths.py                  # Resolve PLUGIN_DATA / PROJECT_DIR with fallback
│       └── config.py                 # Parse .local.md
├── commands/
│   └── setup.md                      # /cloud-doctor:setup command
├── templates/
│   ├── cloud-doctor.local.md.example
│   └── claim_phrases.default.txt     # Bilingual defaults
├── references/
│   └── philosophy.md                 # English «why»
├── tests/
│   └── test_completion_claims.py     # Ported unit test
├── LICENSE                           # MIT
├── README.md                         # EN (primary)
├── README.ru.md                      # RU
├── CHANGELOG.md
├── PLAN.md                           # This file
└── .gitignore
```

---

## Task 1: Initialize repo structure

**Files:**
- Create: `C:/ObsidianVault/_repos/cloud-doctor/.gitignore`
- Create: directory tree per File Structure

- [ ] **Step 1: Create directory tree**

```bash
cd "C:/ObsidianVault/_repos/cloud-doctor"
mkdir -p .claude-plugin hooks/lib commands templates references tests
```

- [ ] **Step 2: Write .gitignore**

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
.pytest_cache/

# Plugin local data (when plugin runs from this repo)
.claude/*.local.md
.claude/*.local.json
data/
*.log
*.heartbeat

# OS
.DS_Store
Thumbs.db

# Editor
.vscode/
.idea/
*.swp
```

- [ ] **Step 3: Verify**

```bash
ls -la
# Expected: .gitignore + 6 dirs (.claude-plugin, hooks, commands, templates, references, tests)
```

---

## Task 2: Write plugin manifest

**Files:**
- Create: `.claude-plugin/plugin.json`

- [ ] **Step 1: Write plugin.json**

```json
{
  "name": "cloud-doctor",
  "version": "0.1.0",
  "description": "Structural guardrails for Claude Code: in-moment reminders for production actions, architectural questions, and completion claims without evidence. Because rules in CLAUDE.md don't activate in the moment.",
  "author": {
    "name": "Alena Zakharova",
    "url": "https://github.com/alenazaharovaux"
  },
  "homepage": "https://github.com/alenazaharovaux/cloud-doctor",
  "repository": "https://github.com/alenazaharovaux/cloud-doctor",
  "license": "MIT",
  "keywords": ["hooks", "self-check", "guardrails", "verification", "quality"]
}
```

- [ ] **Step 2: Validate JSON**

```bash
python3 -c "import json; json.load(open('.claude-plugin/plugin.json'))"
# Expected: no output (valid JSON)
```

---

## Task 3: Write marketplace manifest

**Files:**
- Create: `.claude-plugin/marketplace.json`

- [ ] **Step 1: Write marketplace.json**

```json
{
  "name": "cloud-doctor",
  "description": "Cloud Doctor single-plugin marketplace — structural guardrails for Claude Code",
  "owner": {
    "name": "Alena Zakharova",
    "url": "https://github.com/alenazaharovaux"
  },
  "plugins": [
    {
      "name": "cloud-doctor",
      "source": "./",
      "description": "In-moment reminders for production actions, architectural questions, and completion claims without evidence",
      "version": "0.1.0",
      "category": "productivity",
      "tags": ["hooks", "guardrails", "quality", "self-check"]
    }
  ]
}
```

- [ ] **Step 2: Validate JSON**

```bash
python3 -c "import json; json.load(open('.claude-plugin/marketplace.json'))"
# Expected: no output (valid JSON)
```

---

## Task 4: Write Python auto-detect launcher

**Files:**
- Create: `hooks/run.sh`

- [ ] **Step 1: Write run.sh**

```bash
#!/bin/sh
# Cloud Doctor — Python interpreter auto-detector
# Tries uv run > python3 > python in order.
# Usage: sh run.sh <hook_script_name_without_extension> [args...]
#
# Rationale: Windows typically has `python`, Linux typically `python3`,
# and `uv run python` works everywhere if uv is installed. Hardcoding
# `python3` causes silent failures on Windows (see hookify issue #405).

HOOK_NAME="$1"
shift

if [ -z "$HOOK_NAME" ]; then
  echo '{"systemMessage": "cloud-doctor run.sh: hook name missing"}' >&2
  exit 0
fi

HOOK_PATH="${CLAUDE_PLUGIN_ROOT}/hooks/${HOOK_NAME}.py"

if [ ! -f "$HOOK_PATH" ]; then
  echo "{\"systemMessage\": \"cloud-doctor: hook script not found: $HOOK_PATH\"}" >&2
  exit 0
fi

if command -v uv >/dev/null 2>&1; then
  exec uv run python "$HOOK_PATH" "$@"
elif command -v python3 >/dev/null 2>&1; then
  exec python3 "$HOOK_PATH" "$@"
elif command -v python >/dev/null 2>&1; then
  exec python "$HOOK_PATH" "$@"
else
  echo '{"systemMessage": "cloud-doctor: no Python interpreter found (tried uv, python3, python)"}' >&2
  exit 0
fi
```

- [ ] **Step 2: Make executable**

```bash
chmod +x hooks/run.sh
```

- [ ] **Step 3: Test the detection logic**

```bash
CLAUDE_PLUGIN_ROOT=$(pwd) sh hooks/run.sh nonexistent
# Expected: systemMessage about missing hook (not Python error)
```

---

## Task 5: Write paths library

**Files:**
- Create: `hooks/lib/__init__.py` (empty)
- Create: `hooks/lib/paths.py`

- [ ] **Step 1: Create empty __init__.py**

```bash
touch hooks/lib/__init__.py
```

- [ ] **Step 2: Write paths.py**

```python
# -*- coding: utf-8 -*-
"""Path resolution helpers for Cloud Doctor hooks.

Handles:
- CLAUDE_PLUGIN_DATA env var with fallback to ~/.claude/plugin-data/cloud-doctor/
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
        p = Path(os.path.expanduser("~")) / ".claude" / "plugin-data" / "cloud-doctor"
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
    return project_dir() / ".claude" / "cloud-doctor.local.md"


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
```

- [ ] **Step 3: Quick smoke test**

```bash
cd "C:/ObsidianVault/_repos/cloud-doctor"
CLAUDE_PLUGIN_ROOT=$(pwd) python3 -c "
import sys
sys.path.insert(0, 'hooks')
from lib.paths import plugin_root, plugin_data, log_file
print('root:', plugin_root())
print('data:', plugin_data())
print('log:', log_file())
"
# Expected: three paths printed, plugin_data dir created in ~/.claude/plugin-data/cloud-doctor/
```

---

## Task 6: Write config loader

**Files:**
- Create: `hooks/lib/config.py`

- [ ] **Step 1: Write config.py**

```python
# -*- coding: utf-8 -*-
"""Parse per-project .local.md config for Cloud Doctor.

Config file location: $CLAUDE_PROJECT_DIR/.claude/cloud-doctor.local.md
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
    # List
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
    # String with quotes
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

    # Extract frontmatter between first two `---` markers
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
```

- [ ] **Step 2: Smoke test**

```bash
cd "C:/ObsidianVault/_repos/cloud-doctor"
python3 -c "
import sys
sys.path.insert(0, 'hooks')
from lib.config import load, DEFAULTS
# No file → defaults
c = load('nonexistent.md')
assert c == DEFAULTS, f'expected defaults, got {c}'
print('OK defaults returned when file missing')
"
# Expected: "OK defaults returned when file missing"
```

- [ ] **Step 3: Test with real frontmatter (cross-platform via tempfile)**

```bash
cd "C:/ObsidianVault/_repos/cloud-doctor"
python3 <<'PYEOF'
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, 'hooks')
from lib.config import load

content = """---
enabled: true
language: "both"
prod_keywords_add: ["mycompany", "prod-db"]
scan_history: false
---
# Notes
body ignored
"""
with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
    f.write(content)
    tmp = f.name

try:
    c = load(tmp)
    assert c['language'] == 'both', c
    assert c['prod_keywords_add'] == ['mycompany', 'prod-db'], c
    assert c['scan_history'] is False, c
    print('OK parsed:', c['language'], c['prod_keywords_add'], c['scan_history'])
finally:
    Path(tmp).unlink()
PYEOF
# Expected: "OK parsed: both ['mycompany', 'prod-db'] False"
```

---

## Task 7: Port prod-keyword-detector

**Files:**
- Create: `hooks/prod_keyword_detector.py`

Source: `C:/Users/alena/.claude/hooks/prod-keyword-detector.py`

Changes from source:
1. Bilingual keyword defaults (RU + EN)
2. Reads `.local.md` for `prod_keywords_add` / `prod_keywords_replace`
3. Injected message in EN / RU / both per `language`
4. `sys.path` for lib imports
5. Honors master `enabled` switch

- [ ] **Step 1: Write prod_keyword_detector.py**

```python
# -*- coding: utf-8 -*-
"""UserPromptSubmit hook: detect production-operation keywords, inject self-check reminder.

Port of Alena Zakharova's prod-keyword-detector. Original source:
https://github.com/alenazaharovaux/cloud-doctor/blob/main/references/philosophy.md
"""
import io
import json
import os
import re
import sys

from pathlib import Path as _Path  # noqa: E402
PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
if PLUGIN_ROOT:
    _hooks_dir = str(_Path(PLUGIN_ROOT) / "hooks")
    if _hooks_dir not in sys.path:
        sys.path.insert(0, _hooks_dir)

from lib.config import load as load_config, is_enabled  # noqa: E402
from lib.paths import config_file  # noqa: E402


DEFAULT_KEYWORDS_EN = [
    "deploy", "deployment", "push to production", "production release",
    "migrate", "migration", "rollout", "publish to", "ship to prod",
    "mass send", "broadcast", "bulk update", "commit and push",
]

DEFAULT_KEYWORDS_RU = [
    "деплой", "задеплой", "пушить в прод", "опублик", "публикуй",
    "рассылк", "массов", "миграци", "мигрир", "коммит и пуш",
    "клиентам", "прод-", "продакшн",
]


INJECT_EN = """
🔍 CLOUD DOCTOR — production keyword detected in user's message.

BEFORE any action, start your reply with this self-check block:

🔍 Self-check before action:
[ ] STATE: Is every «X is done / Y equals Z» claim backed by tool output in THIS response?
    → [concrete answer with command and result]
[ ] CAUSE: Is every «because Y / reason is Z» tagged ⓘ HYPOTHESIS or ✅ VERIFIED empirically?
    → [concrete answer]
[ ] CHOICE: Does every process/tool/architecture decision include an «alternatives: …» line?
    → [concrete answer]
[ ] INHERITANCE: Am I relying on old context (memory, past sessions)? If yes — verified freshness now?
    → [concrete answer]
[ ] LANGUAGE: Am I using «had to / was forced to / system requires» for my own decisions?
    → [concrete answer]

Fail-closed: if ANY item is not closed with a concrete fact — STOP, don't execute the action until user confirms.
"""

INJECT_RU = """
🔍 CLOUD DOCTOR — обнаружен триггер прод-операции в сообщении пользователя.

ДО любого действия — выведи в начале ответа блок самопроверки:

🔍 Самопроверка перед действием:
[ ] СОСТОЯНИЕ: каждое утверждение «N готово / X есть / Y равен Z» подкреплено tool output в этом же ответе?
    → [конкретный ответ с командой и результатом]
[ ] ПРИЧИНА: каждое «потому что Y / причина в Z» помечено как ⓘ ГИПОТЕЗА или ✅ ПРОВЕРЕНО эмпирически?
    → [конкретный ответ]
[ ] ВЫБОР: каждое решение про процесс/инструмент/архитектуру сопровождается строкой «альтернативы: …»?
    → [конкретный ответ]
[ ] НАСЛЕДИЕ: опираюсь на старый контекст (memory, прошлые сессии)? Если да — проверила актуальность сейчас?
    → [конкретный ответ]
[ ] ЯЗЫК: использую «пришлось / вынуждена / system требует» для собственных решений?
    → [конкретный ответ]

Fail-closed: если хоть один пункт не закрыт конкретным фактом — STOP, не выполнять действие до явного подтверждения от пользователя.
"""


def _build_pattern(cfg):
    if cfg["prod_keywords_replace"]:
        words = cfg["prod_keywords_replace"]
    else:
        words = DEFAULT_KEYWORDS_EN + DEFAULT_KEYWORDS_RU + cfg["prod_keywords_add"]
    if not words:
        return None
    escaped = [re.escape(w) for w in words if w]
    return "|".join(escaped)


def _pick_inject(lang):
    if lang == "ru":
        return INJECT_RU
    if lang == "both":
        return INJECT_EN + "\n" + INJECT_RU
    return INJECT_EN


def main():
    sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8")
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    prompt = data.get("prompt", "")
    if not prompt:
        sys.exit(0)

    cfg = load_config(config_file())
    if not cfg["enabled"]:
        sys.exit(0)

    pattern = _build_pattern(cfg)
    if not pattern:
        sys.exit(0)

    if re.search(pattern, prompt, re.IGNORECASE):
        print(_pick_inject(cfg["language"]))

    sys.exit(0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test with trigger word**

```bash
cd "C:/ObsidianVault/_repos/cloud-doctor"
CLAUDE_PLUGIN_ROOT=$(pwd) echo '{"prompt": "lets deploy to production"}' | python3 hooks/prod_keyword_detector.py
# Expected: English self-check block printed
```

- [ ] **Step 3: Test with RU word**

```bash
CLAUDE_PLUGIN_ROOT=$(pwd) echo '{"prompt": "пора делать деплой"}' | python3 hooks/prod_keyword_detector.py
# Expected: English block (default language=en)
```

- [ ] **Step 4: Test no-match**

```bash
CLAUDE_PLUGIN_ROOT=$(pwd) echo '{"prompt": "just checking a file"}' | python3 hooks/prod_keyword_detector.py
# Expected: no output
```

---

## Task 8: Port architectural-question-detector

**Files:**
- Create: `hooks/architectural_question_detector.py`

Source: `C:/Users/alena/.claude/hooks/architectural-question-detector.py`

Changes:
1. Existing pattern already bilingual (EN+RU) — keep as is
2. Reads `.local.md` for `architectural_enabled` switch
3. Injected message EN/RU/both per `language`
4. sys.path wiring

- [ ] **Step 1: Write architectural_question_detector.py**

```python
# -*- coding: utf-8 -*-
"""UserPromptSubmit hook: detect architectural/advisory questions, require tool-call grounding.

Port of Alena Zakharova's architectural-question-detector. Source & rationale:
references/philosophy.md section "Pattern B (Process over substance)".
"""
import io
import json
import os
import re
import sys

from pathlib import Path as _Path  # noqa: E402
PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
if PLUGIN_ROOT:
    _hooks_dir = str(_Path(PLUGIN_ROOT) / "hooks")
    if _hooks_dir not in sys.path:
        sys.path.insert(0, _hooks_dir)

from lib.config import load as load_config, is_enabled  # noqa: E402
from lib.paths import config_file  # noqa: E402


PATTERN = (
    # Russian advisory imperatives
    r"посоветуй|подскажи|"
    r"как (мне|нам) (организ|настр|структур|реализ|сделать так|подойти|выбрать|быть|поступить|разобраться)|"
    r"как (лучше|правильнее)|как бы (мне|нам)|"
    r"что (лучше|правильнее|посоветуешь|выбрать|думаешь о|думаешь про)|"
    r"стоит ли|имеет смысл|"
    r"какой (подход|вариант|способ|инструмент|выбор)|какую (архитектуру|структуру)|"
    r"\bархитектур|\bсетап\b|синхрониз|"
    r"разработай со мной|разбери со мной|обсуди со мной|"
    # English
    r"\bshould i\b|\bhow should i\b|\bhow do i\b|"
    r"what do you think about\b|what'?s the best\b|"
    r"\bbest way to\b|\badvise me\b|\brecommend|"
    r"\bhow would you\b|\bhow to approach\b|\bhow to structure\b|"
    r"\bwhich (approach|option|way|tool|choice|pattern)\b|\bsetup\b"
)


INJECT_EN = """
🔍 CLOUD DOCTOR — architectural/advisory question detected.

BEFORE generating any recommendation, plan, or substantive answer:

1. Make AT LEAST ONE tool call (Read / Bash / Glob / Grep) that reads REAL current state of files or folders related to the question. Not from memory, not from system reminder — a fresh read right now.

2. In your reply, explicitly list which files you read, and anchor each recommendation to specific content from them. Not «usually it's like X», but «in your folder X there is Y, therefore Z». Without this anchoring, don't give the answer.

3. If you can't figure out which files are relevant — DON'T generate a generic recommendation. Ask the user «which files/folders do you mean?» and wait. Asking beats fabricating.

4. Violation signal: a long structured answer with no visible tool_use blocks above it = Pattern B, repeated.

Source: Pattern B (Process over substance) — see references/philosophy.md.
"""

INJECT_RU = """
🔍 CLOUD DOCTOR — обнаружен архитектурный / советный вопрос.

ДО генерации любой рекомендации, плана, оценки:

1. Сделай минимум ОДИН tool call (Read / Bash / Glob / Grep), который читает РЕАЛЬНОЕ текущее состояние файлов/папок по теме. Не из памяти, не из system reminder — свежий read прямо сейчас.

2. В ответе явно перечисли, какие файлы прочитал, и привяжи каждую рекомендацию к конкретному содержимому. Не «обычно бывает так», а «в твоей папке X лежит Y, поэтому Z». Без этой привязки ответ не выдавать.

3. Если не можешь определить, какие файлы относятся к вопросу — НЕ генерируй общую рекомендацию. Спроси «какие файлы / папки ты имеешь в виду?» и жди.

4. Признак нарушения: длинный структурированный ответ без видимых tool_use блоков = Паттерн B, повторён.

Источник: Паттерн B (Process over substance) — см. references/philosophy.md.
"""


def _pick_inject(lang):
    if lang == "ru":
        return INJECT_RU
    if lang == "both":
        return INJECT_EN + "\n" + INJECT_RU
    return INJECT_EN


def main():
    sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8")
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    prompt = data.get("prompt", "")
    if not prompt:
        sys.exit(0)

    cfg = load_config(config_file())
    if not is_enabled(cfg, "architectural_enabled"):
        sys.exit(0)

    if re.search(PATTERN, prompt, re.IGNORECASE):
        print(_pick_inject(cfg["language"]))

    sys.exit(0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test with advisory question**

```bash
cd "C:/ObsidianVault/_repos/cloud-doctor"
CLAUDE_PLUGIN_ROOT=$(pwd) echo '{"prompt": "how should i structure this project?"}' | python3 hooks/architectural_question_detector.py
# Expected: English inject printed
```

- [ ] **Step 3: Test no-match**

```bash
CLAUDE_PLUGIN_ROOT=$(pwd) echo '{"prompt": "read this file"}' | python3 hooks/architectural_question_detector.py
# Expected: no output
```

---

## Task 9: Port fabrication-detector

**Files:**
- Create: `hooks/fabrication_detector.py`
- Create: `templates/claim_phrases.default.txt`

Source: `C:/Users/alena/.claude/hooks/fabrication-detector.py` (405 lines)
Source for claim_phrases: `C:/Users/alena/.claude/hooks/claim_phrases.txt`

Changes:
1. Remove Alena-specific attribution: use project name instead of personal name
2. Read claim_phrases from `templates/` fallback + `.local.md` additions
3. Use `lib.paths` for log/heartbeat locations (not hardcoded ~/.claude/hooks)
4. Honor `fabrication_enabled` + `scan_history` switches
5. Keep logic intact (it works and is tested)

- [ ] **Step 1: Write templates/claim_phrases.default.txt (bilingual)**

```
# Cloud Doctor — default completion-claim phrases
# Bilingual (EN + RU), expanded via user's .local.md
# Format: one phrase per line, lowercase, no regex
# Case-insensitive substring match on each sentence
# Empty lines and lines starting with # are ignored

# English
done
completed
finished
working
works
deployed
pushed
committed
passing
passed
all set
all good
ready
fixed
added
updated
created
successful

# Russian
готово
работает
добавлен
запушено
обновлён
создан
сделано
задеплоено
написано
добавил
исправлено
обновлена
закоммичено
удалён
проверено
успешный
создана
добавлена
развёрнуто
создал
создано
успешно
добавила
обновила
всё работает
создала
всё готово
всё ок
протестировано
закончено
развернуто
успешное
```

- [ ] **Step 2: Write fabrication_detector.py**

Full file — see implementation below. This is a port, not a rewrite. Key changes:
- Imports from `lib.paths` instead of hardcoded `~/.claude/hooks/`
- Reads claim phrases from templates dir with user additions
- Honors enabled/scan_history config
- Attribution pattern v1 stays the same (it's generic — «code words»)

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stop hook: detect fabrication patterns in assistant's last response.

Port of Alena Zakharova's fabrication-detector. Logs flagged patterns to
$CLAUDE_PLUGIN_DATA/audit.log. Log-only (exit 0) — does not block.

Two detectors:
- v1: attribution fabrication — assistant claims user has «code words»
      that don't actually appear in user's messages (or only in questioning context).
- v2: completion-claim without evidence — assistant says «done/works/deployed»
      without any evidence-tool call (Read/Bash/Grep/...) in same response.

Both detectors log-only for tuning. Upgrade to blocking later if false-positive rate OK.
"""
import datetime
import io
import json
import os
import re
import sys
from pathlib import Path

from pathlib import Path as _Path  # noqa: E402
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

    # Attribution pattern: «кодовое слово X» or «code word X» or «her term X»
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

    # Log
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

    # Stderr visibility
    if flagged:
        print("🚫 CLOUD DOCTOR: attribution fabrication — «code words» not found in user's messages.", file=sys.stderr)
        for w, _ in flagged:
            print(f"  - {w}", file=sys.stderr)
    if cc_flagged:
        print("⚠️  CLOUD DOCTOR: completion claim without evidence in the same response.", file=sys.stderr)
        for p, _ in cc_flagged:
            print(f"  - {p}", file=sys.stderr)
        print(f"  Tools in response: {response_tools or 'none'}", file=sys.stderr)

    print(f"Log: {log_file()}", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Basic smoke test**

```bash
cd "C:/ObsidianVault/_repos/cloud-doctor"
# Empty stdin — should exit 0
echo '{}' | CLAUDE_PLUGIN_ROOT=$(pwd) python3 hooks/fabrication_detector.py
echo "exit=$?"
# Expected: exit=0, no errors
```

---

## Task 10: Port cc_log_analyzer → session_start_analyzer

**Files:**
- Create: `hooks/session_start_analyzer.py`

Source: `C:/Users/alena/.claude/hooks/cc_log_analyzer.py` (large, 450+ lines — we keep logic, change only paths and monitoring location)

Changes:
1. Read log from `plugin_data() / audit.log` instead of `~/.claude/hooks/fabrication-detector.log`
2. Write monitoring summary to `monitoring_file(cfg['monitoring_path'])` (configurable)
3. Inject short summary to stdout on SessionStart (existing behavior)
4. Localize summary to cfg language

- [ ] **Step 1: Create stub that delegates to the original logic**

Because the full analyzer is 450 lines and is internal tooling, we write a compact version focused on what matters:

```python
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

from pathlib import Path as _Path  # noqa: E402
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


def _classify(phrase, context):
    """Rough heuristic: wrap-up vs real claim."""
    wrapup_markers = ["- ", "* ", "# ", "**", "✅", "✓", "done", "итог"]
    if any(m in context for m in wrapup_markers):
        return "wrapup"
    return "real"


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
    header = "# Cloud Doctor Monitoring\n\n" if lang != "ru" else "# Мониторинг Cloud Doctor\n\n"
    header += f"> Updated: {ts}  |  Window: last {WINDOW_DAYS} days\n\n"

    if not entries:
        return header + "_No flags in window._\n"

    counter = Counter(e["phrase"] for e in entries)
    sessions = len({e["session"] for e in entries})
    lines = [
        header,
        f"**Total flags:** {len(entries)}  ",
        f"**Unique sessions:** {sessions}",
        "",
        "## Top phrases",
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

    # Inject short summary
    print(f"📊 {summary_text}  (details: {mon_path})")
    sys.exit(0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke test**

```bash
cd "C:/ObsidianVault/_repos/cloud-doctor"
echo '{}' | CLAUDE_PLUGIN_ROOT=$(pwd) python3 hooks/session_start_analyzer.py
# Expected: "📊 Cloud Doctor — 7d: 0 flags..." and a monitoring.md file path
```

---

## Task 11: Write hooks.json

**Files:**
- Create: `hooks/hooks.json`

- [ ] **Step 1: Write hooks.json with run.sh launcher**

```json
{
  "description": "Cloud Doctor — structural guardrails (production keyword / architectural question / fabrication detection + session-start audit)",
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "sh ${CLAUDE_PLUGIN_ROOT}/hooks/run.sh prod_keyword_detector",
            "timeout": 10
          },
          {
            "type": "command",
            "command": "sh ${CLAUDE_PLUGIN_ROOT}/hooks/run.sh architectural_question_detector",
            "timeout": 10
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "sh ${CLAUDE_PLUGIN_ROOT}/hooks/run.sh fabrication_detector",
            "timeout": 15
          }
        ]
      }
    ],
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "sh ${CLAUDE_PLUGIN_ROOT}/hooks/run.sh session_start_analyzer",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 2: Validate JSON**

```bash
python3 -c "import json; print(json.load(open('hooks/hooks.json'))['description'])"
# Expected: description string printed
```

---

## Task 12: Write user config template

**Files:**
- Create: `templates/cloud-doctor.local.md.example`

- [ ] **Step 1: Write template**

```markdown
---
# Cloud Doctor — per-project configuration
# Copy this file to your project as: .claude/cloud-doctor.local.md
# Changes take effect on the next hook invocation (no Claude Code restart needed).

# Master switch. When false, ALL Cloud Doctor hooks skip.
enabled: true

# Injected-message language: "en" | "ru" | "both"
language: "en"

# Production-keyword detector: triggers self-check block.
# Defaults (shipped): common EN+RU prod-op verbs.
# Add your own project-specific words here (e.g. your company's deploy tool):
prod_keywords_add: []
# To fully replace defaults with a curated list, use this instead:
prod_keywords_replace: []

# Architectural-question detector: requires tool-call grounding.
architectural_enabled: true

# Fabrication detector (Stop hook, log-only).
fabrication_enabled: true

# Extra completion-claim phrases to detect (on top of defaults):
claim_phrases_add: []
# Or fully replace:
claim_phrases_replace: []

# Scan ~/.claude/history.jsonl to detect attribution fabrication?
# Turn off for privacy. Default true.
scan_history: true

# Override location of the SessionStart monitoring summary file.
# Leave empty to use plugin data dir. Path expands ~.
monitoring_path: ""
---

# Notes

Body is ignored by Cloud Doctor. Use it for your own notes about why
you configured the plugin this way (e.g. «added project X's jargon,
disabled architectural for code-review-only sessions»).
```

---

## Task 13: Write setup slash command

**Files:**
- Create: `commands/setup.md`

- [ ] **Step 1: Write /cloud-doctor:setup command**

```markdown
---
name: setup
description: Create Cloud Doctor per-project config from template
---

# Cloud Doctor Setup

Steps:

1. Check if `.claude/cloud-doctor.local.md` exists in the current project. If yes, tell the user it's already configured and offer to show current settings (cat the file).

2. If not, read the template from `${CLAUDE_PLUGIN_ROOT}/templates/cloud-doctor.local.md.example`.

3. Create `.claude/` directory in project if missing.

4. Copy the template to `.claude/cloud-doctor.local.md`.

5. Tell the user:
   - File created at `.claude/cloud-doctor.local.md`
   - Add `.claude/*.local.md` to `.gitignore` (don't commit personal config)
   - Hooks already use defaults; edit the file to customize (no restart needed)
   - Key switches: `enabled`, `language`, `prod_keywords_add`

6. Remind: if hooks aren't firing, run `claude --debug` once to see hook registration.
```

---

## Task 14: Write LICENSE (MIT)

**Files:**
- Create: `LICENSE`

- [ ] **Step 1: Write MIT License**

```
MIT License

Copyright (c) 2026 Alena Zakharova

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## Task 15: Write philosophy document

**Files:**
- Create: `references/philosophy.md`

- [ ] **Step 1: Write philosophy.md (~180 lines, English prose)**

Write the following sections in order, each with actual content — NOT a placeholder list:

**Section 1: «The problem» (opening, 2 paragraphs)**
- First paragraph sets up the observation: «Claude Code's behavior drifts mid-session. It starts sessions careful and explicit — reads real files before recommending, asks for confirmation before production actions — then, after several rounds, skips these steps silently. Not because the rules are missing: CLAUDE.md and AGENTS.md usually spell them out clearly. The rules are post-hoc appeals, not in-moment guardrails.»
- Second paragraph names the gap: knowing the rule and activating it are separate events. The model can recite the rule verbatim and still fail to apply it in the next turn.

**Section 2: «Two patterns we observed» (3-4 paragraphs)**
- **Pattern A — Fabrication of established vocabulary.** The assistant attributes phrases to the user that the user never said, or said only in questioning form («what do you mean by X?»). Opens with the April 2026 incident: assistant claimed «code words» that were the assistant's own invention. Frame the damage: user starts doubting their own memory, trust erodes.
- **Pattern B — Process over substance.** When asked advisory questions («how should I organize X», «what's the best approach»), the model generates structured plausible-sounding answers without opening any files. Contrast with concrete-task questions («fix the bug in Y.ts») where file-reading happens reflexively. The gap is advisory-framed tasks.
- Bridge paragraph: both patterns have the same root — rules don't activate in-moment. They activate when pointed-at post-hoc.

**Section 3: «External validation» (4 citations, 1 paragraph each)**
- Cite anthropics/claude-code issue #37818 (title, one-line summary, URL)
- Cite issue #36492
- Cite issue #29564
- Cite issue #37297
- Quote Karpathy: «All of this happens despite a few simple attempts to fix it via instructions in CLAUDE.md.» Source + date.
- Cite Huang et al. 2023 «LLMs Cannot Self-Correct Reasoning Yet» — one-sentence finding.
- Cite Anthropic alignment-faking research (December 2024) — one-sentence framing.

**Section 4: «Why hooks specifically» (2 paragraphs)**
- Structural mechanism, not another instruction: hooks run inside Claude Code's own program loop. The reminder appears as context injection at the event (UserPromptSubmit or Stop), not as text I have to remember to re-read.
- Three events, three purposes: UserPromptSubmit = prevent before acting; Stop = audit after; SessionStart = aggregate history to visible artifact.

**Section 5: «Log-only vs blocking» (1 paragraph + table)**
- Current state: v1 attribution check + v2 completion-claim are log-only (exit 0). Why: unknown false-positive rate on novel codebases and languages.
- Upgrade path table: when fabrication-detector hits > N sessions with < M% FP rate, flip exit code to 2 (blocking).

**Section 6: «Limits of this approach» (closing, 1 paragraph)**
- Honest: hooks can't catch everything. They catch the specific patterns we encoded. New patterns need new detectors. This plugin is a starting point, not a cure. The real product is the workflow — keyword list tuning, monitoring aggregation, regular review of flagged sessions.

**Section 7: «Credits» (final, 2 lines)**
- Plugin origin: Alena Zakharova, project «Анализ Клода — апрель», April 2026.
- MIT license. PRs welcome at alenazaharovaux/cloud-doctor.

Actual file tone: analytical, no marketing. Write in past tense for incidents, present tense for mechanism. Every claim anchored to a citation or explicit «our observation, not independently validated».

---

## Task 16: Write EN README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write README.md (~250 lines, EN, written during execution)**

Each section written as full prose, not bullet-summary. Structure:

**Top header (lines 1-15)**
```markdown
# Cloud Doctor

> Structural guardrails for Claude Code. Hook-based in-moment reminders for production actions, architectural questions, and completion claims without evidence.

[🇷🇺 Читать на русском](README.ru.md)

**Why this exists:** Rules in CLAUDE.md / AGENTS.md are post-hoc appeals — Claude reads them at session start, then drifts away from them mid-session. This plugin injects reminders at the exact event where the pattern would repeat (UserPromptSubmit / Stop), not as text that needs to be re-read. See [references/philosophy.md](references/philosophy.md).

**Status:** v0.1.0, log-only detection for the Stop hook (tunable). Cross-platform (Linux / macOS / Windows with Git Bash).
```

**Section «What it does» — one paragraph per hook:**
- prod-keyword-detector paragraph: triggers on words like `deploy`, `migrate`, `publish`, `push to production` (bilingual defaults EN+RU). Injects a 5-point self-check block before the assistant acts. User extends defaults via `prod_keywords_add`.
- architectural-question-detector paragraph: triggers on advisory phrasings (`how should I...`, `what's the best approach...`, `посоветуй...`). Requires at least one tool call (Read/Bash/Grep) on real files before the assistant generates a recommendation. Source: Pattern B from the linked philosophy doc.
- fabrication-detector paragraph: scans the assistant's last response at Stop event. Two sub-checks: attribution fabrication (assistant claims «your code words» that the user never used) and completion-claim without evidence («done», «deployed», «works» without a tool call that verified the state). Log-only by default.
- session-start-analyzer paragraph: once per session, aggregates last 7 days of flags into a human-readable summary, writes it to a monitoring file, and injects a one-line status into Claude's context.

**Section «Installation» — exact commands:**
```bash
# Inside Claude Code:
/plugin marketplace add alenazaharovaux/cloud-doctor
/plugin install cloud-doctor@cloud-doctor
/cloud-doctor:setup   # creates .claude/cloud-doctor.local.md in your project
```

**Section «Configuration» — full table of every `.local.md` field:**
| Field | Type | Default | Meaning |
| `enabled` | bool | true | Master switch |
| `language` | `en` / `ru` / `both` | en | Injected-message language |
| `prod_keywords_add` | list[str] | [] | Add to default keyword list |
| `prod_keywords_replace` | list[str] | [] | Replace defaults entirely |
| `architectural_enabled` | bool | true | Pattern B detector switch |
| `fabrication_enabled` | bool | true | Stop-hook detector switch |
| `claim_phrases_add` | list[str] | [] | Extra completion-claim phrases |
| `claim_phrases_replace` | list[str] | [] | Replace claim phrases entirely |
| `scan_history` | bool | true | Let fabrication-detector read ~/.claude/history.jsonl |
| `monitoring_path` | str | "" | Override SessionStart summary path |

Each field gets a short example immediately after the table.

**Section «Philosophy» — 1 paragraph + link:**
Links to `references/philosophy.md` with a teaser: «Why does this need to be a hook instead of just another rule in CLAUDE.md? Short answer: rules in CLAUDE.md activate post-hoc, hooks activate in-moment. Long answer, with external citations (4 GitHub issues, Karpathy, Huang et al.), in the philosophy doc.»

**Section «Troubleshooting» — problem / diagnosis / fix triples:**
- «Hooks silent / nothing happens on trigger words»
  - Diagnosis: run `claude --debug` and watch for hook registration
  - Fix: ensure `python3` or `python` in PATH; on Windows ensure Git Bash available
- «Windows: `sh: command not found`»
  - Cause: No Git Bash installed
  - Fix: install Git for Windows (bundles Git Bash)
- «I changed `.local.md` but nothing happens»
  - Cause: `.local.md` is read per hook invocation. Send a new user message to re-trigger.
- «Where are the logs?»
  - Default: `~/.claude/plugin-data/cloud-doctor/audit.log` (or `$CLAUDE_PLUGIN_DATA/` if set)
- «How do I turn it off without uninstalling?»
  - Option 1: `/plugin disable cloud-doctor@cloud-doctor`
  - Option 2: in `.local.md`, set `enabled: false`

**Section «Contributing»**: 3 lines + link to CONTRIBUTING.md (to be added later if demand). For v0.1 just: «PRs welcome — open issues on the repo. Biggest wanted contributions: keyword list suggestions for other languages, false-positive reports from fabrication-detector.»

**Section «License»**: one line, MIT, link to LICENSE file.

**Section «Credits»**: 2 lines. Author (Alena Zakharova, URL). Project origin (Анализ Клода — апрель, April 2026). Co-authored by Claude Opus 4.6.

---

## Task 17: Write RU README

**Files:**
- Create: `README.ru.md`

- [ ] **Step 1: Write README.ru.md (~250 lines, RU, during execution)**

Русский зеркальный перевод README.md. **Не машинный** — передаёт голос и стиль оригинального проекта «Анализ Клода». Структура идентична: header с переключателем языка, «Что делает», «Установка», «Конфигурация» (таблица всех полей), «Философия», «Troubleshooting», «Contributing», «Лицензия», «Благодарности».

**Критично для голоса — применять правила из `~/.claude/CLAUDE.md` секция «Правила написания текстов»:**
- Никаких рубленых драматических фрагментов («Кейсы есть. Системы нет.» — так не писать)
- Никаких стаккато-списков («Нет X. Нет Y. Нет Z.» → «Не было ни X, ни Y, ни Z»)
- Никаких punch-line обрубков в конце абзацев
- Факты → контекст → анализ, связным предложением
- Без кликбейта, без «шокирующей правды», без «никто не знает»

**Примеры тональности:**
- «Почему это нужно» (EN: Why this exists) — открывается абзацем с фактами из проекта «Анализ Клода — апрель», не с эмоциональным хуком
- «Что делает» (EN: What it does) — 4 абзаца, каждый описывает хук через механизм, не через пафос
- «Философия» — ссылка на philosophy.md с короткой аннотацией, тот же голос

**Пример первого абзаца header'а (задаёт тон всему документу):**
> «Cloud Doctor — плагин для Claude Code, добавляющий структурные предохранители в момент действия. Правила в CLAUDE.md и AGENTS.md Claude читает в начале сессии и к середине дрейфует от них — об этом написаны отчёты на anthropics/claude-code (#37818, #36492, #29564, #37297), об этом пишет Andrej Karpathy, это подтверждает независимое академическое исследование Huang et al. 2023. Cloud Doctor не добавляет ещё одно правило — он инжектит напоминание ровно в тот момент, когда паттерн вот-вот повторится.»

**Ссылка сверху:** `[🇬🇧 Read in English](README.md)`

**Не делать:**
- «Никто не заметил! Только Cloud Doctor видит!» — кликбейт
- «Просто установи и забудь» — маркетинговая ложь, плагин требует конфигурации
- Длинные вступления «В наше время, когда AI меняет мир...» — убрать

---

## Task 18: Write CHANGELOG

**Files:**
- Create: `CHANGELOG.md`

- [ ] **Step 1: Initial entry**

```markdown
# Changelog

All notable changes to this project will be documented in this file.

## [0.1.0] — 2026-04-14

### Added
- Initial release
- UserPromptSubmit hook: production keyword detector (bilingual EN+RU)
- UserPromptSubmit hook: architectural question detector (bilingual EN+RU)
- Stop hook: fabrication detector (attribution + completion-claim, log-only)
- SessionStart hook: 7-day audit aggregator
- Per-project config via `.claude/cloud-doctor.local.md`
- `/cloud-doctor:setup` slash command
- Cross-platform Python launcher (`run.sh`) — auto-detects uv/python3/python
- English and Russian READMEs

### Known limitations
- Completion-claim detector is log-only (not blocking). Upgrade path documented in philosophy.md.
- `CLAUDE_PLUGIN_DATA` env var — fallback to `~/.claude/plugin-data/cloud-doctor/` if unset.
- No automated tests in CI yet.
```

---

## Task 19: Port existing unit test

**Files:**
- Create: `tests/test_completion_claims.py`

Source: `C:/Users/alena/.claude/hooks/test_completion_claims.py` (16 test cases, passing)

- [ ] **Step 1: Copy with path adjustments**

Replace imports like `from fabrication_detector import ...` to work from tests dir:

```python
#!/usr/bin/env python3
"""Unit tests for completion-claim detection. Port from personal hooks."""
import os
import sys
import unittest
from pathlib import Path

# Make hooks/ importable
REPO_ROOT = Path(__file__).parent.parent
os.environ["CLAUDE_PLUGIN_ROOT"] = str(REPO_ROOT)
sys.path.insert(0, str(REPO_ROOT / "hooks"))

from fabrication_detector import find_completion_claims, has_evidence


class TestCompletionClaims(unittest.TestCase):
    def setUp(self):
        self.phrases = ["done", "работает", "готово", "deployed"]

    def test_simple_claim(self):
        self.assertTrue(find_completion_claims("All done.", self.phrases))

    def test_negation_filter(self):
        self.assertFalse(find_completion_claims("not done yet.", self.phrases))

    def test_question_filter(self):
        self.assertFalse(find_completion_claims("is it done?", self.phrases))

    def test_code_block_stripped(self):
        text = "```\nall done\n```\nno claim here."
        self.assertFalse(find_completion_claims(text, self.phrases))

    def test_ru_claim(self):
        self.assertTrue(find_completion_claims("Всё работает.", self.phrases))

    def test_evidence_tools(self):
        self.assertTrue(has_evidence(["Read", "Edit"]))
        self.assertFalse(has_evidence(["Edit"]))
        self.assertFalse(has_evidence([]))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests**

```bash
cd "C:/ObsidianVault/_repos/cloud-doctor"
python3 -m unittest tests.test_completion_claims -v
# Expected: 6 tests OK
```

---

## Task 20: Git init, first commit, push

**Files:**
- Create: `.git/` (via git init)

- [ ] **Step 1: Init repo**

```bash
cd "C:/ObsidianVault/_repos/cloud-doctor"
git init -b main
git add -A
git status
```

- [ ] **Step 2: Review staged files**

Expected: all source files, no `.log` / `.heartbeat` / `__pycache__` leaked.

- [ ] **Step 3: Commit**

```bash
git commit -m "$(cat <<'EOF'
Initial release — Cloud Doctor v0.1.0

Structural guardrails for Claude Code via hooks:
- UserPromptSubmit: prod-keyword detector + architectural-question detector
- Stop: fabrication detector (attribution + completion-claim, log-only)
- SessionStart: 7-day audit aggregator

Bilingual EN/RU defaults. Per-project config via .claude/cloud-doctor.local.md.
Cross-platform Python launcher (uv/python3/python auto-detect).
MIT License.

Origin: project «Анализ Клода — апрель» — rules in CLAUDE.md activate post-hoc,
not in-moment. Hooks run inside Claude Code itself and inject context at the
exact event where the pattern would repeat.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 4: Create GitHub repo (ask Alena for confirmation before push)**

Ask: «Create `alenazaharovaux/cloud-doctor` as public GitHub repo and push? Or you want to create the repo manually in browser first?»

- [ ] **Step 5: Push (after confirmation)**

```bash
# If Alena creates repo in browser:
git remote add origin https://github.com/alenazaharovaux/cloud-doctor.git
git push -u origin main

# Or using gh CLI (if available):
gh repo create cloud-doctor --public --source=. --push --description "Structural guardrails for Claude Code — hook-based in-moment reminders"
```

---

## Self-Review Checklist

After completing all 20 tasks, run:

- [ ] Every file in File Structure section exists
- [ ] All JSON files validate
- [ ] `sh hooks/run.sh nonexistent` returns systemMessage, exit 0
- [ ] Each hook script runs with `CLAUDE_PLUGIN_ROOT=$(pwd)` and sample stdin without errors
- [ ] `tests/test_completion_claims.py` passes all cases
- [ ] README.md has link to README.ru.md and vice versa
- [ ] `.gitignore` excludes `__pycache__`, `.log`, `.heartbeat`, `.local.md`
- [ ] `plugin.json` + `marketplace.json` both have correct `name`, `version`, `source`
- [ ] `philosophy.md` cites 4 GitHub issues, Karpathy, Huang et al. (external validation)
- [ ] Git log shows one clean initial commit

---

## Acceptance Criteria

1. A stranger on macOS can run `/plugin marketplace add alenazaharovaux/cloud-doctor` followed by `/plugin install cloud-doctor@cloud-doctor`, then `/cloud-doctor:setup`, and have working hooks on their first session with no additional manual edits.
2. The same stranger on Windows 11 with `python` (no `python3`) can install and have hooks actually fire (no silent failure like hookify #405).
3. Adding `prod_keywords_add: ["mycustomword"]` to `.claude/cloud-doctor.local.md` makes the prod-keyword hook fire on that word within one session (hookify-style hot config, no restart).
4. Setting `enabled: false` silences all hooks without uninstall.
5. SessionStart inject appears once per session with flag count summary.
