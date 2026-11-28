"""QA の方向性の段（手元で実物・デプロイ後・代役）と、段ごとの証拠の要求（lint と check が読む）。

段は QA の方向性の表の 2 列目に書く（`| R1 | 手元で実物 | 確かめ方 | 合格基準 |`）。選ぶ順は次のとおり。
- 手元で実物（既定）: 手元から本物の道具・API・runtime を動かす。マージ前に本番で一時的な資源を作って試す形も含む
- デプロイ後: 手元では確かめられない要件だけ。`- 手元でできない理由: R<n>（<理由>）` を書く
- 代役: 実物が手元にもデプロイ後にも無いときだけ。`- 代役の理由: R<n>（<理由>）` を書き、人が承認で見る
手元で実物とデプロイ後の pass は、実行の出力を spec のディレクトリの `evidence/<要件>.txt` に残す。どちらも `$ <コマンド>` の行と
その出力が要る。手元で実物の出力は、頭の `- commit:` が、その要件を最後に確かめた評価役の巡の tip のもの（spec の置き場の外が tip と同じ commit も含む）だけを数える。デプロイ後の出力は、最後のマージの commit のデプロイが通った後に書き、頭に `- commit: <その sha>` と
`- 結果: Confirmed` を 1 本ずつ書いたものだけを数える。unverified は、`- unverified の承認: R<n>（<理由>）` の行か、
その要件を積んだ park があるときだけ通す。行の形だけを読み、自由文は解釈しない。
"""
import re
import subprocess
from pathlib import Path

import carry

LOCAL, DEPLOYED, STAND_IN = "手元で実物", "デプロイ後", "代役"
STAGES = (LOCAL, DEPLOYED, STAND_IN)
STAGE_ROW = re.compile(r"^\|\s*(R\d+)\s*\|\s*([^|]*?)\s*\|", re.M)
REASON = re.compile(r"^- (手元でできない理由|代役の理由|unverified の承認):[ \t]*(R\d+)[ \t]*（[^）\s][^）]*）[ \t]*$", re.M)
QA_ROW4 = re.compile(r"^\|\s*(R\d+)\s*\|[^|]*\|[^|]*\|([^|]*)\|", re.M)  # | 要件 | 段 | 確かめ方 | 合格基準 |
COMMAND = re.compile(r"^\$ \S")
READ_CAP = 256 * 1024  # Stop hook の時間の上限に収めるため、証拠は頭だけを読む
REASON_ANY = re.compile(r"^- (手元でできない理由|代役の理由|unverified の承認):.*$", re.M)
NEEDS = {DEPLOYED: "手元でできない理由", STAND_IN: "代役の理由"}

# autopilot.py と deploy.py が借りる spec の文の読み取りと repo の場所（下の層に置き、autopilot.py に依らない）
TEST_PATH = re.compile(r"(^|/)(tests?|__tests__)/|(^|/)test_[^/]*$|_test\.[^/]+$|\.(test|spec)\.[^/]+$")
NOT_CODE = re.compile(r"(^|/)docs/|^\.autopilot-qa/")  # テストと docs/ の下は数えない。.md は docs/ の外なら数える（skill・agent など .md が本体の repo があるため）
REQ = re.compile(r"^- (R\d+):\s*(\S.*)$", re.M)
BUDGET = re.compile(r"^- 予算:\s*(\d+)\s*分\s*$", re.M)
COMMENT = re.compile(r"^\s*<!--.*-->\s*$")
COMMENT_BLOCK = re.compile(r"<!--.*?-->", re.S)
QA_ROW = re.compile(r"^\|\s*(R\d+)\s*\|\s*(pass|fail|unverified)\s*\|(.*)\|\s*$")  # 証拠の欄は 1 つの (.*) にし、前後の空白は check で除く（空白の分け方で後戻りしない）
MAX_REWORKS = 2  # references/dead-end.md の段: 作り直しは要件ごとに 2 回


