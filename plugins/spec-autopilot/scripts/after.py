"""依る spec の名前の読み取りと、後の spec と依る spec の対の記録（repo の外のファイル）。
autopilot.py・lineup.py・light.py が使う下の層（stages だけに依る）。"""
import json
import os
import re
from pathlib import Path

from stages import COMMENT_BLOCK, section

AFTER = re.compile(r"^- 依る spec:\s*(\S+)\s*$", re.M)
NEXT = "lineup.py next"


def after_name(d):
    return (AFTER.search(COMMENT_BLOCK.sub("", section((d / "spec.md").read_text(encoding="utf-8"), "制約") or "")) or [None, None])[1]


def pairs_file():
    return Path(os.environ.get("SPEC_AUTOPILOT_HOME") or Path.home() / ".claude" / "spec-autopilot") / "lineup-after.json"


def pairs():
    """「後の spec の絶対パス → 依る spec の絶対パス」。repo の外に置く（state.json は commit されるので、パスは書けない）。無ければ {}、壊れていれば例外。"""
    f = pairs_file()
    if not f.exists():
        return {}
    try:
        v = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ValueError(f"{f.name} が読めない（{type(e).__name__}）") from e  # block の理由は state.json に入るので、パスは書かず名前だけ
    if not isinstance(v, dict) or not all(isinstance(k, str) and isinstance(x, str) for k, x in v.items()):
        raise ValueError(f"{f.name} の形が読めない")
    return v
