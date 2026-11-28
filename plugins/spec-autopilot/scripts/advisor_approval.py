#!/usr/bin/env python3
"""夜の間の承認し直し（autopilot.py approve --by-advisor）の門。人の発言の代わりに、相談役 2 本の起動の記録を受ける。

- 受けるのは、人が一度承認した spec が block した後の承認し直しだけ（phase=blocked で、最後の承認のときの
  `## 自走の範囲` の節と今の節が同じ）。初回の承認（discovery・queued）と、範囲を変える承認し直しは人の返事が要る
- 条件は、承認の起点（consent.origin。lint が通した中身なら lint が初めて見た時刻、でなければ spec.md の最後の変更。block の後ならその時刻）より後に、このセッションで fable-advisor が起動し、その後に
  advice-checker が起動していて、fable-advisor の最後の返答に `承認: 可`、advice-checker の最後の返答に
  `判定: 反証なし（確かめられない 0 / <n>）` の行が、行の先頭が `承認:`・`判定:` の行のうち
  ちょうど 1 本としてあること。許可の形はこの 1 つだけで、ほかは全部止める
- 返答は subagent の transcript の最後の assistant の行の text か、SubagentHandback の `input.message`
- 想定するのは事故（main が人の返事も相談役の検証も無いまま承認し直すこと）。subagent の記録の偽造は守らない
"""
import glob
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ladder  # noqa: E402

ADVISOR, CHECKER = "fable-advisor", "advice-checker"  # 既定の名前（BY_PREFIX・エラーの文言の呼び名）
# 数える記録の名前は、相談・検証の段の表（ladder.ADVISORS）の agent の名前だけ
NAMES = {label: {agent for agent, _, _ in ladder.ADVISORS[role].values()} for label, role in ((ADVISOR, "advisor"), (CHECKER, "checker"))}
BY_PREFIX = f"相談役（{ADVISOR}・{CHECKER} 反証なし）: "
COMMENT_BLOCK = re.compile(r"<!--.*?-->", re.S)
READ_ERRORS = (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError)


def since_of(s, spec_mtime):  # spec_mtime は承認の起点（consent.origin）
    """承認の門が「いつより後」を見るか。(時刻, 何の後か)。承認の起点（consent.origin）を、block・done の時刻が超えればそれ。"""
    since, what = spec_mtime, "承認の起点（lint が中身を初めて見た時刻か、lint を通していなければ spec.md の最後の変更）"
    if s.get("phase") == "blocked" and float((s.get("blocked") or {}).get("at", 0)) > since:
        since, what = float(s["blocked"]["at"]), "block"
    if s.get("phase") == "done":  # done の前の発言では戻さない。done の時刻が読めなければ戻さない
        done_at = s.get("done_at")
        if isinstance(done_at, bool) or not isinstance(done_at, (int, float)):
            sys.exit("done の時刻（state.json の done_at）が読めないので approve しない")
        if done_at > since:
            since, what = float(done_at), "done"
    return since, what


def scope_sha(text):
    """`## 自走の範囲` の節の中身のハッシュ。コメントと前後の空白は外す。"""
    return hashlib.sha256(COMMENT_BLOCK.sub("", text or "").strip().encode("utf-8")).hexdigest()


def human_errors(s, scope):
    """相談役では承認し直せない形（人の返事が要る）の ERROR。phase と自走の範囲だけを見る（相談役の条件は reply_errors）。"""
    if s.get("phase") != "blocked":
        return [f"相談役で承認し直せるのは、人が承認した spec の block の後だけ（phase={s.get('phase')}）。人の返事が要る"]
    if not s.get("scope_sha256"):
        return ["最後の承認のときの自走の範囲の節の記録が無い（この版より前に承認した spec）。人の返事が要る"]
    if s["scope_sha256"] != scope:
        return ["`## 自走の範囲` の節が最後の承認のときと違う（範囲を変える承認し直し）。人の返事が要る"]
    return []


def reply_of(rows):
    """最後の assistant の行（host は text・tool_use ごとに 1 行を書く）の返答。text の文か、SubagentHandback の input.message。"""
    for row in reversed(rows):
        if row.get("type") != "assistant" or row["message"].get("model") == "<synthetic>":
            continue
        content = row["message"].get("content")
        blocks = [{"type": "text", "text": content}] if isinstance(content, str) else content
        texts = [b["text"] for b in blocks if b.get("type") == "text" and isinstance(b.get("text"), str)]
        texts += [b["input"]["message"] for b in blocks if b.get("type") == "tool_use" and b.get("name") == "SubagentHandback"
                  and isinstance(b.get("input"), dict) and isinstance(b["input"].get("message"), str)]
        if texts:
            return "\n".join(texts)
    return ""