def repo_root(start):
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=start, capture_output=True, text=True)
    except OSError:
        return Path(start)
    return Path(out.stdout.strip()) if out.returncode == 0 else Path(start)


def section(text, name):
    m = re.search(rf"^## {re.escape(name)}\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    return m.group(1) if m else None


def classify(text, kinds):
    """全行を、空行・1 行のコメント・kinds（名前→正規表現）のどれか 1 つに分ける。
    (受けた行の (名前, match) の一覧, 分けられない行の一覧) を返す。読み飛ばしは kinds の宣言だけで決まる。"""
    kept, bad = [], []
    for line in text.splitlines():
        if not line.strip() or COMMENT.match(line):
            continue
        for name, pattern in kinds:
            m = pattern.match(line)
            if m:
                kept.append((name, m))
                break
        else:
            bad.append(line.strip())
    return kept, bad


def requirement_lines(text):
    """要件の節を読み、(要件の (id, 本文) の一覧, 読めない行の一覧) を返す。"""
    kept, bad = classify(section(text, "要件") or "", [("req", REQ)])
    return [m.groups() for _, m in kept], bad


def requirements(text):
    return dict(requirement_lines(text)[0])


def git_lines(root, *args):
    """git の出力を NUL 区切りで読む。失敗したら例外を投げる（数えられないまま通さない）。"""
    out = subprocess.run(["git", "-c", "core.quotePath=false", args[0], "-z", *args[1:]], cwd=root, capture_output=True, text=True)
    if out.returncode not in (0, 1):
        raise RuntimeError(out.stderr.strip() or f"git {args[0]} が {out.returncode} で終わった")
    return [f for f in out.stdout.split("\0") if f]


def plan(text):
    """({要件: 段}, {(理由の種類, 要件)}, 形の読めない理由の行)。段の列が無い旧い表は {}。"""
    body = COMMENT_BLOCK.sub("", section(text, "QA の方向性") or "")
    header = next((line for line in body.splitlines() if line.startswith("|")), "")
    stages = dict(STAGE_ROW.findall(body)) if re.match(r"^\|\s*要件\s*\|\s*段\s*\|", header) else {}
    reasons = {(m.group(1), m.group(2)) for m in REASON.finditer(body)}
    bad = [m.group(0) for m in REASON_ANY.finditer(body) if not REASON.match(m.group(0))]
    return stages, reasons, bad


def lint(text, reqs):
    errors = []
    stages, reasons, bad = plan(text)
    if not stages:
        return ["「## QA の方向性」の表に段の列が無い（`| 要件 | 段 | 確かめ方 | 合格基準 |`。段は " + "・".join(STAGES) + "）"]
    for rid in reqs:
        stage = stages.get(rid)
        if stage is not None and stage not in STAGES:
            errors.append(f"{rid} の段が読めない（{'・'.join(STAGES)} のどれか。今は「{stage}」）")
        if stage in NEEDS and (NEEDS[stage], rid) not in reasons:
            errors.append(f"{rid} は段が{stage}なので、QA の方向性に `- {NEEDS[stage]}: {rid}（<理由>）` を書く")
    body = COMMENT_BLOCK.sub("", section(text, "QA の方向性") or "")
    errors += [f"{rid} の合格基準が unverified なので、QA の方向性に `- unverified の承認: {rid}（<理由>）` を書く"
               for rid, criteria in QA_ROW4.findall(body) if "unverified（" in criteria and ("unverified の承認", rid) not in reasons]
    errors += [f"理由の行の形が読めない（`- <種類>: R<n>（<理由>）`）: {line}" for line in bad]
    errors += [f"{kind} の {rid} は要件に無い" for kind, rid in sorted(reasons) if rid not in reqs]
    return errors


def deployed_reqs(text):
    """段がデプロイ後の要件。段の列が無い旧い spec は、全部をデプロイ後として扱う（マージ後の QA を省かない）。"""
    stages, _, _ = plan(text)
    reqs = requirements(text)
    return [r for r in reqs if stages.get(r, DEPLOYED) == DEPLOYED] if stages else list(reqs)


def read_head(f):
    with open(f, "rb") as fh:
        return fh.read(READ_CAP).decode("utf-8", errors="replace")


def ran(text):
    """実行の出力の形: `$ <コマンド>` の行と、その後の空でない出力の行。"""
    seen = False  # 後ろから読み、出力の行を見た後に `$ ` の行があれば実行の形
    for line in reversed(text.splitlines()):
        if COMMAND.match(line):
            if seen:
                return True
        elif line.strip():
            seen = True
    return False


def head_rows(text):
    """先頭から続く `- <キー>: <値>` の行（頭の宣言）。[(キー, 値)]。"""
    rows = []
    for line in text.splitlines():  # 正規表現を使わない（値の長い空白で後戻りしない）
        key, colon, value = line[2:].partition(":") if line.startswith("- ") else ("", "", "")
        if not colon or not key or key[0].isspace() or "：" in key:
            break
        rows.append((key, value.strip(" \t")))
    return rows


def approved(text, rid):
    return ("unverified の承認", rid) in plan(text)[1]


def declared_for(text, merge_sha):
    """デプロイ後の evidence の頭の宣言: `- commit: <最後のマージの sha（7 字以上の頭か全部）>` と `- 結果: Confirmed` がちょうど 1 本ずつ。
    頭の外の宣言・2 本以上・ほかの値は通さない。"""
    rows = head_rows(text)
    commits = [v for k, v in rows if k == "commit"]
    results = [v for k, v in rows if k == "結果"]
    if len(commits) != 1 or len(results) != 1 or results[0] != "Confirmed" or not merge_sha:
        return False
    return same_commit(commits[0], merge_sha)


def same_commit(c, sha):
    return bool(c and sha) and (c == sha or (len(c) >= 7 and sha.startswith(c)))


GIT_TIMEOUT_SEC = 5  # Stop hook の予算（20 秒）に収めるため、git の 1 回ごとに切る
FULL_SHA = re.compile(r"^[0-9a-f]{40}([0-9a-f]{24})?$")


def same_outside_as(root, commit, sha):
    """`- commit:` の値と巡の sha の間で、spec の置き場の外のファイルが同じ。値は rev-parse で commit の sha に引き当て、
    引き当てた完全な sha だけを diff に渡す（値を option として読ませない）。git が 0 以外・引き当たらない場合は False、
    timeout は TimeoutExpired をそのまま上げる（呼び出し側が残りの巡を試さずに落とす）。"""
    try:
        found = subprocess.run(["git", "rev-parse", "--verify", "--quiet", "--end-of-options", f"{commit}^{{commit}}"],
                               cwd=root, capture_output=True, text=True, timeout=GIT_TIMEOUT_SEC)
        resolved = found.stdout.strip()
        if found.returncode != 0 or not FULL_SHA.match(resolved):
            return False
        same = subprocess.run(["git", "diff", "--quiet", resolved, sha, "--", *carry.OUTSIDE],
                              cwd=root, capture_output=True, timeout=GIT_TIMEOUT_SEC)
    except subprocess.TimeoutExpired:
        raise
    except (OSError, subprocess.SubprocessError):
        return False
    return same.returncode == 0


def checked_in_review(text, mtime, rid, reviews, approved_at, root):
    """手元で実物の出力が、今の承認の評価役の巡に結び付くか: 頭の `- commit:` が、その要件が最後に high になった巡より後の巡の sha の
    どれか（または、その巡の sha との間で spec の置き場の外が同じ commit）で、出力がその high の巡（無ければ承認）より後に書かれている。
    前の承認・fail の巡の出力は通らない。"""
    commits = [v for k, v in head_rows(text) if k == "commit"]
    if len(commits) != 1:
        return False
    last_high = max((i for i, r in enumerate(reviews) if rid in (r.get("high") or [])), default=-1)
    since = float(reviews[last_high].get("at", 0)) if last_high >= 0 else float(approved_at or 0)
    if mtime <= since:
        return False
    counted = reviews[last_high + 1:]
    if any(same_commit(commits[0], r.get("sha")) for r in counted):
        return True
    try:  # 新しい巡から当て、最初に同じと分かった巡で止める
        return any(r.get("sha") and same_outside_as(root, commits[0], r["sha"]) for r in reversed(counted))
    except subprocess.TimeoutExpired:
        return False


def check(d, rows, parked_reqs, deployed_at, stage="all", merge_sha=None, reviews=(), approved_at=0):
    """qa.md の行（{要件: (結果, 証拠)}）に段ごとの要求を当てる。deployed_at は最後のマージの commit のデプロイが通った時刻か None。
    stage が pr（PR の前）なら、デプロイ後の要件はまだ確かめられないので unverified を通し、pass を落とす。
    段の列の無い旧い spec には当てない（承認したときの規則のまま）。"""
    text = (d / "spec.md").read_text(encoding="utf-8")
    stages, reasons, _ = plan(text)
    if not stages:
        return []
    errors = []
    root = repo_root(d)
    for rid, (result, _) in rows.items():
        stage_of = stages.get(rid)
        if stage_of == DEPLOYED and stage == "pr":
            if result == "pass":
                errors.append(f"{rid} は段がデプロイ後なので、PR の前は pass にしない（`unverified（デプロイ後に確かめる）`）")
            continue
        if result == "unverified" and ("unverified の承認", rid) not in reasons and rid not in parked_reqs:
            errors.append(f"{rid} は unverified だが、spec の `- unverified の承認: {rid}（<理由>）` も、"
                          f"その要件を積んだ park も無い（本物で確かめるか、積む）")
        if result != "pass" or stage_of not in (LOCAL, DEPLOYED):
            continue
        if stage_of == LOCAL:
            f = d / "evidence" / f"{rid}.txt"
            if not f.is_file() or f.stat().st_size == 0:
                errors.append(f"{rid} は段が{LOCAL}なので、実行の出力を {d.name}/evidence/{rid}.txt に残す（空でないファイル）")
            elif not ran(read_head(f)):
                errors.append(f"{rid} の {d.name}/evidence/{rid}.txt に、実行したコマンドの行（`$ <コマンド>`）とその出力が無い")
            elif not checked_in_review(read_head(f), f.stat().st_mtime, rid, list(reviews), approved_at, root):
                errors.append(f"{rid} の evidence/{rid}.txt の頭の `- commit:` が、{rid} を最後に確かめた評価役の巡の tip でない"
                              "（前の承認か fail の巡の出力。確かめ直して、渡された tip を頭に書いて書き直す）")
            continue
        f = d / "evidence" / f"{rid}.txt"  # デプロイ後は baseline（R<n>.baseline.txt など）と分けて名前を決める
        if deployed_at is None:
            errors.append(f"{rid} は段がデプロイ後なのに、最後のマージの commit のデプロイを確かめた記録が無い（pass にできない）")
        elif not f.is_file() or f.stat().st_size == 0:
            errors.append(f"{rid} は段がデプロイ後なので、実環境の出力を {d.name}/evidence/{rid}.txt に残す（空でないファイル）")
        elif f.stat().st_mtime <= deployed_at:
            errors.append(f"{rid} の evidence/{rid}.txt がデプロイの前のもの。デプロイの後に実環境で確かめ直して書き直す")
        elif not declared_for(read_head(f), merge_sha):
            errors.append(f"{rid} の evidence/{rid}.txt の頭に `- commit: <最後のマージの sha>` と `- 結果: Confirmed` が 1 本ずつ無い"
                          "（Insufficient は fail、Inconclusive は unverified にする）")
        elif not ran(read_head(f)):
            errors.append(f"{rid} の evidence/{rid}.txt に、実行したコマンドの行（`$ <コマンド>`）とその出力が無い")
    return errors
