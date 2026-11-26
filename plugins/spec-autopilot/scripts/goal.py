#!/usr/bin/env python3
"""目的の spec（大きさ L でよい）を、人が 1 回承認して、夜の間に子の spec へ分けて回すための記録と判定。

  autopilot.py approve <dir> --by .. --goal   目的として承認した記録を state.json の `goal` に残す（phase は discovery のまま）

- 目的の spec は実装役の dispatch にも自走（building）にも入らない。Stop hook は discovery を放す
- 想定するのは事故（main が人の承認の無い子を回すこと）。承認の記録の書き換えは守らない
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import autopilot as ap  # noqa: E402


def record(d, by, scope):
    """目的として承認した記録（時刻・要約・自走の範囲の節のハッシュ）を足す。書く直前に state.json を読み直し、goal のキーだけを変える。"""
    s = ap.load_state(d)
    s["goal"] = {"at": time.time(), "by": by, "scope_sha256": scope}
    ap.save_state(d, s)


def refuse_mix(a):
    """--goal は人の発言で 1 回の承認。--queue・--by-advisor（子の承認）とは一緒に使わせない。"""
    if a.goal and (a.queue or a.by_advisor):
        sys.exit("--goal は --queue・--by-advisor と一緒に使えない（目的の承認は人の発言で 1 回）")


def approve(d, by, scope, warnings):
    """approve --goal。人の発言の門と lint は呼び出し側が通した後に呼ぶ。壁打ち中（discovery）の spec だけ受ける。"""
    s = ap.load_state(d)
    if s.get("phase") != "discovery":
        ap.refuse(s, "--goal は壁打ち中（discovery）の spec だけ受ける")
    record(d, by, scope)
    return ap.report([], warnings, "goal: 目的として承認した（phase は discovery のまま。子の spec は main が分けて --queue で承認する）")
