"""範囲・デプロイ・本番・ロールバックの判定と、待ちの記録と予算（overnight.py から移した。Stop hook・status・lint・check・watch も読む）。"""
import json
import os
import re
import subprocess
import time
from pathlib import Path

import autopilot
import carry
import stages

SCOPE_SECTION = "自走の範囲"
FULL, MERGE, PR = "マージ・デプロイ・QA まで", "マージまで", "PR まで"
SCOPES = (FULL, MERGE, PR)
SCOPE_KEYS = ("範囲", "QA の環境", "QA の書き込み先", "デプロイの起動", "デプロイの確かめ", "ロールバック", "AWS の profile")
REQUIRED_FOR_FULL = ("QA の環境", "QA の書き込み先", "デプロイの起動", "デプロイの確かめ", "ロールバック")  # 空なら ERROR
AUTO_DEPLOY = "マージで自動"
NO_DEPLOY = "なし（マージした commit で QA）"  # デプロイの workflow が無い repo: 最後のマージの記録を QA の起点にする
ROUND_KEYS = ("merges", "merged_at", "paused_at_merge", "parked", "qa_runs", "handoffs", "dispatches", "lenses",
              "rolled_back", "review_launches")
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


WORKFLOW_NAME = re.compile(r"^name:[ \t]*(.+?)[ \t]*(?:#.*)?$", re.M)  # 字下げの無い最上位の `name:` だけ


def workflow_names(root):
    """repo の workflow の名前（gh の workflowName。`name:` が無ければ GitHub が付ける workflow のパス）と、
    ファイル名・その幹からその名前への対応。.github/workflows が無ければ None（GitHub の外の repo では照らさない）。"""
    w = Path(root) / ".github" / "workflows"
    if not w.is_dir():
        return None
    names, by_file = set(), {}
    for f in sorted(w.glob("*.y*ml")):
        m = WORKFLOW_NAME.search(f.read_text(encoding="utf-8", errors="replace"))
        name = m.group(1).strip("'\"") if m else f".github/workflows/{f.name}"
        names.add(name)
        by_file[f.name] = by_file[f.stem] = name
    return names, by_file


def deploy_check_lint(text, root):
    """`- デプロイの確かめ:` の名前が workflow の名前にあるか。await --kind deploy は gh の workflowName で照らし、
    承認の後は spec を直せないので、合わない名前は承認の前に止める（2026-11-26、ファイル名を書いて記録できなかった事例）。"""
    known = workflow_names(root) if root else None
    if not known:
        return []
    names, by_file = known
    return [f"自走の範囲の `- デプロイの確かめ:` の「{n}」は .github/workflows の workflow の名前に無い"
            "（await は gh の workflowName〔`name:` の値〕で照らす）"
            + (f"。ファイル {n} の workflow の名前は `{by_file[n]}`" if n in by_file else "")
            for n in deploy_workflows(text) if n not in names]


def scope_lint(text, root=None):
    """(errors, warnings)。root は spec の repo の root（workflow の名前を照らす。None なら照らさない）。"""
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
    if start and start not in (AUTO_DEPLOY, NO_DEPLOY) and not ROLLBACK_CMD.match(start):
        errors.append(f"自走の範囲の `- デプロイの起動:` は「{AUTO_DEPLOY}」か「コマンド: <1 行のコマンド>」か「{NO_DEPLOY}」のどれか（今は「{start}」）")
    if start == NO_DEPLOY and rows.get("デプロイの確かめ"):
        errors.append(f"デプロイの起動が「{NO_DEPLOY}」なので `- デプロイの確かめ:` は空にする（待つデプロイが無い）")
    warnings = []
    deployed = stages.deployed_reqs(autopilot, text)
    if scope in (PR, MERGE):  # 夜の間に届かないデプロイ後の要件は、承認のときに人が見る
        errors += [f"範囲が「{scope}」なので、デプロイ後の {r} は夜の間に確かめられない。"
                   f"`- unverified の承認: {r}（<理由>）` を書くか、範囲を「{FULL}」にする"
                   for r in deployed if not stages.approved(autopilot, text, r)]
    if scope == FULL:  # デプロイ後の要件が無ければ、マージ後の QA のループを通らない。マージで起きるデプロイの失敗は拾うので、起動と確かめは要る
        need = REQUIRED_FOR_FULL if deployed else ("QA の書き込み先", "デプロイの起動") + (
            () if start and ROLLBACK_CMD.match(start) else ("デプロイの確かめ",))
        if start == NO_DEPLOY:
            need = tuple(k for k in need if k != "デプロイの確かめ")
        errors += [f"範囲が「{FULL}」なので `- {k}:` を書く" for k in need if k in rows and not rows[k]]
        errors += deploy_check_lint(text, root)
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
    if "merge" not in parked and not (merges and (contains(root, head(root), merges[-1].get("head")) or carry.holds_head(root, s, merges[-1].get("head")))):
        errors.append("範囲がマージを含むのに、今の HEAD を含むマージを確かめていない（references/after-pr.md。"
                      "マージしたら overnight.py merged <dir> --pr <n>、できないなら overnight.py park --kind merge）")
    late = stages.deployed_reqs(autopilot, (d / "spec.md").read_text(encoding="utf-8"))
    if no_deploy(d):  # 待つデプロイが無い。マージの後の QA の記録は production_errors（smoke）と stage_errors（証拠の commit）が見る
        return errors
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


