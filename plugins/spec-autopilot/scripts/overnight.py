#!/usr/bin/env python3
"""spec-autopilot の PR の後のループ（範囲がマージ以上の spec。手順は references/after-pr.md）。

使い方:
  overnight.py dispatch <dir> --task T<n>...        実装役に渡す時点の HEAD を記録し、起動する実装役の段の agent を最後の行に出す（渡すたびに打つ）
  overnight.py agent <dir> --role impl|review [--task T<n>...]  今の段の agent の名前（実装役は受け持つ要件の段の最大）
  overnight.py raise <dir> --role review --reason 判定が決まらない  評価役の段を 1 つ上げる（実装役は review の巡で自動）
  overnight.py handoff <dir> --task T<n>...         実装役の報告を確かめ、最後の dispatch を閉じる（開いていれば、その時点から commit が
                                                    増えた・dispatch が指した実装役が定義の model と effort で動いた・commit していないコードが無い・タスクが [x]。
                                                    閉じた後は同じ HEAD で記録済み、HEAD が動いた後は〔rebase に限らず〕増分も起動も見ない）。review は最後の dispatch を今の HEAD で閉じた後だけ受ける
  overnight.py await <dir> --kind ci --pr <n>       CI を待つ（background の Bash で 1 本だけ起動する）
  overnight.py await <dir> --kind deploy   最後のマージの commit で、spec の `- デプロイの確かめ:` の workflow を全部待つ
      1 本でも失敗したら、すぐに exit 1。失敗のログが flake の型（run の 1 回目）なら exit 3 で返し、再実行は main が打つ。
      全部が通れば exit 0（run が 0 本のうちは通ったとみなさない）。上限（--timeout-min）を過ぎたら park として exit 2。
      phase は building のまま。待ちの記録は spec の await.json と awaits.jsonl に書き、state.json には書かない。
      Stop hook は、このプロセスが host の子孫として生きていて期限の内にある間だけ放す。待った時間は予算に数えない
  overnight.py await <dir> --kind review --pr <n>   レビューの承認を待つ（gh pr merge が承認の要件で断られたときだけ。既定の上限 600 分）
  overnight.py ready <dir> --pr <n> [--rollback]    マージの前に、評価役が見た HEAD と PR の head が同じかを確かめる。本番が壊れたままなら、
                                                    spec のマージを戻す PR（--rollback）だけを受ける
  overnight.py merged <dir> --pr <n> [--rollback --reason <理由>]   マージを gh で確かめて記録する（冪等）。マージ後の予算はここから数える
  overnight.py qa <dir> --evidence <file> --smoke pass|fail|unknown   デプロイの後に実環境で QA を回した証拠と、変えない挙動の smoke を記録する
  overnight.py notify <dir>                         spec の `- 通知:` の先に、今の状態と本番の状態を 1 行で知らせる（done と block も出す）
  overnight.py park <dir> --kind merge|deploy|qa|ci|other --op <操作> --reason <理由> [--req R<n>]
                                                    範囲の外の操作・満たせない要件を、止めずに積む
  overnight.py report <dir>                         朝の報告（done も最後に出す）

範囲の行は許可リストの値だけを読む（自由文は解釈しない）。読めない値は止める側（ERROR・block）に倒す。
"""
import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import autopilot  # noqa: E402
import ladder  # noqa: E402
import stages  # noqa: E402

SCOPE_SECTION = "自走の範囲"
FULL, MERGE, PR = "マージ・デプロイ・QA まで", "マージまで", "PR まで"
SCOPES = (FULL, MERGE, PR)
SCOPE_KEYS = ("範囲", "QA の環境", "QA の書き込み先", "デプロイの起動", "デプロイの確かめ", "ロールバック", "AWS の profile")
REQUIRED_FOR_FULL = ("QA の環境", "QA の書き込み先", "デプロイの起動", "デプロイの確かめ", "ロールバック")  # 空なら ERROR
AUTO_DEPLOY = "マージで自動"
ROUND_KEYS = ("merges", "merged_at", "paused_at_merge", "parked", "qa_runs", "handoffs", "dispatches", "lenses",
              "rolled_back")
OPTIONAL_KEYS = ("通知",)  # 無くてよい行（無ければ なし）
NOTIFY = ("デスクトップ", "Slack の DM", "なし")
PROFILE = re.compile(r"^[A-Za-z0-9_.-]+$")
SCOPE_ROW = re.compile(r"^- (" + "|".join(map(re.escape, SCOPE_KEYS + OPTIONAL_KEYS)) + r"):[ \t]*(.*?)[ \t]*$", re.M)
SMOKE = ("pass", "fail", "unknown")  # unknown は fail と同じに扱う
BROKEN, UNKNOWN, CONFIRMED, RESTORED = "壊れたまま", "分からない", "確かめた", "戻して確かめた"
POST_BUDGET = re.compile(r"^- マージ後の予算:\s*(\d+)\s*分\s*$", re.M)
PARK_KINDS = ("merge", "deploy", "qa", "ci", "other")
OK = ("pass", "success")  # 通ったものとして数える値（許可リスト。ほかは失敗）
SKIP = ("skipping", "skipped", "neutral")  # 走らなかったもの。これだけでは通ったとみなさない
PENDING = ("pending", "queued", "in_progress", "waiting", "requested", "expected")
FLAKE = re.compile(r"Error acquiring the state lock|PreconditionFailed|The runner has received a shutdown signal"
                   r"|lost communication with the server|The hosted runner encountered an error")
RUN_ID = re.compile(r"/actions/runs/(\d+)")
MAX_DEPLOY_FIXES = autopilot.MAX_REWORKS  # デプロイの失敗を直す PR は作り直しと同じ回数まで。3 回目の失敗で積む（references/after-pr.md の 3）
DEFAULT_TIMEOUT = {"ci": 90, "deploy": 60, "review": 600}
GRACE_SEC = 300  # Stop hook が await を生きているとみなす、上限の後の余裕（最後の poll と後始末の分）
AWAIT_FILE, AWAITS_LOG = "await.json", "awaits.jsonl"


# --- 範囲（lint と check が読む） ---

def scope_rows(text):
    """自走の範囲の節の行を {キー: 値} で返す。節が無ければ None。"""
    body = autopilot.section(text, SCOPE_SECTION)
    if body is None:
        return None
    return dict(SCOPE_ROW.findall(autopilot.COMMENT_BLOCK.sub("", body)))


def budgets(text):
    """(予算, マージ後の予算) を、制約の節からコメントを除いて読む（lint・approve・preflight の読み手はこれだけ）。
    予算が無ければ (None, None)。マージ後の予算が無ければ予算と同じ。"""
    body = autopilot.COMMENT_BLOCK.sub("", autopilot.section(text, "制約") or "")
    m, post = autopilot.BUDGET.search(body), POST_BUDGET.search(body)
    if not m:
        return None, None
    return int(m.group(1)), int(post.group(1)) if post else int(m.group(1))


REVERT = "revert の PR をマージし、デプロイの完了を確かめる"
ROLLBACK_CMD = re.compile(r"^コマンド:[ \t]*(\S.*?)[ \t]*$")


def rollback_cmd(text):
    """spec の `- ロールバック:` がコマンドの宣言なら、そのコマンド。revert の PR（既定の文）か読めなければ None。"""
    m = ROLLBACK_CMD.match((scope_rows(text) or {}).get("ロールバック") or "")
    return m.group(1) if m else None


