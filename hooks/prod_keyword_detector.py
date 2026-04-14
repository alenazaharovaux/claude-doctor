# -*- coding: utf-8 -*-
"""UserPromptSubmit hook: detect production-operation keywords, inject self-check reminder.

Part of Cloud Doctor plugin. Source & rationale:
https://github.com/alenazaharovaux/cloud-doctor/blob/main/references/philosophy.md
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

from lib.config import load as load_config  # noqa: E402
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
