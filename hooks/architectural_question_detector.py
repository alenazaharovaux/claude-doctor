# -*- coding: utf-8 -*-
"""UserPromptSubmit hook: detect architectural/advisory questions, require tool-call grounding.

Part of Claude Doctor plugin. Source & rationale:
references/philosophy.md section "Pattern B (Process over substance)".
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
🔍 CLAUDE DOCTOR — architectural/advisory question detected.

BEFORE generating any recommendation, plan, or substantive answer:

1. Make AT LEAST ONE tool call (Read / Bash / Glob / Grep) that reads REAL current state of files or folders related to the question. Not from memory, not from system reminder — a fresh read right now.

2. In your reply, explicitly list which files you read, and anchor each recommendation to specific content from them. Not «usually it's like X», but «in your folder X there is Y, therefore Z». Without this anchoring, don't give the answer.

3. If you can't figure out which files are relevant — DON'T generate a generic recommendation. Ask the user «which files/folders do you mean?» and wait. Asking beats fabricating.

4. Violation signal: a long structured answer with no visible tool_use blocks above it = Pattern B, repeated.

Source: Pattern B (Process over substance) — see references/philosophy.md.
"""

INJECT_RU = """
🔍 CLAUDE DOCTOR — обнаружен архитектурный / советный вопрос.

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