def scope_lint(text):
    """(errors, warnings)。"""
    rows = scope_rows(text)
    if rows is None:
        return [f"spec.md に「## {SCOPE_SECTION}」の節が無い（{'・'.join(SCOPE_KEYS)} の 6 行）"], []
    errors = [f"自走の範囲に `- {k}:` の行が無い" for k in SCOPE_KEYS if k not in rows]
    keys = [k for k, _ in SCOPE_ROW.findall(autopilot.COMMENT_BLOCK.sub("", autopilot.section(text, SCOPE_SECTION)))]
    errors += [f"自走の範囲に `- {k}:` が 2 本以上ある（1 本にする）" for k in dict.fromkeys(keys) if keys.count(k) > 1]
    scope = rows.get("範囲")
    if scope is not None and scope not in SCOPES:
        errors.append(f"自走の範囲の `- 範囲:` は「{'」「'.join(SCOPES)}」のどれか（今は「{scope}」）")
    if rows.get("通知") is not None and rows["通知"] not in NOTIFY:
        errors.append(f"自走の範囲の `- 通知:` は「{'」「'.join(NOTIFY)}」のどれか（今は「{rows['通知']}」）")
    if rows.get("AWS の profile") is not None and rows["AWS の profile"] != "なし" and not PROFILE.match(rows["AWS の profile"]):
        errors.append(f"自走の範囲の `- AWS の profile:` は profile の名前か「なし」（今は「{rows['AWS の profile']}」）")
    back = rows.get("ロールバック")
    if back and back != REVERT and not ROLLBACK_CMD.match(back):
        errors.append(f"自走の範囲の `- ロールバック:` は「{REVERT}」か「コマンド: <1 行のコマンド>」のどちらか（今は「{back}」）")
    start = rows.get("デプロイの起動")
    if start and start != AUTO_DEPLOY and not ROLLBACK_CMD.match(start):
        errors.append(f"自走の範囲の `- デプロイの起動:` は「{AUTO_DEPLOY}」か「コマンド: <1 行のコマンド>」のどちらか（今は「{start}」）")
    warnings = []
    deployed = stages.deployed_reqs(autopilot, text)
    if scope in (PR, MERGE):  # 夜の間に届かないデプロイ後の要件は、承認のときに人が見る
        errors += [f"範囲が「{scope}」なので、デプロイ後の {r} は夜の間に確かめられない。"
                   f"`- unverified の承認: {r}（<理由>）` を書くか、範囲を「{FULL}」にする"
                   for r in deployed if not stages.approved(autopilot, text, r)]
    if scope == FULL:  # デプロイ後の要件が無ければ、マージ後の QA のループを通らない。マージで起きるデプロイの失敗は拾うので、起動と確かめは要る
        need = REQUIRED_FOR_FULL if deployed else ("QA の書き込み先", "デプロイの起動") + (
            () if start and ROLLBACK_CMD.match(start) else ("デプロイの確かめ",))
        errors += [f"範囲が「{FULL}」なので `- {k}:` を書く" for k in need if k in rows and not rows[k]]
    if scope == FULL and deployed:
        if start and ROLLBACK_CMD.match(start):
            warnings.append(f"デプロイの起動が「{AUTO_DEPLOY}」でない（{start}）。夜の間に agent がこのコマンドを打つ。"
                            "global の規則が 1 操作ごとの確認を求める形なら、その起動は park になる。承認の前に人に示す")
    return errors, warnings


def scope_of(d):
    """範囲の値。節の無い旧い spec は PR まで（今までの完了条件）として扱う。"""
    rows = scope_rows((d / "spec.md").read_text(encoding="utf-8"))
    return PR if rows is None else rows.get("範囲")


def head(root):
    out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True)
    return out.stdout.strip() if out.returncode == 0 else None


def contains(root, ancestor, tip):
    """ancestor が tip に含まれる。読めなければ False。"""
    if not ancestor or not tip:
        return False
    return subprocess.run(["git", "merge-base", "--is-ancestor", ancestor, tip], cwd=root,
                          capture_output=True).returncode == 0


def only_tests_and_docs(root, a, b):
    try:
        changed = autopilot.git_lines(root, "diff", "--name-only", f"{a}..{b}")
    except RuntimeError:
        return False
    return all(autopilot.TEST_PATH.search(f) or autopilot.NOT_CODE.search(f) for f in changed)


def scope_errors(d, s):
    """範囲がマージ以上の spec の完了条件（check が読む。gh は呼ばず、state と git と待ちの記録だけを読む）。"""
    scope = scope_of(d)
    if scope not in (FULL, MERGE):
        return []
    root, parked = autopilot.repo_root(d), exempt_kinds(d, s)
    merges = s.get("merges") or []
    errors = production_errors(d, s)
    if "merge" not in parked and not (merges and contains(root, head(root), merges[-1].get("head"))):
        errors.append("範囲がマージを含むのに、今の HEAD を含むマージを確かめていない（references/after-pr.md。"
                      "マージしたら overnight.py merged <dir> --pr <n>、できないなら overnight.py park --kind merge）")
    late = stages.deployed_reqs(autopilot, (d / "spec.md").read_text(encoding="utf-8"))
    smoke = [] if not deploy_stage(d) or late or deploy_smoke(d, s) != (True, None) else [
        "この夜にデプロイが落ちたのに、最後に落ちた後の smoke を記録していない（spec の変えない挙動を本番で確かめて "
        "overnight.py qa <dir> --evidence <file> --smoke <pass|fail|unknown>。fail でも戻さずに積む）"]
    if not deploy_stage(d) or "deploy" in parked or len(errors) > len(production_errors(d, s)):
        return errors + (smoke if "deploy" in parked and len(errors) == len(production_errors(d, s)) else [])
    deployed = deploys_of_last_merge(d, s)
    if not deployed and deploy_exhausted(d, s):
        return errors + [f"デプロイの失敗を直す PR が {MAX_DEPLOY_FIXES} 回とも通らなかった（上限）。直しを続けずに "
                         "overnight.py park --kind deploy（--reason に、main にデプロイされていない変更が残ることを書く）"]
    if not deployed:  # デプロイ後の要件が無い spec も、デプロイの失敗を拾うために待つ
        return errors + ["範囲がデプロイを含むのに、最後のマージの commit のデプロイの成功を確かめていない"
                         "（overnight.py await <dir> --kind deploy。落ちたら references/after-pr.md の 3。"
                         "できないなら overnight.py park --kind deploy）"]
    if not late:
        return errors + smoke
    if "qa" not in parked and not [q for q in s.get("qa_runs") or [] if float(q["at"]) > max(deployed)]:
        errors.append("デプロイの後の実環境の QA を記録していない（QA を回して qa.md を書き直し、"
                      "overnight.py qa <dir> --evidence <file>。できないなら overnight.py park --kind qa）")
    return errors


def deploy_stage(d):
    """デプロイの段を通るか: 範囲が「マージ・デプロイ・QA まで」で、デプロイ後の要件があるか、起動がコマンドの宣言でない
    （マージで本番が変わる。読めない値もこちら）。コマンドで起動しデプロイ後の要件が無い spec は、夜の間にデプロイを起こさない。"""
    text = (d / "spec.md").read_text(encoding="utf-8")
    if scope_of(d) != FULL:
        return False
    return bool(stages.deployed_reqs(autopilot, text)) or not ROLLBACK_CMD.match((scope_rows(text) or {}).get("デプロイの起動") or "")


def deploy_parked(s):
    """最後のマージの後に、要件を名指ししない deploy の park を積んだか。"""
    n = len(s.get("merges") or [])
    return any(p.get("kind") == "deploy" and not p.get("req") and p.get("merges", 0) == n for p in s.get("parked") or [])


def failed_deploys(d, s):
    """最後のデプロイの success の後に、デプロイが failure になったマージの数（マージの順。sha ごとに最後の結果を採る）。
    success だけが 0 に戻す。flake・error・timeout・記録の無いマージは数えず、0 にも戻さない。"""
    last = {}
    for a in awaits(d, s):
        if a.get("kind") == "deploy" and a.get("result") in ("success", "failure"):
            last[a.get("sha")] = a["result"]
    n = 0
    for m in s.get("merges") or []:
        result = last.get(m.get("sha"))
        n = 0 if result == "success" else n + 1 if result == "failure" else n
    return n


def deploy_exhausted(d, s):
    """デプロイの失敗の直しが上限に当たった（ready が次の直しを拒み、check が積むよう言う。止める側が読む唯一の述語）。"""
    return failed_deploys(d, s) > MAX_DEPLOY_FIXES


def deploy_smoke(d, s):
    """この夜のマージのデプロイが 1 度でも落ちたか（failure の記録。後で直して成功しても数える）と、
    最後に落ちた後の smoke の値（無ければ None）。"""
    shas = {m.get("sha") for m in s.get("merges") or [] if m.get("sha")}
    failed = [a["at"] for a in awaits(d, s) if a.get("kind") == "deploy" and a.get("sha") in shas and a.get("result") == "failure"]
    if not failed:
        return False, None
    smokes = [(float(q["at"]), q["smoke"]) for q in s.get("qa_runs") or [] if "smoke" in q and float(q["at"]) > max(failed)]
    return True, max(smokes)[1] if smokes else None


def deploy_view(d, s):
    """デプロイ後の要件が無い spec の朝の報告の「本番:」の値（production() が None のとき）。
    積んだことを「デプロイが起きなかった」と読むのは、起動がコマンドのときだけ（マージで自動なら、落ちて積んだ）。"""
    merges = s.get("merges") or []
    by_command = bool(ROLLBACK_CMD.match((scope_rows((d / "spec.md").read_text(encoding="utf-8")) or {}).get("デプロイの起動") or ""))
    if not deploy_stage(d) or not merges or (by_command and deploy_parked(s)):
        return None
    sha = merges[-1].get("sha")
    results = [a.get("result") for a in awaits(d, s) if a.get("kind") == "deploy" and a.get("sha") == sha]
    failed, smoke = deploy_smoke(d, s)
    if "success" in results:
        return "デプロイした（" + (f"落ちた後の smoke: {smoke or '記録なし'}）" if failed else "本番の中身は確かめていない）")
    if "failure" in results:
        return f"デプロイが失敗したまま（{(sha or '')[:8]}。" + (f"smoke: {smoke}）" if smoke else "本番の中身は確かめていない）")
    return "デプロイを確かめていない"


def deploy_workflows(text):
    """spec の `- デプロイの確かめ:` に `、` で並べた、デプロイの成功・失敗を決める workflow の名前。"""
    return [w.strip() for w in ((scope_rows(text) or {}).get("デプロイの確かめ") or "").split("、") if w.strip()]


