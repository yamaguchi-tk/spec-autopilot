#!/usr/bin/env python3
"""夜の間の承認し直し（autopilot.py approve --by-advisor）の門。人の発言の代わりに、相談役 2 本の起動の記録を受ける。

- 受けるのは、人が一度承認した spec が block した後の承認し直しだけ（phase=blocked で、最後の承認のときの
  `## 自走の範囲` の節と今の節が同じ）。初回の承認（discovery・queued）と、範囲を変える承認し直しは人の返事が要る
- 条件は、spec.md の最後の変更（block の後ならその時刻）より後に、このセッションで fable-advisor が起動し、その後に
  advice-checker が起動していて、fable-advisor の最後の返答に `承認: 可`、advice-checker の最後の返答に
  `判定: 反証なし（確かめられない 0 / <n>）` の行があること。許可の形はこの 1 つだけで、ほかは全部止める
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

ADVISOR, CHECKER = "fable-advisor", "advice-checker"
BY_PREFIX = f"相談役（{ADVISOR}・{CHECKER} 反証なし）: "
COMMENT_BLOCK = re.compile(r"<!--.*?-->", re.S)
READ_ERRORS = (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError)


def since_of(s, spec_mtime):
    """承認の門が「いつより後」を見るか。(時刻, 何の後か)。spec.md の最後の変更を、block・done の時刻が超えればそれ。"""
    since, what = spec_mtime, "spec.md の最後の変更"
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


def launches(session, since):
    """session で since 以後に起動した fable-advisor・advice-checker の [(名前, 起動の時刻, 最後の返答)]。
    記録は overnight.launches と同じ <config>/projects/*/<session>/subagents/。形が読めない記録は、since の後に
    書かれたなら ValueError（照合できないまま通さない）、前なら読み飛ばす。"""
    home = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    out = []
    for meta in home.glob(f"projects/*/{glob.escape(session)}/subagents/*.meta.json"):
        try:
            name = json.loads(meta.read_text(encoding="utf-8"))["agentType"].split(":")[-1]
        except READ_ERRORS:
            continue
        if name not in (ADVISOR, CHECKER):
            continue
        log = meta.with_name(meta.name[: -len(".meta.json")] + ".jsonl")
        try:
            rows = [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines() if x.strip()]
            start = datetime.fromisoformat(rows[0]["timestamp"].replace("Z", "+00:00")).timestamp()
            if start >= since:
                out.append((name, start, reply_of(rows)))
        except READ_ERRORS:
            try:
                late = (log if log.exists() else meta).stat().st_mtime >= since
            except OSError:
                late = True
            if late:
                raise ValueError(f"{log.stem} の記録が読めない") from None
    return out


def reply_errors(session, since):
    """相談役の条件（起動の順と 2 つの行）を満たさないものの一覧。空なら通る。phase と自走の範囲は見ない（human_errors）。"""
    if not session:
        return ["セッションの id（CLAUDE_CODE_SESSION_ID）が無いので、このセッションの相談役の記録を探せない"]
    try:
        found = launches(session, since)
    except ValueError as e:
        return [str(e)]
    last = {n: max((x for x in found if x[0] == n), key=lambda x: x[1], default=None) for n in (ADVISOR, CHECKER)}
    errors = [f"{n} の起動の記録が、spec.md の最後の変更（block の後なら block）より後に無い" for n in (ADVISOR, CHECKER) if not last[n]]
    if all(last.values()) and last[CHECKER][1] <= last[ADVISOR][1]:
        errors.append(f"{CHECKER} の起動が {ADVISOR} の起動より前（{ADVISOR} の推奨を {CHECKER} が検証した順になっていない）")
    if last[ADVISOR]:
        lines = [x.strip() for x in last[ADVISOR][2].splitlines()]
        verdicts = [m.group(1) for m in map(re.compile(r"承認: (可|否)").fullmatch, lines) if m]
        if not verdicts or verdicts[-1] != "可":
            errors.append(f"{ADVISOR} の最後の返答に `承認: 可` の行が無い（{'承認: ' + verdicts[-1] if verdicts else '承認: の行が無い'}）")
    if last[CHECKER]:
        lines = [x.strip() for x in last[CHECKER][2].splitlines()]
        judged = [m for m in map(re.compile(r"判定: (反証あり|反証なし)(.*)").fullmatch, lines) if m]
        if not judged:
            errors.append(f"{CHECKER} の最後の返答に `判定:` の行が無い")
        elif judged[-1].group(1) == "反証あり":
            errors.append(f"{CHECKER} の判定が反証あり")
        elif not re.fullmatch(r"（確かめられない 0 / \d+）", judged[-1].group(2)):
            errors.append(f"{CHECKER} の判定が `判定: 反証なし（確かめられない 0 / <n>）` の形でない（確かめられない 1 以上か、形が違う: {judged[-1].group(0)}）")
    return errors