def _written_since(path, since):
    """path が since 以後に書かれたか。mtime が読めなければ、後に書かれたとして扱う。"""
    try:
        return path.stat().st_mtime >= since
    except OSError:
        return True


def launches(session, since):
    """session で since 以後に起動した相談役・検証役（段の表の名前）の [(ADVISOR か CHECKER, 起動の時刻, 最後の返答)]。
    記録は overnight.launches と同じ <config>/projects/*/<session>/subagents/。形が読めない記録は、since の後に
    書かれたなら ValueError（照合できないまま通さない）、前なら読み飛ばす。"""
    home = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    out = []
    for meta in home.glob(f"projects/*/{glob.escape(session)}/subagents/*.meta.json"):
        try:
            name = json.loads(meta.read_text(encoding="utf-8"))["agentType"].split(":")[-1]
        except READ_ERRORS:
            if _written_since(meta, since):
                raise ValueError(f"{meta.name} の記録が読めない") from None
            continue
        role = next((r for r, names in NAMES.items() if name in names), None)  # 段の表に無い名前は数えない
        if role is None:
            continue
        log = meta.with_name(meta.name[: -len(".meta.json")] + ".jsonl")
        try:
            rows = [json.loads(x) for x in log.read_bytes().decode("utf-8").split("\n") if x.strip()]  # "\n" だけで割る（本文の U+2028 で割らない）
            start = datetime.fromisoformat(rows[0]["timestamp"].replace("Z", "+00:00")).timestamp()
            if start >= since:
                out.append((role, start, reply_of(rows)))
        except READ_ERRORS:
            if _written_since(log if log.exists() else meta, since):
                raise ValueError(f"{log.stem} の記録が読めない") from None
    return out


def _lines_of(reply, head):
    """返答の中の、行の先頭が head の行（前後の空白は外す）。"""
    return [x for x in (y.strip() for y in reply.splitlines()) if x.startswith(head)]


def reply_errors(session, since):
    """相談役の条件（起動の順と 2 つの行）を満たさないものの一覧。空なら通る。phase と自走の範囲は見ない（human_errors）。"""
    if not session:
        return ["セッションの id（CLAUDE_CODE_SESSION_ID）が無いので、このセッションの相談役の記録を探せない"]
    try:
        found = launches(session, since)
    except ValueError as e:
        return [str(e)]
    last = {n: max((x for x in found if x[0] == n), key=lambda x: x[1], default=None) for n in (ADVISOR, CHECKER)}
    errors = [f"{n} の起動の記録が、承認の起点（lint が中身を初めて見た時刻か spec.md の最後の変更。block の後なら block）より後に無い" for n in (ADVISOR, CHECKER) if not last[n]]
    if all(last.values()) and last[CHECKER][1] <= last[ADVISOR][1]:
        errors.append(f"{CHECKER} の起動が {ADVISOR} の起動より前（{ADVISOR} の推奨を {CHECKER} が検証した順になっていない）")
    if last[ADVISOR]:
        approvals = _lines_of(last[ADVISOR][2], "承認:")
        if len(approvals) != 1:
            errors.append(f"{ADVISOR} の最後の返答の `承認:` の行が {len(approvals)} 本（ちょうど 1 本の `承認: 可` が要る）")
        elif approvals[0] != "承認: 可":
            errors.append(f"{ADVISOR} の最後の返答に `承認: 可` の行が無い（{approvals[0]}）")
    if last[CHECKER]:
        judged = _lines_of(last[CHECKER][2], "判定:")
        if len(judged) != 1:
            errors.append(f"{CHECKER} の最後の返答の `判定:` の行が {len(judged)} 本（ちょうど 1 本の `判定: 反証なし（確かめられない 0 / <n>）` が要る）")
        elif not (m := re.fullmatch(r"判定: (反証あり|反証なし)(.*)", judged[0])):
            errors.append(f"{CHECKER} の判定が `判定: 反証なし（確かめられない 0 / <n>）` の形でない（{judged[0]}）")
        elif m.group(1) == "反証あり":
            errors.append(f"{CHECKER} の判定が反証あり")
        elif not re.fullmatch(r"（確かめられない 0 / \d+）", m.group(2)):
            errors.append(f"{CHECKER} の判定が `判定: 反証なし（確かめられない 0 / <n>）` の形でない（確かめられない 1 以上か、形が違う: {judged[0]}）")
    return errors