def deploys_of_last_merge(d, s):
    merges = s.get("merges") or []
    if not merges:
        return []
    return [a["at"] for a in awaits(d, s) if a.get("kind") == "deploy" and a.get("result") == "success"
            and a.get("sha") == merges[-1].get("sha")]


def stage_errors(d, s, rows, stage="all"):
    """段ごとの証拠の要求（stages.check）を、検査の時点・積んだ要件・最後のマージとそのデプロイの時刻で当てる。"""
    parked = {p.get("req") for p in parked_ops(d, s) if p.get("req")}
    deployed = deploys_of_last_merge(d, s)
    merges = s.get("merges") or []
    errors = stages.check(autopilot, d, rows, parked, max(deployed) if deployed else None, stage,
                          merges[-1].get("sha") if merges else None, s.get("reviews") or [], s.get("approved_at"))
    if going_back(s):
        late = stages.deployed_reqs(autopilot, (d / "spec.md").read_text(encoding="utf-8"))
        errors += [f"{rid} は段がデプロイ後で、本番は spec のマージを戻した後なので pass にしない（unverified にして park で積む）"
                   for rid, (result, _) in rows.items() if result == "pass" and rid in late]
    return errors


def going_back(s):
    """最後に本番の中身を変えた記録（マージ・コマンドでの戻し）が戻しか。戻す PR のマージは、デプロイの前でも戻しの側に数える。"""
    changes = [(float(m.get("at", 0)), bool(m.get("rollback"))) for m in s.get("merges") or []]
    changes += [(float(r.get("at", 0)), True) for r in s.get("rolled_back") or []]
    return bool(changes) and max(changes)[1]


def production(d, s):
    """本番の状態。デプロイ後の要件がある「マージ・デプロイ・QA まで」の spec だけ導く（ほかは None）。
    マージ・デプロイの終わり・コマンドでの戻し・smoke を時刻の順に 1 回読む（後から消えない印は持たない）。
    - マージ: 確かめはやり直し（分からない）。壊れたままは抜けない。ただし、デプロイの起動が `コマンド: <cmd>` の spec で、
      そのマージの後（次のマージの前）に要件を名指ししない deploy の park を積んだ前へ進めるマージは、本番を変えていないので数えない。
      起動がそれ以外の値（読めない値・注釈つきの「マージで自動」を含む）なら、マージで本番が変わるものとして数える。
      戻すマージは、起動の種類によらず数える（前の smoke の pass を、戻した本番の確かめに数えないため）。
    - デプロイの終わり: 成功のときだけ、次の smoke の pass を確かめたにする。壊れたままを抜けるのは、壊れた後のマージのデプロイの成功だけ。
    - デプロイの失敗を戻さずに積んだ（最後のマージのデプロイが failure で終わった後の、要件を名指ししない deploy の park。
      戻すマージを除く）: 届いた分の本番を、次の smoke の pass で確かめたにする。壊れたままは抜けない。
    - コマンドでの戻し: 分からない（戻した本番として smoke を待つ）。
    - smoke の fail・unknown: 壊れたまま。
    確かめたは、最後に中身を変えた記録が戻し（going_back）なら戻して確かめた。この夜に何も無ければ None。"""
    text = (d / "spec.md").read_text(encoding="utf-8")
    if scope_of(d) != FULL or not stages.deployed_reqs(autopilot, text):
        return None
    merges = s.get("merges") or []
    at_of = {m.get("sha"): float(m.get("at", 0)) for m in merges if m.get("sha")}
    by_command = bool(ROLLBACK_CMD.match((scope_rows(text) or {}).get("デプロイの起動") or ""))
    parked = {p.get("merges") for p in s.get("parked") or [] if p.get("kind") == "deploy" and not p.get("req")}
    events = [(float(m.get("at", 0)), "merge", m) for n, m in enumerate(merges, 1)
              if not (by_command and n in parked) or m.get("rollback")]
    events += [(a["at"], "deploy", a) for a in awaits(d, s) if a.get("kind") == "deploy" and a.get("sha") in at_of]
    events += [(float(r["at"]), "rolled", r) for r in s.get("rolled_back") or []]
    if not events:
        return None
    events += [(float(p["at"]), "parked", merges[p["merges"] - 1]) for p in s.get("parked") or []
               if p.get("kind") == "deploy" and not p.get("req") and 0 < p.get("merges", 0) <= len(merges) and "at" in p]
    events += [(float(q["at"]), "smoke", q.get("smoke")) for q in s.get("qa_runs") or [] if "smoke" in q]
    ended = {}  # sha ごとの、その時点までの最後のデプロイの結果
    state, broken_at, deployed = None, None, False
    for at, kind, v in sorted(events, key=lambda e: e[0]):
        if kind == "merge":
            deployed = False
            if state != BROKEN:
                state = UNKNOWN
        elif kind == "deploy":
            ended[v.get("sha")] = v.get("result")
            if state == BROKEN and (at_of[v.get("sha")] <= broken_at or v.get("result") != "success"):
                continue  # 壊れる前のマージのデプロイ（やり直しを含む）と、成功しなかったデプロイでは抜けない
            state, deployed = UNKNOWN, v.get("result") == "success"
        elif kind == "parked":
            if state == UNKNOWN and ended.get(v.get("sha")) == "failure" and not v.get("rollback"):
                deployed = True  # 戻さずに積んだ: 届いた分の本番を smoke で確かめる
        elif kind == "rolled":
            state, deployed = UNKNOWN, True
        elif state is not None and v == "pass":
            if state != BROKEN and deployed:
                state = CONFIRMED
        elif state is not None:
            state, broken_at = BROKEN, at
    return RESTORED if state == CONFIRMED and going_back(s) else state


def production_errors(d, s, done=True):
    """本番を壊れたまま・確かめないまま朝にしない。止める側（check・Stop hook・ready・block・wait）が読む唯一の述語。
    done=False（ready・block・wait の門）は、壊れたまま・戻した後の未確認・予算を過ぎた未確認・直せないデプロイ後の要件だけを言う。
    done=True（check・Stop hook）は、確かめていない本番も言う。"""
    prod = production(d, s)
    if prod is None:
        return []
    cmd = rollback_cmd((d / "spec.md").read_text(encoding="utf-8"))
    rollback = (f"spec の `- ロールバック:` の `{cmd}` を打ち、`$ {cmd}` の行と出力を overnight.py rolled-back で記録する" if cmd else
                "spec のマージを戻す revert の PR を出し、overnight.py ready --rollback と merged --rollback で記録する"
                "（戻す PR が通らなければ block --no-rollback で人に示す）")
    if prod == BROKEN:
        return [f"本番が壊れたまま（smoke の fail・unknown）。直しより先にロールバック: {rollback}"]
    if going_back(s):  # 戻した本番は、確かめれば開ける。確かめていなければ待つ
        return [] if prod == RESTORED else [
            "ロールバックの後の本番を smoke で確かめていない（デプロイを待ち、smoke を overnight.py qa --smoke で記録する。"
            "戻しても壊れたままなら block --no-rollback で人に示す）"]
    late = stage_failures(d, s)
    if late:
        return [f"デプロイ後の {'、'.join(late)} が作り直しを {autopilot.MAX_REWORKS} 回しても通らないか、マージ後の予算を過ぎた。"
                f"直しを続けずにロールバック: {rollback}"]
    if prod == UNKNOWN:
        elapsed, budget, label = budget_view(d, s)
        if label == "マージ後" and elapsed > budget:
            return [f"マージ後の予算 {budget:.0f} 分を過ぎたのに、本番を smoke で確かめていない。直しを続けずにロールバック: {rollback}"]
        if done:
            return ["本番を smoke で確かめていない（デプロイを待ち、spec の変えない挙動を本番で確かめて overnight.py qa --smoke で"
                    f"記録する。確かめられなければ --smoke unknown を記録してロールバック: {rollback}）"]
    return []


def stage_failures(d, s):
    """マージの後に、作り直しが尽きたか、マージ後の予算を過ぎて pass でないデプロイ後の要件。"""
    if not s.get("merges") or s.get("merged_at") is None:
        return []
    text = (d / "spec.md").read_text(encoding="utf-8")
    rows = {}
    qa = d / "qa.md"
    for line in (qa.read_text(encoding="utf-8") if qa.exists() else "").splitlines():
        m = autopilot.QA_ROW.match(line)
        if m:
            rows[m.group(1)] = m.group(2)
    elapsed, budget, label = budget_view(d, s)
    over = label == "マージ後" and elapsed > budget
    return [r for r in stages.deployed_reqs(autopilot, text) if rows.get(r) == "fail"
            and (over or len((s.get("reworks") or {}).get(r, [])) >= autopilot.MAX_REWORKS)]


