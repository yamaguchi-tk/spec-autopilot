#!/usr/bin/env python3
"""人の発言の時刻を、セッションごとの記録と、その worktree の git dir（セッションの id つき）に書く UserPromptSubmit hook。

autopilot.py の approve と resume は、この時刻と、記録した transcript の人の発言の行（origin が human）の時刻が、
spec.md の変更（block・done の後はその時刻、resume は wait）より後のときだけ通る。この hook は background の終わりの
知らせや subagent の報告でも動き、payload に出どころの欄が無いので、人の発言かは transcript の側で確かめる
（origin の無い transcript では止める。この hook の環境で SPEC_AUTOPILOT_TRUST_PROMPT_RECORD がちょうど 1 のときだけ、
記録に trust: true を書き、origin の無い transcript でも記録の時刻で確かめさせる。印は origin のある transcript でも、
origin の無い発言の行の時刻で効く。origin の付いた知らせ・subagent の報告だけでは通らない。hook の環境は Claude Code を
起動した側のもので、agent の Bash の環境変数は届かない）。
agent が事故で自分を承認し直すのを止めるためのもので、agent が意図してこのファイル・spec.md の mtime・
state.json を書けば通る（同じ権限のファイルなので、plugin の中では閉じられない）。
記録できないときは何もしない（発言は止めない）。
"""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


def main():
    try:
        import autopilot

        payload = json.loads(sys.stdin.buffer.read() or b"{}")
        now = time.time()
        f = autopilot.prompt_file(payload.get("session_id"))
        g = autopilot.git_dir(Path(payload.get("cwd") or "."))
        targets = [t for t in (f, g / autopilot.PROMPT_FILE if g else None) if t]
        for t in targets:
            rec = {"at": now, "session_id": payload.get("session_id"),
                   "transcript_path": payload.get("transcript_path")}  # approve・resume が人の発言を確かめ、done が異常を数える
            if os.environ.get("SPEC_AUTOPILOT_TRUST_PROMPT_RECORD") == "1":
                rec["trust"] = True
            t.parent.mkdir(parents=True, exist_ok=True)
            t.write_text(json.dumps(rec) + "\n", encoding="utf-8")
    except Exception:  # 記録できなくても、人の発言は止めない
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
