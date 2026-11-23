#!/usr/bin/env python3
"""実装役（subagent_type の最後の `:` の後が autopilot-implementer で始まる）の起動を、dispatch が開いているときだけ通す
PreToolUse hook。prompt に書かれた spec のディレクトリ（state.json があるもの）のうち、phase が building・最後の dispatch を
閉じた handoff が無い・その dispatch の agent が起動する名前と同じ、の 3 つを満たすものが 1 つでもあれば何も出さない。
無ければ、prompt に spec が無い・state.json が読めない・途中の例外も含めて deny する。
想定するのは事故（dispatch の打ち忘れ）で、prompt に別の spec を書く・state.json を書き換える形は想定しない。
答えを出さずに終わった（import の失敗・終了コード 0 以外）ときの deny は、hooks.json の command が出す。"""
import json
import re
import sys
from pathlib import Path

START = re.compile(r"(?:^|(?<=[\s\"'`(\[<=,:]))[/~A-Za-z0-9_.-]")
WORD = re.compile(r"\w")


def short(name):
    return str(name or "").rsplit(":", 1)[-1]


def spec_dirs(prompt, cwd):
    """prompt の各行で、区切りの字の後から始まり state.json を持つディレクトリになる最長の部分を探す（空白・日本語を含むパスも拾う）。"""
    found = []
    for line in prompt.splitlines():
        line = line[:4000]
        for m in START.finditer(line):
            for end in range(len(line), m.start(), -1):
                if end < len(line) and WORD.match(line[end]):
                    continue
                tok = line[m.start():end].rstrip("/")
                if not tok:
                    continue
                p = Path(tok).expanduser()
                p = p if p.is_absolute() else Path(cwd) / p
                try:
                    ok = (p / "state.json").is_file()
                except OSError:
                    ok = False
                if ok:
                    if p not in found:
                        found.append(p)
                    break
    return found


def problem(d, name):
    """この spec で起動を通せない理由（通せるなら None）。"""
    try:
        s = json.loads((d / "state.json").read_text(encoding="utf-8"))
    except Exception as e:
        return f"{d} の state.json が読めない（{type(e).__name__}）"
    if s.get("phase") != "building":
        return f"{d} は building でない（{s.get('phase')}）"
    dispatches = s.get("dispatches") or []
    if not dispatches:
        return f"{d} に dispatch の記録が無い"
    n = len(dispatches) - 1
    if any(h.get("dispatch") == n for h in s.get("handoffs") or []):
        return f"{d} の最後の dispatch は handoff で閉じている"
    if short(dispatches[-1].get("agent")) != name:
        return f"{d} の最後の dispatch は {dispatches[-1].get('agent')} を指している（起動は {name}）"
    return None


def decide(payload):
    """(deny の理由 | None)。"""
    inp = payload.get("tool_input") or {}
    name = short(inp.get("subagent_type"))
    if not name.startswith("autopilot-implementer"):
        return None
    dirs = spec_dirs(str(inp.get("prompt") or ""), payload.get("cwd") or ".")
    if not dirs:
        return "prompt に spec のディレクトリ（state.json があるもの）が無いので、dispatch を確かめられない"
    reasons = []
    for d in dirs:
        why = problem(d, name)
        if why is None:
            return None
        reasons.append(why)
    return "; ".join(reasons)


def main():
    try:
        why = decide(json.loads(sys.stdin.buffer.read() or b"{}"))
    except Exception as e:
        why = f"判定の途中で例外が出た（{type(e).__name__}: {e}）"
    if why:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "deny",
            "permissionDecisionReason": f"実装役を起動できない: {why}。overnight.py dispatch <dir> --task T<n> を打ってから起動する"}},
            ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
