#!/usr/bin/env python3
"""目的の spec（大きさ L でよい）を、人が 1 回承認して、夜の間に子の spec へ分けて回すための記録と判定。

  autopilot.py approve <dir> --by .. --goal   目的として承認した記録を state.json の `goal` に残す（phase は discovery のまま）
  autopilot.py approve <dir> --by .. --queue --by-advisor   子の spec を、親の記録と相談役 2 本の記録で承認する（child_errors）

- 目的の spec は実装役の dispatch にも自走（building）にも入らない。Stop hook は discovery を放す
- 想定するのは事故（main が人の承認の無い子を回すこと）。承認の記録の書き換えは守らない
"""
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import advisor_approval  # noqa: E402
import autopilot as ap  # noqa: E402

PARENT = re.compile(r"^- 親 spec:[ \t]*(.*?)[ \t]*$", re.M)
PARENT_REQS = re.compile(r"^- 親の要件:[ \t]*(.*?)[ \t]*$", re.M)
REQ_ID = re.compile(r"R\d+")


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


def parse_reqs(text):
    """`R1、R2` の形の番号のリスト。形が違えば（空・末尾の読点・区切りが読点でない）None。"""
    ids = text.split("、")
    return ids if all(REQ_ID.fullmatch(x) for x in ids) else None


def parent_lines(d):
    """子の `## 制約` の (`- 親 spec:` の値のリスト, `- 親の要件:` の値のリスト)。コメントの中は読まない。"""
    text = ap.COMMENT_BLOCK.sub("", ap.section((d / "spec.md").read_text(encoding="utf-8"), "制約") or "")
    return PARENT.findall(text), PARENT_REQS.findall(text)


def parent_facts(parent):
    """親の (目的の承認の記録 or None, 親の要件の番号の集合 or None)。読めなければ None（親が無い・壊れた）。"""
    try:
        g = ap.load_state(parent).get("goal")
        g = g if isinstance(g, dict) and isinstance(g.get("scope_sha256"), str) else None
    except (OSError, ValueError):
        g = None
    try:
        body = ap.COMMENT_BLOCK.sub("", ap.section((parent / "spec.md").read_text(encoding="utf-8"), "要件") or "")
        return g, {m[0] for m in ap.REQ.findall(body)}
    except OSError:
        return g, None


def last_sibling_queued_at(d, name):
    """同じ親（`- 親 spec: name`）のほかの子のうち、最後に --queue で承認した時刻。無ければ 0。
    先の子のための相談の記録で、相談していない後の子が通らないように、相談の記録を数え始める時刻に使う。"""
    times = [0.0]
    for x in d.parent.iterdir():
        if x.resolve() == d.resolve() or not (x / "state.json").is_file() or not (x / "spec.md").is_file():
            continue
        try:
            at = ap.load_state(x).get("queued_at")
            if parent_lines(x)[0] == [name] and isinstance(at, (int, float)) and not isinstance(at, bool):
                times.append(float(at))
        except (OSError, ValueError):
            continue
    return max(times)


def child_errors(d, scope, session):
    """子の承認の条件（親が目的として承認されている・自走の範囲の節が親と同じ・`- 親の要件:` が全部親にある・相談役の条件）
    を満たさないものの一覧。空なら通る。足りない条件は全部挙げる。"""
    errors = []
    names, reqs_lines = parent_lines(d)
    name = names[0] if len(names) == 1 else None
    if name is None or name != Path(name).name or name in (".", ".."):
        errors.append(f"`## 制約` に `- 親 spec: <親の spec のディレクトリ名>` が 1 行要る（{len(names)} 行。子の承認は目的の spec の子だけ）")
        name = None
    reqs = parse_reqs(reqs_lines[0]) if len(reqs_lines) == 1 else None
    if reqs is None:
        errors.append("`## 制約` に `- 親の要件: R<n>、…` が 1 行要る（`R1、R2` の形。空・区切りの違い・複数行は受けない）")
    if name:
        g, ids = parent_facts(d.parent / name)
        if g is None:
            errors.append(f"親 spec {name} が目的として承認されていない（`approve --goal` の記録が無い）")
        elif g["scope_sha256"] != scope:
            errors.append("`## 自走の範囲` の節が親の承認のときと違う（子は親と同じ節だけを受ける）")
        if ids is None:
            errors.append(f"親 spec {name} の `## 要件` が読めない")
        elif reqs and (missing := [x for x in reqs if x not in ids]):
            errors.append(f"`- 親の要件:` に親 spec {name} の要件に無い番号がある: {'、'.join(missing)}")
    since = max((d / "spec.md").stat().st_mtime, last_sibling_queued_at(d, name) if name else 0.0)
    return errors + advisor_approval.reply_errors(session, since)