def no_deploy(d):
    """範囲が「マージ・デプロイ・QA まで」で、デプロイの起動が「なし（マージした commit で QA）」か。

    範囲: デプロイの workflow が無い repo で、最後のマージの記録（merged の時刻と commit）をデプロイの成功の代わりに QA の起点にする
    想定する脅威: 事故（agent がデプロイを待たずに QA を記録する・マージの前の証拠で通す）。敵対的な agent が state.json を書き換えることは防がない
    やらないこと: マージした commit を実際に checkout して QA したかの機械の確かめ（証拠の頭の `- commit:` を stages.check が見るだけ）"""
    text = (d / "spec.md").read_text(encoding="utf-8")
    return scope_of(d) == FULL and (scope_rows(text) or {}).get("デプロイの起動") == NO_DEPLOY


def qa_origins(d, s):
    """最後のマージの QA の起点の時刻。デプロイの起動が「なし」なら最後のマージの記録、ほかはそのマージの commit のデプロイの成功。"""
    merges = s.get("merges") or []
    if no_deploy(d):
        return [float(merges[-1].get("at", 0))] if merges else []
    return deploys_of_last_merge(d, s)


def deploy_stage(d):
    """デプロイの段を通るか: 範囲が「マージ・デプロイ・QA まで」で、デプロイ後の要件があるか、起動がコマンドの宣言でない
    （マージで本番が変わる。読めない値もこちら）。コマンドで起動しデプロイ後の要件が無い spec は、夜の間にデプロイを起こさない。"""
    text = (d / "spec.md").read_text(encoding="utf-8")
    if scope_of(d) != FULL or no_deploy(d):
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
    deployed = qa_origins(d, s)
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
    - デプロイの起動が「なし（マージした commit で QA）」（no_deploy）: デプロイは無く、マージした commit がそのまま確かめる相手。
      マージは成功したデプロイと同じに扱い（次の smoke の pass で確かめたにする）、壊れたままも壊れた後のマージで抜ける。
    確かめたは、最後に中身を変えた記録が戻し（going_back）なら戻して確かめた。この夜に何も無ければ None。"""
    text = (d / "spec.md").read_text(encoding="utf-8")
    if scope_of(d) != FULL or not stages.deployed_reqs(autopilot, text):
        return None
    merges = s.get("merges") or []
    at_of = {m.get("sha"): float(m.get("at", 0)) for m in merges if m.get("sha")}
    by_command = bool(ROLLBACK_CMD.match((scope_rows(text) or {}).get("デプロイの起動") or ""))
    merged_is_live = no_deploy(d)  # デプロイが無ければ、マージした commit がそのまま確かめる相手
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
            deployed = merged_is_live
            if state != BROKEN or merged_is_live:  # デプロイが無ければ、壊れた後のマージがデプロイの成功の代わり
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


def production_label(d, s):
    """朝の報告・通知・qa の表示の「本番:」の値。デプロイが無いと宣言した spec は、確かめた相手がマージした commit だと添える
    （宣言が誤りでもマージで本番にデプロイされる repo なら、本番そのものは見ていない。人が朝に宣言を読み直せるように）。"""
    prod = production(d, s)
    return f"{prod}（マージした commit。デプロイは無いと宣言）" if prod and no_deploy(d) else prod


def production_errors(d, s, done=True):
    """本番を壊れたまま・確かめないまま朝にしない。止める側（check・Stop hook・ready・block・wait）が読む唯一の述語。
    done=False（ready・block・wait の門）は、壊れたまま・戻した後の未確認・予算を過ぎた未確認・直せないデプロイ後の要件だけを言う。
    done=True（check・Stop hook）は、確かめていない本番も言う。"""
    cmd = rollback_cmd((d / "spec.md").read_text(encoding="utf-8"))
    rollback = (f"spec の `- ロールバック:` の `{cmd}` を打ち、`$ {cmd}` の行と出力を overnight.py rolled-back で記録する" if cmd else
                "spec のマージを戻す revert の PR を出し、overnight.py ready --rollback と merged --rollback で記録する"
                "（戻す PR が通らなければ block --no-rollback で人に示す）")
    try:
        prod = production(d, s)
    except UnreadableAwaits as e:  # 本番を確かめられない。止める側に倒し、マージの後なら先に戻させ、block で人に渡せるようにする
        if not s.get("merges") or going_back(s):
            return [f"{e}。本番を確かめられないので、block --no-rollback で理由を書いて人に示す（戻した後で smoke を回せるなら、先に qa --smoke で記録する）"]
        return [f"{e}。本番を確かめられないので、直しより先にロールバック: {rollback}"]
    if prod is None:
        return []
    wait = "マージした commit で、" if no_deploy(d) else "デプロイを待ち、"
    if prod == BROKEN:
        return [f"本番が壊れたまま（smoke の fail・unknown）。直しより先にロールバック: {rollback}"]
    if going_back(s):  # 戻した本番は、確かめれば開ける。確かめていなければ待つ
        return [] if prod == RESTORED else [
            f"ロールバックの後の本番を smoke で確かめていない（{wait}smoke を overnight.py qa --smoke で記録する。"
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
            return [f"本番を smoke で確かめていない（{wait}spec の変えない挙動を本番で確かめて overnight.py qa --smoke で"
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


# --- 待ちの記録と予算（Stop hook と status が読む） ---

def awaits(d, s, strict=True):
    """今の承認より後に終わった待ちの記録（承認し直した前の夜の記録は読まない）。読めない行があれば止める（_awaits）。
    strict=False は読める行だけを返す。記録が欠けても断る側にしか倒れない読み手（「通った記録があるか」）と、deploy_floor と、
    朝の報告（判定の門に使わない。読めないときは pass の要件も done と書かない）だけが使う。"""
    since = float(s.get("awaits_since") or s.get("approved_at") or 0)  # 持ち越した spec は、持ち越したマージの待ちの記録も読む
    return [r for r in _awaits(d, strict) if r["at"] > since]


def deploy_floor(d, s):
    """smoke・戻しの証拠が後でなければならない、デプロイの待ちの終わりの時刻。読めない行があるときは、
    消えた記録の時刻を知れないので、記録のファイルの更新の時刻も足す（書き手は追記だけなので、どの記録よりも後）。"""
    floor = [float(x["at"]) for x in awaits(d, s, strict=False) if x.get("kind") == "deploy"]
    try:
        _awaits(d)
    except UnreadableAwaits:
        floor.append((d / AWAITS_LOG).stat().st_mtime)
    return floor


UNREADABLE_PROD = "待ちの記録が読めないので分からない"  # 読めない待ちの記録のときの本番の表示（qa・report・notify）


class UnreadableAwaits(ValueError):
    """awaits.jsonl に記録として読めない行がある（production_errors が「本番が良くない」として受け、block で人に戻せるようにする）。"""


def _awaits(d, strict=True):
    """待ちの記録の行。空でないのに記録として読めない行（書き込みの途中で切れたものなど）があれば、数えずに通さないよう、
    ファイルと行番号を名指しして UnreadableAwaits で止める（人がその行を直すか消すまで、その spec の判定は止まる）。
    strict=False はその行を飛ばす（awaits の strict を見る）。"""
    f = d / AWAITS_LOG
    out = []
    lines = f.read_bytes().split(b"\n") if f.exists() else []  # "\n" だけで割る（記録の文字列の U+2028 で割らない）
    for n, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            r = json.loads(line.decode("utf-8"))
        except ValueError:  # UnicodeDecodeError（マルチバイトの途中で切れた行）も ValueError の子
            r = None
        if not (isinstance(r, dict) and isinstance(r.get("at"), (int, float))):
            if not strict:
                continue
            raise UnreadableAwaits(f"{f}:{n} の待ちの記録が読めないので、数えずに止める。行は人が直すか消す"
                                   "（agent が消すと数え漏れる）。autopilot.py block で人に示す"
                                   "（本番が良くないと断られたら、先に戻すか、戻せない理由を --no-rollback に書く）")
        out.append(r)
    return out


def parked_ops(d, s, strict=True):
    """積んだ操作（park と、上限を過ぎた待ち）。"""
    timeouts = [{"kind": a.get("kind"), "op": f"{a.get('kind')} の待ち（PR {a.get('pr')}）",
                 "reason": "待ちの上限を過ぎた", "req": None, "sha": a.get("sha"), "at": a["at"]}
                for a in carry.this_round_timeouts(awaits(d, s, strict), s)]
    return list(s.get("parked") or []) + timeouts


def exempt_kinds(d, s, strict=True):
    """段（merge・deploy・qa）を免除する積んだ操作の kind。要件を名指しした park は、その要件だけの話なので段を免除しない。
    park は最後のマージの後に積んだものだけ、deploy の待ちの上限は最後のマージの commit のものだけを数える。"""
    merges = s.get("merges") or []
    last = merges[-1].get("sha") if merges else None
    kinds = {p.get("kind") for p in s.get("parked") or [] if not p.get("req") and p.get("merges", 0) == len(merges)}
    kinds |= {a.get("kind") for a in carry.this_round_timeouts(awaits(d, s, strict), s) if a.get("kind") == "deploy" and a.get("sha") == last}
    since = float(merges[-1].get("at", 0)) if merges else 0
    if any(a.get("kind") == "review" and a["at"] > since for a in carry.this_round_timeouts(awaits(d, s, strict), s)):
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
