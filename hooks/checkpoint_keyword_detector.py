# -*- coding: utf-8 -*-
"""UserPromptSubmit hook: detect checkpoint/end-session keywords, inject handoff-format reminder.

Part of Claude Doctor plugin. Source & rationale:
https://github.com/alenazaharovaux/claude-doctor/blob/main/references/philosophy.md

Session memory files are not diary logs — they are self-contained handoffs for the next
session. Without structured fields (fresh commit SHA, state invariant, literal continuation
prompt, infra notes, ADR status), the next session wastes 15-20% of context rebuilding
what the previous session already knew.
"""
import io
import json
import os
import re
import sys

from pathlib import Path as _Path
PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
if PLUGIN_ROOT:
    _hooks_dir = str(_Path(PLUGIN_ROOT) / "hooks")
    if _hooks_dir not in sys.path:
        sys.path.insert(0, _hooks_dir)

from lib.config import load as load_config, is_enabled  # noqa: E402
from lib.paths import config_file  # noqa: E402


DEFAULT_KEYWORDS_EN = [
    "checkpoint", "check-point", "check point",
    "end session", "end of session", "wrap up", "wrap-up",
    "close the session", "finish the session",
]

DEFAULT_KEYWORDS_RU = [
    "чекпоинт", "чек-поинт", "чекпойнт", "чек-пойнт",
    "завершаем сесси", "завершить сесси", "завершаем",
    "закрываем сесси", "закрыть сесси",
]


INJECT_EN = """
🔍 CLAUDE DOCTOR — checkpoint keyword detected in user's message.

The session memory file you are about to write is NOT a diary log.
It is a self-contained HANDOFF for the next session. Without structure, the
next session wastes context rebuilding what this one already knew.

Required sections in session-*.md:

1. **Current system state**
   - Latest commit SHA (format: `git log -1 --oneline`)
   - What is complete vs partial (state invariant — what is TRUE right now, not what was done)
   - Which files wait for the next step

2. **Literal prompt for the next session** (copy-paste ready)
   Format: «Continue with Task X. Read Y. Fresh on master: Z.»

3. **Infrastructure left in place** (if reused later)
   - Which scripts are not deleted and why
   - Which artefacts are in git
   - Which changes are stashed

4. **Quirks discovered** (so the next session doesn't hit the same walls)
   - What broke and how it was fixed
   - Encoding / API / parser quirks — anything not obvious from code

5. **ADR status** (explicit)
   - If architectural decisions were made → list ADR candidates
   - If not → state explicitly «ADR not required, reason: ...»

Applies to EVERY session-*.md file on «checkpoint» / «end session» trigger.
"""

INJECT_RU = """
🔍 CLAUDE DOCTOR — обнаружен триггер «чекпоинт» в сообщении пользователя.

Session memory файл — это НЕ дневниковый лог.
Это self-contained ХЭНДОФФ для следующей сессии. Без структуры следующая
сессия тратит контекст на пересборку того, что эта уже знала.

Обязательные секции в session-*.md файле:

1. **Свежее состояние системы**
   - Последний commit SHA (формат: `git log -1 --oneline`)
   - Что полное / что частичное (инвариант — не «что сделано», а «что сейчас true»)
   - Какие файлы ждут следующего шага

2. **Буквальный промпт для следующей сессии** (копипастом запускаемый)
   Формат: «Продолжаем с Task X. Прочитай Y. Свежее на master: Z.»

3. **Инфраструктура оставлена** (если что-то переиспользуется)
   - Какие скрипты не удалены, зачем
   - Какие artefact'ы в git
   - Какие изменения стэшены

4. **Нюансы обнаружены** (чтобы следующая сессия не наступала на те же грабли)
   - Что ломалось и как починилось
   - Кавычки / encoding / API quirks — всё, что не очевидно из кода

5. **ADR-статус** (явно)
   - Если были архитектурные решения → список ADR-кандидатов
   - Если нет → явно «ADR не требуется, причина: ...»

Применимо к КАЖДОМУ session-*.md файлу при триггере «чекпоинт» / «завершаем сессию».
"""


def _build_pattern(cfg):
    if cfg["checkpoint_keywords_replace"]:
        words = cfg["checkpoint_keywords_replace"]
    else:
        words = (
            DEFAULT_KEYWORDS_EN
            + DEFAULT_KEYWORDS_RU
            + cfg["checkpoint_keywords_add"]
        )
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
    if not is_enabled(cfg, "checkpoint_enabled"):
        sys.exit(0)

    pattern = _build_pattern(cfg)
    if not pattern:
        sys.exit(0)

    if re.search(pattern, prompt, re.IGNORECASE):
        print(_pick_inject(cfg["language"]))

    sys.exit(0)


if __name__ == "__main__":
    main()