def rollback_error(root, s, head, base):
    """head が、base の上で、この夜の spec のマージ（戻したものを除く）の変更をちょうど戻したものか。誤りの文か None。
    spec の変更は、各マージの PR の head とその分岐点の差分（squash・rebase・merge commit を問わない）。
    base に当て、できた tree が head の tree と同じかで決める（ほかの変更を混ぜた PR は通らない）。"""
    spec = [m for m in s.get("merges") or [] if not m.get("rollback")]
    if not spec or not head or not base or not all(m.get("sha") and m.get("head") for m in spec):
        return "戻す相手の spec のマージ、または戻す PR の head・base の記録が無い"
    import tempfile
    env = {**os.environ, "GIT_INDEX_FILE": tempfile.mktemp(prefix="autopilot-rollback-")}
    try:
        def git(*args):
            return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True).stdout.strip()

        fork = git("merge-base", head, base)
        subprocess.run(["git", "read-tree", fork], cwd=root, env=env, check=True, capture_output=True)
        for m in reversed(spec):
            start = git("merge-base", m["head"], f"{m['sha']}^1")
            patch = subprocess.run(["git", "diff", "--binary", start, m["head"]], cwd=root, capture_output=True, check=True).stdout
            r = subprocess.run(["git", "apply", "--cached", "-R"], cwd=root, env=env, input=patch, capture_output=True)
            if r.returncode != 0:
                return f"spec のマージ（{m['sha'][:8]}）の変更を {fork[:8]} の上で戻せない（ほかの変更と重なる）"
        tree = subprocess.run(["git", "write-tree"], cwd=root, env=env, capture_output=True, text=True, check=True).stdout.strip()
        want = git("rev-parse", f"{head}^{{tree}}")
    except (OSError, subprocess.CalledProcessError) as e:
        return f"git で確かめられない（{type(e).__name__}）"
    finally:
        try:
            os.unlink(env["GIT_INDEX_FILE"])
        except OSError:
            pass
    if tree != want:
        return f"{head[:8]} は spec のマージの変更を戻したものと一致しない（ほかの変更を混ぜたか、戻し切っていない）"
    return None


def review_errors(d, s):
    """最後のレビューが今の HEAD を見たか（テスト・文書だけの違いは許す）。check が読む。"""
    reviews = s.get("reviews") or []
    if not reviews or "sha" not in reviews[-1]:
        return []  # レビューが無いことは ladder_errors が言う。sha の無い旧い記録は今までどおり
    root, now = autopilot.repo_root(d), head(autopilot.repo_root(d))
    if reviews[-1]["sha"] == now or only_tests_and_docs(root, reviews[-1]["sha"], now):
        return []
    merges = s.get("merges") or []
    if merges and merges[-1].get("rollback") and only_tests_and_docs(root, merges[-1].get("head"), now):
        return []  # 戻した PR は、spec のマージを戻したことを merged --rollback が git で確かめている
    return [f"最後のレビューの後に、テスト・文書の外のコードが変わった（{reviews[-1]['sha'][:8]}..{(now or '?')[:8]}）。"
            "overnight.py handoff を通して評価役を回し直す"]


def dirty_code(root):
    return [line[3:] for line in autopilot.git_lines(root, "status", "--porcelain", "--untracked-files=all")
            if not autopilot.SPEC_FILES.search(line[3:].strip('"'))]


def closed_handoff(s, now):
    """最後の dispatch を閉じた handoff のうち、tip が now のもの。無ければ None（dispatch の番号の無い旧い記録は閉じていない）。"""
    n = len(s.get("dispatches") or []) - 1
    return next((h for h in reversed(s.get("handoffs") or []) if h.get("dispatch") == n and n >= 0 and h.get("tip") == now), None)


def review_gate(d, s):
    """review の記録の前提: 今の HEAD で handoff が通っていて、commit していないコードが無い。(誤り, HEAD)。"""
    root = autopilot.repo_root(d)
    now = head(root)
    if now is None or closed_handoff(s, now) is None:
        return (f"最後の dispatch を、今の HEAD（{(now or '無い')[:8]}）で overnight.py handoff が閉じていない。"
                "実装役の報告を確かめてから評価役に進む"), now
    dirty = dirty_code(root)
    if dirty:
        return f"commit していないコードがある: {', '.join(dirty)}", now
    return None, now


# --- 待ちの記録と予算（Stop hook と status が読む） ---

def awaits(d, s):
    """今の承認より後に終わった待ちの記録（承認し直した前の夜の記録は読まない）。読めない行は飛ばす。"""
    since = float(s.get("approved_at") or 0)
    return [r for r in _awaits(d) if r["at"] > since]


def _awaits(d):
    f = d / AWAITS_LOG
    out = []
    for line in f.read_text(encoding="utf-8").splitlines() if f.exists() else []:
        try:
            r = json.loads(line)
            if isinstance(r, dict) and isinstance(r.get("at"), (int, float)):
                out.append(r)
        except ValueError:
            continue
    return out


def parked_ops(d, s):
    """積んだ操作（park と、上限を過ぎた待ち）。"""
    timeouts = [{"kind": a.get("kind"), "op": f"{a.get('kind')} の待ち（PR {a.get('pr')}）",
                 "reason": "待ちの上限を過ぎた", "req": None, "sha": a.get("sha"), "at": a["at"]}
                for a in awaits(d, s) if a.get("result") == "timeout"]
    return list(s.get("parked") or []) + timeouts


def exempt_kinds(d, s):
    """段（merge・deploy・qa）を免除する積んだ操作の kind。要件を名指しした park は、その要件だけの話なので段を免除しない。
    park は最後のマージの後に積んだものだけ、deploy の待ちの上限は最後のマージの commit のものだけを数える。"""
    merges = s.get("merges") or []
    last = merges[-1].get("sha") if merges else None
    kinds = {p.get("kind") for p in s.get("parked") or [] if not p.get("req") and p.get("merges", 0) == len(merges)}
    kinds |= {a.get("kind") for a in awaits(d, s) if a.get("result") == "timeout" and a.get("kind") == "deploy"
              and a.get("sha") == last}
    since = float(merges[-1].get("at", 0)) if merges else 0
    if any(a.get("result") == "timeout" and a.get("kind") == "review" and a["at"] > since for a in awaits(d, s)):
        kinds.add("merge")  # 承認の待ちが朝まで届かなかったマージは、人の判断を待つものとして積む
    return kinds


def budget_view(d, s):
    """(経過の分, 予算の分, 名前)。待ちの時間は数えない。マージの後は、マージ後の予算をマージの時刻から数える。"""
    paused = float(s.get("paused_sec", 0))
    waited = [(float(a["at"]), float(a["at"]) - float(a.get("started_at", a["at"]))) for a in awaits(d, s)]
    if s.get("merged_at") is not None:
        merged = float(s["merged_at"])
        since = merged + paused - float(s.get("paused_at_merge", 0)) + sum(w for at, w in waited if at > merged)
        return (time.time() - since) / 60, float(s.get("post_budget_min") or s["budget_min"]), "マージ後"
    since = float(s["approved_at"]) + paused + sum(w for _, w in waited)
    return (time.time() - since) / 60, float(s["budget_min"]), "承認から"


