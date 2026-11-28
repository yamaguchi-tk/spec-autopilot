"""state.json の読み書き。autopilot.py・goal.py が使う（stages.py のほかの scripts を import しない下の層）。"""
import json
import os
import time


def load_state(d):
    return json.loads((d / "state.json").read_text(encoding="utf-8"))


def save_state(d, s):
    s["last_active_at"] = time.time()  # 中断の後の再開で、止まっていた時間を予算から外すために残す
    tmp = d / f".state.json.{os.getpid()}"  # 書きかけを Stop hook に読ませない（読めない spec は続行中に放される）
    tmp.write_text(json.dumps(s, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, d / "state.json")