def await_record(d):
    """生きているかもしれない待ちの記録 {pid, started_at, deadline, dir}。無い・読めなければ None。"""
    try:
        r = json.loads((d / AWAIT_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(r, dict):
        return None
    pid, started, deadline = r.get("pid"), r.get("started_at"), r.get("deadline")
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        return None
    if not all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in (started, deadline)):
        return None
    return r


# --- CLI ---

def gh(*args, timeout=60):
    r = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout, r.stderr


def gh_json(*args):
    code, out, err = gh(*args)
    try:
        return json.loads(out)
    except ValueError:
        raise RuntimeError(f"gh {' '.join(args)} が読めない（exit {code}）: {err.strip()[:300]}")


def _state(value):
    if value in OK:
        return "ok"
    if value in SKIP:
        return "skip"
    if value in PENDING or value is None:
        return "pending"
    return "fail"


REVIEW = {"APPROVED": "ok", "CHANGES_REQUESTED": "fail", "REVIEW_REQUIRED": "pending"}


class NotRequired(Exception):
    pass


def poll(kind, pr, sha, workflows):
    """[(名前, 状態, run の id)]。状態は ok・pending・fail のどれか（許可リストの外は fail）。"""
    if kind == "review":
        v = gh_json("pr", "view", str(pr), "--json", "reviewDecision,headRefOid")
        decision = v.get("reviewDecision") or ""
        if decision not in REVIEW:
            raise NotRequired(f"reviewDecision が「{decision}」。レビューの承認はこの PR の要件ではない（承認を待たずにマージを試す）")
        return [("review", REVIEW[decision], None)]
    if kind == "ci":
        rows = gh_json("pr", "checks", str(pr), "--json", "name,bucket,link")
        return [(r.get("name"), _state(r.get("bucket")), (RUN_ID.search(r.get("link") or "") or [None, None])[1])
                for r in rows]
    rows = gh_json("run", "list", "--commit", sha, "--json", "databaseId,workflowName,status,conclusion")
    out = [(r.get("workflowName"), _state(r.get("conclusion") if r.get("status") == "completed" else r.get("status")),
            str(r.get("databaseId"))) for r in rows if not workflows or r.get("workflowName") in workflows]
    seen = {n for n, _, _ in out}
    return out + [(w, "pending", None) for w in workflows if w not in seen]  # まだ起きていない workflow は待つ


def cmd_await(a):
    if not Path(a.dir).is_absolute():
        sys.exit("<dir> は絶対パスで渡す（Stop hook は待ちのプロセスの引数に spec の絶対パスがあるかで確かめる）")
    d = Path(a.dir)
    s = autopilot.load_state(d)
    if s.get("phase") != "building":
        autopilot.refuse(s, "await は自走中（building）だけ受ける")
    if a.kind in ("ci", "review") and a.pr is None:
        sys.exit(f"--kind {a.kind} には --pr が要る")
    sha = None
    if a.kind == "ci":
        sha = gh_json("pr", "view", str(a.pr), "--json", "headRefOid").get("headRefOid")
    workflows = a.workflow
    if a.kind == "deploy":
        merges = s.get("merges") or []
        if not merges or not merges[-1].get("sha"):
            sys.exit("マージの記録が無い。先に overnight.py merged <dir> --pr <n>")
        if a.workflow:
            sys.exit("--kind deploy は --workflow を受けない。spec の `- デプロイの確かめ:` に並べた workflow を全部待つ")
        if autopilot.sha(d) != s.get("spec_sha256"):
            sys.exit("spec.md が承認の後に変わっている。デプロイは承認した `- デプロイの確かめ:` でだけ待つ")
        workflows = deploy_workflows((d / "spec.md").read_text(encoding="utf-8"))
        if not workflows:
            sys.exit("spec の `- デプロイの確かめ:` に待つ workflow の名前が無い（`、` で並べる）")
        sha = merges[-1]["sha"]
    timeout = (a.timeout_min if a.timeout_min is not None else DEFAULT_TIMEOUT[a.kind]) * 60
    started = time.time()
    (d / AWAIT_FILE).write_text(json.dumps({"pid": os.getpid(), "started_at": started, "deadline": started + timeout + GRACE_SEC,
                                            "kind": a.kind, "pr": a.pr, "dir": str(d)}), encoding="utf-8")
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    result, detail = "error", []
    try:
        while True:
            runs = poll(a.kind, a.pr, sha, workflows)
            failed = [r for r in runs if r[1] == "fail"]
            if failed:  # 1 本でも落ちたら、残りを待たずに main を起こす
                flaky = [r for r in failed if r[2] and first_attempt(r[2]) and FLAKE.search(gh("run", "view", r[2], "--log-failed")[1])]
                if len(flaky) == len(failed):
                    result, detail = "flake", [f"gh run rerun {r[2]} --failed" for r in flaky]
                else:
                    result, detail = "failure", [f"{r[0]}: 失敗（run {r[2]}）" for r in failed if r not in flaky]
                break
            if any(r[1] == "ok" for r in runs) and all(r[1] in ("ok", "skip") for r in runs):
                result, detail = "success", [r[0] for r in runs]
                break
            if time.time() - started >= timeout:
                result, detail = "timeout", [f"{n}: {st}" for n, st, _ in runs] or ["run がまだ 1 本も無い"]
                break
            time.sleep(a.interval)
    except NotRequired as e:
        result, detail = "not_required", [str(e)]
    except Exception as e:  # 読めないときは失敗として main を起こす（黙って待ち続けない）
        result, detail = "error", [f"{type(e).__name__}: {e}"]
    finally:
        with (d / AWAITS_LOG).open("a", encoding="utf-8") as f:
            f.write(json.dumps({"kind": a.kind, "pr": a.pr, "sha": sha, "result": result, "started_at": started,
                                "at": time.time(), "detail": detail}, ensure_ascii=False) + "\n")
        (d / AWAIT_FILE).unlink(missing_ok=True)
    print(f"await {a.kind}: {result}\n- " + "\n- ".join(detail))
    if result == "flake":
        print("flake の型（1 回目の実行）。上のコマンドを main の Bash で打ち、await を起動し直す（2 回目に落ちたら失敗として扱う）")
    return {"success": 0, "timeout": 2, "flake": 3}.get(result, 1)


def first_attempt(run_id):
    """run がまだ 1 回目の実行か（gh の attempt で決める。await を起動し直しても再実行は 1 回だけになる）。読めなければ False。"""
    try:
        return gh_json("run", "view", run_id, "--json", "attempt").get("attempt") == 1
    except Exception:
        return False


def cmd_dispatch(a):
    """実装役に渡す時点の HEAD を記録する（handoff はここから commit が増えたかを見る）。"""
    d = Path(a.dir)
    s = autopilot.load_state(d)
    if s.get("phase") != "building":
        autopilot.refuse(s, "dispatch は自走中（building）だけ受ける")
    name, reqs, stop = impl_name(d, s, a.task)
    if stop:
        print(stop)
        return 1
    base = head(autopilot.repo_root(d))
    s.setdefault("dispatches", []).append({"base": base, "tasks": a.task, "reqs": reqs, "agent": name, "at": time.time(),
                                           "session": os.environ.get("CLAUDE_CODE_SESSION_ID")})
    autopilot.save_state(d, s)
    print(f"dispatch: {', '.join(a.task)} を {(base or 'commit の無い repo')[:8]} から実装役に渡す。起動する agent:\n{name}")
    return 0


def new_commits(root, base, now):
    """base から now までの commit の数（rebase の後も数えられる）。読めなければ 0。"""
    if now is None:
        return 0
    if base is None:
        return 1
    try:
        return int(autopilot.git_lines(root, "rev-list", "--count", f"{base}..{now}")[0])
    except (RuntimeError, IndexError, ValueError):
        return 0


AGENTS = Path(__file__).resolve().parent.parent / "agents"
ALIASES = ("opus", "sonnet", "fable", "haiku")


def defined(name):
    """agent 定義の (model, effort)。読めなければ (None, None)。"""
    try:
        fm = dict(re.findall(r"^(model|effort): *(\S+)", (AGENTS / f"{name}.md").read_text(encoding="utf-8"), re.M))
    except OSError:
        return None, None
    return fm.get("model"), fm.get("effort")


def same_model(want, got):
    """定義の model（別名か ID）と、動いた model の ID が合うか。"""
    return isinstance(got, str) and (got == want or want in ALIASES and got.startswith(f"claude-{want}-"))


def launches(session, since):
    """session で since の後に起動した subagent の [(agent の名前, {model}, {effort}, 読めない記録の名前 or None)]。
    host は subagent ごとに <config>/projects/<project>/<session>/subagents/agent-<id>.meta.json と .jsonl を書く。
    meta.json が読めない記録は数えない。実装役と読めて transcript が読めない記録は、読めない記録として返す（照合できないまま通さない）。"""
    home = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    out = []
    for meta in home.glob(f"projects/*/{session}/subagents/*.meta.json"):
        try:
            name = json.loads(meta.read_text(encoding="utf-8"))["agentType"].split(":")[-1]
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            continue
        log = meta.with_name(meta.name[: -len(".meta.json")] + ".jsonl")
        try:
            launch = read_launch(name, log, since)
        except (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError):
            try:  # transcript が無ければ meta.json の時刻で決める
                late = (log if log.exists() else meta).stat().st_mtime >= since
            except OSError:
                late = True
            launch = (name, set(), set(), log.stem) if late else None
        if launch:
            out.append(launch)
    return out


def read_launch(name, log, since):
    """1 つの subagent の (名前, {model}, {effort}, None)。since より前に起動したものは None。形が違えば例外を投げる。
    model は transcript から読む（meta.json に無いことがある。<synthetic> は host が足す行）。"""
    lines = [line for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]
    if datetime.fromisoformat(json.loads(lines[0])["timestamp"].replace("Z", "+00:00")).timestamp() < since:
        return None
    models, efforts = set(), set()
    for row in map(json.loads, lines):
        if row.get("type") != "assistant" or row["message"].get("model") == "<synthetic>":
            continue
        model, effort = row["message"].get("model"), row.get("effort")
        if not isinstance(model, str) or not isinstance(effort, (str, type(None))):
            raise TypeError("model・effort の形が違う")
        models.add(model)
        efforts.add(effort)
    return name, models, efforts, None


def launch_errors(dispatch):
    """dispatch が指した実装役が、定義の model と effort で起動されたか。実装役を起動しなかった（main が書いた・
    実装役でない agent だけに書かせた）・別の段の実装役を起動した・model を渡した・main の effort を継承した、を拒む。
    範囲: 起動した実装役の agent・model・effort が定義と合うかだけを見る。想定するのは事故（model の渡し間違い、
    effort の継承、段の取り違え）で、わざと避ける形は想定しない。やらないこと: main が自分で書いた commit・amend・merge
    の見分け、dispatch を打たずに起動した実装役の見分け、定義と違う model が書いた commit の除去（戻すのは手順書の main の手順）。"""
    name, session = dispatch.get("agent"), dispatch.get("session") or os.environ.get("CLAUDE_CODE_SESSION_ID")
    if not name:
        return ["dispatch の記録に実装役の名前が無い（前の版の記録か、手で直した記録）。dispatch から打ち直す"]
    if not isinstance(session, str) or not autopilot.SESSION_ID.fullmatch(session):
        return ["dispatch したセッションが分からない（CLAUDE_CODE_SESSION_ID が無い）ので、実装役の起動の記録を確かめられない"]
    runs = [r for r in launches(session, float(dispatch.get("at") or 0)) if r[0].startswith("autopilot-implementer")]
    errors = [f"{name} の起動の記録 {bad} が読めない（照合できない）" for t, _, _, bad in runs if bad and t == name]
    errors += [f"dispatch は {name} を指したが、{t} を起動した" for t, _, _, _ in runs if t != name]
    mine = [r for r in runs if r[0] == name and not r[3]]
    if not mine and not errors:
        return [f"dispatch の後に {name} を起動した記録が無い（main が書いた、または別の agent に書かせた）"]
    model, effort = defined(name)
    for _, models, efforts, _ in mine:
        if not models or not all(same_model(model, m) for m in models):
            errors.append(f"{name} が model {'・'.join(sorted(map(str, models))) or 'なし'} で動いた（定義は {model}）。"
                          "起動のときに model を渡さない")
        if efforts != {effort}:
            errors.append(f"{name} が effort {'・'.join(sorted(map(str, efforts))) or 'なし'} で動いた（定義は {effort}）")
    return errors


def after_close_errors(root, tip, now):
    """閉じた tip の後に main が書いたコードの検査。spec のファイルの外で、tip と今の HEAD で中身が違うファイルから、統合先が
    変えたファイル（rebase・merge で入る分）を除いて、残りを拒む。tip が読めなければ拒む。"""
    def git(*args):
        out = subprocess.run(["git", "-c", "core.quotePath=false", *args], cwd=root, capture_output=True, text=True)
        return out.stdout.strip() if out.returncode == 0 else None
    def names(a, b):
        out = subprocess.run(["git", "-c", "core.quotePath=false", "diff", "-z", "--name-only", a, b], cwd=root, capture_output=True, text=True)
        if out.returncode != 0:
            raise RuntimeError(out.stderr.strip())
        return {f for f in out.stdout.split("\0") if f}
    if git("rev-parse", "--verify", "--quiet", f"{tip}^{{commit}}") is None:
        return [f"閉じたときの tip（{str(tip)[:8]}）が repo に無い（読めない）ので、閉じた後の変更を確かめられない"]
    try:
        cur, up = git("symbolic-ref", "-q", "HEAD"), git("rev-parse", "--symbolic-full-name", "@{u}")
        short = cur.removeprefix("refs/heads/") if cur else None
        merged = set()
        for ref in (git("for-each-ref", "--format=%(refname)", "refs/heads", "refs/remotes") or "").splitlines():
            if ref in (cur, up) or ref.endswith("/HEAD") or (short and ref.startswith("refs/remotes/") and ref.endswith("/" + short)):
                continue
            if contains(root, tip, ref) or contains(root, now, ref):
                continue
            mb0, mb1 = git("merge-base", tip, ref), git("merge-base", now, ref)  # 統合先を merge した後は tip が今の HEAD の祖先で、tip と HEAD の merge-base は tip 自身になる。統合先から見た分岐点を使う
            if mb0 and mb1 and contains(root, mb0, mb1):
                merged |= names(mb0, mb1)
        mine = sorted(f for f in names(tip, now) - merged if not autopilot.SPEC_FILES.search(f))
    except (RuntimeError, OSError) as e:
        return [f"閉じた後の変更を確かめられない: {e}"]
    if mine:
        return [f"閉じた後に、統合先が変えていないコードが変わっている: {', '.join(mine)}。閉じた tip（{tip[:8]}）に戻して commit するか、"
                "dispatch から実装役に直させる"]
    return []


def cmd_handoff(a):
    """受ける形は 3 つだけ。最後の dispatch が開いている: 全部を確かめる。閉じていて HEAD が閉じたときの tip: 記録済み。
    閉じていて HEAD が違う（マージの前の rebase を通すため。rebase に限らず受ける）: 増分も起動も見ず、commit していない
    コードと [x] だけを確かめる。"""
    d = Path(a.dir)
    s = autopilot.load_state(d)
    if s.get("phase") != "building":
        autopilot.refuse(s, "handoff は自走中（building）だけ受ける")
    root = autopilot.repo_root(d)
    now, errors = head(root), []
    dispatches = s.get("dispatches") or []
    if not dispatches:
        return autopilot.report(["dispatch の記録が無い。実装役に渡す前に overnight.py dispatch <dir> --task T<n>"], [], "")
    n, base = len(dispatches) - 1, dispatches[-1].get("base")
    closed = [h for h in s.get("handoffs") or [] if h.get("dispatch") == n]
    missing = [t for t in a.task if t not in (dispatches[-1].get("tasks") or [])]
    if missing:
        errors.append(f"{', '.join(missing)} は最後の dispatch で渡していない（渡すたびに dispatch する）")
    if closed and closed[-1].get("tip") == now and not missing:
        print("handoff: 最後の dispatch は今の HEAD で記録済み。評価役に進む")
        return 0
    if not closed:  # 開いている dispatch: 実装役の commit が増えたかを数える
        if base is not None and not contains(root, base, now):
            errors.append(f"dispatch の時点（{base[:8]}）が今の HEAD の祖先でない。実装役に渡している間に履歴が書き換わった")
        elif new_commits(root, base, now) == 0:
            errors.append(f"{(base or '着手の時点')[:8]} の後に commit が無い。実装役の「commit した」は事実と違う")
        errors += launch_errors(dispatches[-1])
    elif closed[-1].get("tip") != now:  # 閉じた後に HEAD が動いた: main が書いたコードを見分ける
        errors += after_close_errors(root, closed[-1].get("tip"), now)
    dirty = dirty_code(root)
    if dirty:
        errors.append(f"commit していないコードがある: {', '.join(dirty)}")
    done = {m.group(2) for m in map(autopilot.TASK.match, (d / "tasks.md").read_text(encoding="utf-8").splitlines())
            if m and m.group(1) in "xX"}
    errors += [f"{t} が tasks.md で [x] になっていない" for t in a.task if t not in done]
    if not errors:
        s.setdefault("handoffs", []).append({"tip": now, "tasks": a.task, "dispatch": n, "at": time.time()})
        autopilot.save_state(d, s)
    return autopilot.report(errors, [], "handoff: OK。評価役に進む")


def cmd_ready(a):
    d = Path(a.dir)
    s = autopilot.load_state(d)
    if a.rollback:
        return ready_rollback(d, s, a.pr)
    broken = production_errors(d, s, done=False)
    if broken:
        print("ERROR: " + broken[0] + "。戻す PR でなければマージしない")
        return 1
    if deploy_exhausted(d, s):
        print(f"ERROR: デプロイの失敗を直す PR が {MAX_DEPLOY_FIXES} 回とも通らなかった（上限）。この PR はマージせず、"
              "overnight.py park --kind deploy で積む")
        return 1
    reviews = s.get("reviews") or []
    reviewed = reviews[-1].get("sha") if reviews else None
    pr_head = gh_json("pr", "view", str(a.pr), "--json", "state,headRefOid").get("headRefOid")
    if not reviewed or (pr_head != reviewed and not only_tests_and_docs(autopilot.repo_root(d), reviewed, pr_head)):
        print(f"ERROR: 評価役が見た HEAD（{reviewed}）と PR の head（{pr_head}）が違い、テスト・文書の外も変わっている。"
              "評価役を 1 本だけ回し直して review を記録してからマージする")
        return 1
    if not any(x.get("kind") == "ci" and x.get("result") == "success" and x.get("sha") == pr_head for x in awaits(d, s)):
        print(f"ERROR: PR の head（{pr_head}）で CI が通った記録が無い。overnight.py await <dir> --kind ci --pr {a.pr}")
        return 1
    errors, _ = autopilot.check(d, stage="pr")
    if errors:
        print("ERROR: " + "\nERROR: ".join(errors))
        return 1
    print("ready: 評価役が見た head と同じ（またはテスト・文書だけの違い）で、CI が通り、PR の前の検査も通る。gh pr merge を打つ")
    return 0


def ready_rollback(d, s, pr):
    """戻す PR: 評価役の巡は要らない。PR の head が spec のマージを戻していて、その head で CI が通っている。"""
    v = gh_json("pr", "view", str(pr), "--json", "state,headRefOid,baseRefOid")
    pr_head = v.get("headRefOid")
    err = rollback_error(autopilot.repo_root(d), s, pr_head, v.get("baseRefOid"))
    if err:
        print(f"ERROR: PR {pr} は spec のマージを戻していない: {err}")
        return 1
    if not any(x.get("kind") == "ci" and x.get("result") == "success" and x.get("sha") == pr_head for x in awaits(d, s)):
        print(f"ERROR: PR の head（{pr_head}）で CI が通った記録が無い。overnight.py await <dir> --kind ci --pr {pr}")
        return 1
    print("ready: spec のマージを戻す PR で、CI が通っている。gh pr merge を打つ")
    return 0


def cmd_merged(a):
    d = Path(a.dir)
    s = autopilot.load_state(d)
    if s.get("phase") != "building":
        autopilot.refuse(s, "merged は自走中（building）だけ受ける")
    merges = s.setdefault("merges", [])
    if any(m.get("pr") == a.pr for m in merges):
        print(f"merged: PR {a.pr} は記録済み")
        return 0
    v = gh_json("pr", "view", str(a.pr), "--json", "state,mergedAt,mergeCommit,headRefOid")
    if v.get("state") != "MERGED" or not v.get("mergedAt"):
        print(f"ERROR: PR {a.pr} はマージされていない（state={v.get('state')}）。branch protection に断られたら回避せず park する")
        return 1
    sha = (v.get("mergeCommit") or {}).get("oid")
    entry = {"pr": a.pr, "at": time.time(), "sha": sha, "head": v.get("headRefOid")}
    if a.rollback:
        if not (a.reason or "").strip():
            sys.exit("--rollback には --reason が要る")
        err = rollback_error(autopilot.repo_root(d), s, v.get("headRefOid"), f"{sha}^1" if sha else None)
        if err:
            print(f"ERROR: PR {a.pr} のマージは spec のマージを戻していない: {err}")
            return 1
        entry.update(rollback=True, reason=a.reason)
    merges.append(entry)
    if s.get("merged_at") is None:  # マージ後の予算は承認のときに固めた値（spec を読み直さない）
        s.update(merged_at=time.time(), paused_at_merge=float(s.get("paused_sec", 0)))
    autopilot.save_state(d, s)
    print(f"merged: PR {a.pr}。マージ後の予算 {s.get('post_budget_min') or s['budget_min']} 分")
    return 0


def cmd_qa(a):
    d = Path(a.dir)
    s = autopilot.load_state(d)
    if s.get("phase") != "building":
        autopilot.refuse(s, "qa は自走中（building）だけ受ける")
    f = Path(a.evidence)
    if not f.is_file() or f.stat().st_size == 0:
        sys.exit(f"証拠のファイルが無いか空: {f}")
    deployed = [x["at"] for x in awaits(d, s) if x.get("kind") == "deploy"]
    deployed += [float(r["at"]) for r in s.get("rolled_back") or []]
    if not deployed or f.stat().st_mtime <= max(deployed):
        sys.exit("証拠のファイルが、最後に終わったデプロイの待ちより後に書かれていない。デプロイの後に QA を回す")
    mtime = f.stat().st_mtime
    if any(q.get("evidence") == str(f) and q.get("mtime") == mtime for q in s.get("qa_runs") or []):
        print("qa: 記録済み")
        return 0
    s.setdefault("qa_runs", []).append({"evidence": str(f), "mtime": mtime, "smoke": a.smoke, "at": time.time()})
    autopilot.save_state(d, s)
    print(f"qa: 記録した。本番: {production(d, s) or '確かめていない'}")
    return 0


def cmd_rolled_back(a):
    """spec の `- ロールバック:` がコマンドの宣言のとき、そのコマンドを打った出力つきで戻したことを記録する。
    宣言と違うコマンド・壊れる前の出力・承認の後に変えた spec は受けない。"""
    d = Path(a.dir)
    s = autopilot.load_state(d)
    if s.get("phase") != "building":
        autopilot.refuse(s, "rolled-back は自走中（building）だけ受ける")
    if not a.reason.strip():
        sys.exit("--reason は空にできない")
    if autopilot.sha(d) != s.get("spec_sha256"):
        sys.exit("spec.md が承認の後に変わっている。rolled-back は承認した宣言でだけ受ける")
    cmd = rollback_cmd((d / "spec.md").read_text(encoding="utf-8"))
    if cmd is None:
        sys.exit("spec の `- ロールバック:` が revert の PR なので、rolled-back は受けない。"
                 "overnight.py ready --rollback と merged --rollback で戻す")
    f = Path(a.evidence)
    lines = stages.read_head(f).splitlines() if f.is_file() else []
    at = [i for i, x in enumerate(lines) if x.startswith("$ ") and x[2:].strip() == cmd]
    if not any(any(y.strip() for y in lines[i + 1:]) for i in at):
        sys.exit(f"証拠のファイルに、宣言したコマンドの `$ {cmd}` の行とその出力が無い: {f}")
    since = [float(m.get("at", 0)) for m in s.get("merges") or []]
    since += [float(x["at"]) for x in awaits(d, s) if x.get("kind") == "deploy"]
    since += [float(q["at"]) for q in s.get("qa_runs") or [] if q.get("smoke") in ("fail", "unknown")]
    mtime = f.stat().st_mtime
    if mtime <= max(since, default=0) or any(r.get("evidence") == str(f) and r.get("mtime") == mtime
                                             for r in s.get("rolled_back") or []):
        sys.exit("証拠のファイルが、最後のマージ・デプロイ・smoke の fail より後に書かれていないか、記録済み。戻した後の出力で記録する")
    s.setdefault("rolled_back", []).append({"reason": a.reason, "evidence": str(f), "mtime": mtime, "at": time.time()})
    autopilot.save_state(d, s)
    print("rolled-back: 記録した。smoke を確かめ直して overnight.py qa --smoke で記録する")
    return 0


def cmd_park(a):
    d = Path(a.dir)
    s = autopilot.load_state(d)
    if s.get("phase") != "building":
        autopilot.refuse(s, "park は自走中（building）だけ受ける")
    if not a.op.strip() or not a.reason.strip():
        sys.exit("--op と --reason は空にできない")
    if a.req and a.req not in autopilot.requirements((d / "spec.md").read_text(encoding="utf-8")):
        sys.exit(f"{a.req} は spec.md の要件に無い")
    n = len(s.get("merges") or [])
    if any((p.get("kind"), p.get("op"), p.get("req"), p.get("merges", 0)) == (a.kind, a.op, a.req, n)
           for p in s.get("parked") or []):
        print(f"parked: {a.op} は記録済み")
        return 0
    s.setdefault("parked", []).append({"kind": a.kind, "op": a.op, "reason": a.reason, "req": a.req, "merges": n,
                                       "at": time.time()})
    autopilot.save_state(d, s)
    print(f"parked: {a.op}。止めずに残りを進める（この操作に頼る要件は qa.md で unverified（park: ...）にする）")
    return 0


def report(d):
    """朝の報告の行（ketchup の型）。"""
    s = autopilot.load_state(d)
    parked = parked_ops(d, s)
    waiting = [f"{p['op']}（{p['reason']}）" for p in parked]
    rollbacks = [f"PR {m['pr']}（{m.get('reason')}）" for m in s.get("merges") or [] if m.get("rollback")]
    rollbacks += [f"コマンド（{r.get('reason')}）" for r in s.get("rolled_back") or []]
    waiting[:0] = [f"戻した: {x}" for x in rollbacks]
    if s.get("phase") == "blocked":
        b = s.get("blocked") or {}
        waiting.insert(0, f"block: {b.get('req')}（{b.get('reason')}）")
        if b.get("no_rollback"):
            waiting.insert(0, f"本番を戻していない: {b['no_rollback']}")
    lines = [f"## 朝の報告: {d.name}",
             f"本番: {production(d, s) or deploy_view(d, s) or 'この夜はデプロイしていない'}" + (f"。戻した: {'、'.join(rollbacks)}" if rollbacks else ""),
             ("人の判断を待つもの: " + "、".join(waiting)) if waiting else "人の判断を待つものは無い"]
    rows = {}
    for line in (d / "qa.md").read_text(encoding="utf-8").splitlines():
        m = autopilot.QA_ROW.match(line)
        if m:
            rows[m.group(1)] = (m.group(2), m.group(3).strip())
    word = {"pass": "done", "fail": "失敗", "unverified": "確かめていない"}
    scope = scope_of(d)
    stage_parks = exempt_kinds(d, s) & ({"merge"} if scope == MERGE else {"merge", "deploy", "qa"} if scope == FULL else set())
    merged = "、".join(f"PR {m['pr']}" for m in s.get("merges") or []) or "なし"
    for rid in autopilot.requirements((d / "spec.md").read_text(encoding="utf-8")):
        result, evidence = rows.get(rid, (None, ""))
        ops = [p["op"] for p in parked if p.get("req") == rid]
        state = word.get(result, "まだ動いている")
        if result == "pass" and (ops or stage_parks):  # 人を待っているものを done と書かない
            state = "確かめていない（積んだ操作に頼る: " + "、".join(ops + sorted(stage_parks)) + "）"
        lines.append(f"- {rid}: {state}" + (f"（{evidence}）" if evidence else "")
                     + f"。マージ: {merged}。直した欠陥 {len((s.get('fails') or {}).get(rid, []))}。"
                     + f"積んだ操作: {'、'.join(ops) or 'なし'}")
    lines.append(f"- 範囲: {scope or '読めない'}。マージ: {merged}")
    done = awaits(d, s)
    bad = [a for a in done if a.get("result") != "success"]
    lines.append(f"- 待ち: {len(done)} 回（通らなかった {len(bad)} 回" + "".join(f"、{a.get('kind')} {a.get('result')}" for a in bad) + "）")
    lines.append(f"- 積んだ操作: {len(parked)} 件。異常: {autopilot.anomaly_line(s.get('anomalies') or {})}")
    lines += ladder.report_lines(s.get("raises") or [], s.get("reviews") or [], task_rows(d))
    for x in s.get("lenses") or []:
        lines.append(f"- 観点「{x['name']}」: 指摘 {x['found']}・実行で再現 {x['reproduced']}・直した {x['fixed']}")
    return lines


def model_section(d):
    return autopilot.section((d / "spec.md").read_text(encoding="utf-8"), "モデル")


def task_rows(d):
    """tasks.md の {タスク: [要件]}。check と同じ読み手（autopilot.TASK）で行ごとに読む。"""
    t = d / "tasks.md"
    rows = {}
    for line in (t.read_text(encoding="utf-8") if t.exists() else "").splitlines():
        m = autopilot.TASK.match(line)
        if m:
            rows[m.group(2)] = [r.strip() for r in m.group(3).split(",") if r.strip()]
    return rows


def impl_name(d, s, tasks):
    """(実装役の名前, 渡す要件, 止める文)。止める文があれば渡さない。
    段は、タスクの全要件の梯子で決める（park の記録で要件を引かない）。一番上を超えた要件は、park に積むまで止め、積んだら渡さない。
    Fable は、Fable で渡した後にその要件の失敗が記録されたら一番上を超えたとみなす（通った要件の次の直しは止めない）。"""
    rows = task_rows(d)
    missing = [t for t in tasks if t not in rows]
    if missing:
        return None, [], f"{', '.join(missing)} は tasks.md に無い（読めない行も無いものとして扱う）"
    reqs = sorted({q for t in tasks for q in rows[t]})
    parked = {p.get("req") for p in parked_ops(d, s) if p.get("req")}
    fable = ladder.RUNGS["impl"]["fable"][0]
    fails = s.get("fails") or {}
    tried = {q for x in s.get("dispatches") or [] if x.get("agent") == fable for q in x.get("reqs") or []
             if any(float(f["at"]) > float(x["at"]) for f in fails.get(q, []))}
    name, past = ladder.impl_agent(model_section(d), s.get("raises") or [], reqs, tried)
    waiting = [q for q in past if q and q not in parked]
    if waiting:
        return None, [], park_line(waiting)
    if name is None:
        return None, [], "このタスクの要件は全部、一番上を超えて park に積んである。渡すものが無い"
    return name, [q for q in reqs if q not in past], None


def park_line(reqs):
    return f"一番上の段でも通らない。{', '.join(reqs)} を park に積む（overnight.py park <dir> --kind other --req R<n> ...）"


def cmd_agent(a):
    """その役（とタスク）に今起動する agent の名前を出す。一番上を超えた要件なら park を言って 1 で終える。"""
    d = Path(a.dir)
    s = autopilot.load_state(d)
    if a.role == "review":
        print(ladder.review_agent(model_section(d), s.get("raises") or [], s.get("reviews") or []))
        return 0
    if not a.task:
        sys.exit("--role impl には --task T<n> が要る")
    name, _, stop = impl_name(d, s, a.task)
    if stop:
        print(stop)
        return 1
    print(name)
    return 0


def cmd_raise(a):
    """評価役の判定が決まらないときに、評価役の段を 1 つ上げる（実装役の段は review の巡で CLI が上げる）。"""
    d = Path(a.dir)
    if a.reason != ladder.REVIEW_REASON:
        sys.exit(f"--reason は「{ladder.REVIEW_REASON}」だけ（実装役の段は review の巡で自動で上がる）")
    s = autopilot.load_state(d)
    raises = s.get("raises") or []
    sec = model_section(d)
    before = ladder.review_agent(sec, raises, s.get("reviews") or [])
    raises = raises + [{"role": "review", "reason": a.reason, "at": time.time()}]
    after = ladder.review_agent(sec, raises, s.get("reviews") or [])
    raises[-1].update({"from": before, "to": after})
    s["raises"] = raises
    autopilot.save_state(d, s)
    print(f"raise: {before}→{after}\n{after}")
    return 0


def cmd_lens(a):
    """評価役に差し込んだ観点ごとに、拾った指摘・実行で再現した数・直した数を残す（効かない観点を外すため）。"""
    d = Path(a.dir)
    s = autopilot.load_state(d)
    if s.get("phase") != "building":
        autopilot.refuse(s, "lens は自走中（building）だけ受ける")
    if not a.name.strip() or not 0 <= a.fixed <= a.reproduced <= a.found:
        sys.exit("--name は空にできず、0 ≤ fixed ≤ reproduced ≤ found にする")
    s.setdefault("lenses", []).append({"name": a.name, "found": a.found, "reproduced": a.reproduced, "fixed": a.fixed,
                                       "at": time.time()})
    autopilot.save_state(d, s)
    print(f"lens: {a.name} を記録した")
    return 0


def notify(d):
    """spec の `- 通知:` の先に 1 行で知らせる。デスクトップは osascript、Slack の DM は main に送らせる。失敗しても止めない。"""
    rows = scope_rows((d / "spec.md").read_text(encoding="utf-8")) or {}
    where = rows.get("通知") or "なし"
    s = autopilot.load_state(d)
    line = f"{d.name}: {s.get('phase')}。本番: {production(d, s) or deploy_view(d, s) or 'デプロイなし'}"
    if where == "Slack の DM":
        line = "\n".join([line, *report(d)[1:]])  # DM は朝の報告の行を載せる（読んで判断できるように）
    if where == "デスクトップ":
        try:
            r = subprocess.run(["osascript", "-e", f"display notification {json.dumps(line, ensure_ascii=False)} with title \"spec-autopilot\""],
                               capture_output=True, timeout=10)
            if r.returncode != 0:
                print(f"NOTE: デスクトップの通知を出せない（osascript の終了コード {r.returncode}）")
        except (OSError, subprocess.TimeoutExpired) as e:
            print(f"NOTE: デスクトップの通知を出せない（{type(e).__name__}）")
    elif where == "Slack の DM":
        print(f"NOTE: Slack の MCP で自分宛ての DM に送る: {line}")
    return line


def cmd_notify(a):
    print(notify(Path(a.dir)))
    return 0


def cmd_report(a):
    print("\n".join(report(Path(a.dir))))
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="overnight.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("await")
    w.add_argument("dir")
    w.add_argument("--kind", choices=("ci", "deploy", "review"), required=True)
    w.add_argument("--pr", type=int)
    w.add_argument("--workflow", action="append", default=[])
    w.add_argument("--interval", type=float, default=30)
    w.add_argument("--timeout-min", type=float)
    for name in ("ready", "merged"):
        x = sub.add_parser(name)
        x.add_argument("dir")
        x.add_argument("--pr", type=int, required=True)
        x.add_argument("--rollback", action="store_true")
        if name == "merged":
            x.add_argument("--reason")
    q = sub.add_parser("qa")
    q.add_argument("dir")
    q.add_argument("--evidence", required=True)
    q.add_argument("--smoke", choices=SMOKE, required=True)
    k = sub.add_parser("park")
    k.add_argument("dir")
    k.add_argument("--kind", choices=PARK_KINDS, required=True)
    k.add_argument("--op", required=True)
    k.add_argument("--reason", required=True)
    k.add_argument("--req")
    for name in ("handoff", "dispatch"):
        h = sub.add_parser(name)
        h.add_argument("dir")
        h.add_argument("--task", action="append", required=True)
    sub.add_parser("report").add_argument("dir")
    sub.add_parser("notify").add_argument("dir")
    rb = sub.add_parser("rolled-back")
    rb.add_argument("dir")
    rb.add_argument("--evidence", required=True)
    rb.add_argument("--reason", required=True)
    g = sub.add_parser("agent")
    g.add_argument("dir")
    g.add_argument("--role", choices=tuple(ladder.RUNGS), required=True)
    g.add_argument("--task", action="append")
    g = sub.add_parser("raise")
    g.add_argument("dir")
    g.add_argument("--role", choices=("review",), required=True)
    g.add_argument("--reason", required=True)
    n = sub.add_parser("lens")
    n.add_argument("dir")
    n.add_argument("--name", required=True)
    for k in ("found", "reproduced", "fixed"):
        n.add_argument(f"--{k}", type=int, required=True)
    a = p.parse_args(argv)
    return {"await": cmd_await, "ready": cmd_ready, "merged": cmd_merged, "qa": cmd_qa, "park": cmd_park,
            "handoff": cmd_handoff, "dispatch": cmd_dispatch, "report": cmd_report, "lens": cmd_lens, "notify": cmd_notify, "rolled-back": cmd_rolled_back,
            "agent": cmd_agent, "raise": cmd_raise}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
