#!/usr/bin/env python3
"""まとめて承認した spec を、夜の間に 1 本ずつ着手する（PR 7）。

  autopilot.py approve <dir> --by .. --queue   承認だけする（phase=queued。予算の時計は着手で始まる）
  lineup.py next                               次の spec に着手する（人の発言は要らない）
  lineup.py hold <dir> --pr <n>                必須レビューの承認待ちの spec を脇に置き（wait、kind=review）、次へ進む

- 順はこのセッションの記録の並び（承認した順）。依る spec は spec.md の「## 制約」の `- 依る spec: <ディレクトリ名>` に書く
- 着手は、承認のときのハッシュが同じで、着手の時点の lint が通るときだけ。通らなければ blocked にする（queued のまま残さない）
- 依る spec が block なら blocked。依る spec が終わっていれば、その先端（マージしたならマージの commit、レビュー待ちならその PR の head）の上に載せ替えて着手する
- レビュー待ちは、GitHub の承認が付き、head が記録と同じなら building に戻す（人の発言の代わりに GitHub の承認を根拠にする）
"""
import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import autopilot as ap  # noqa: E402

AFTER = re.compile(r"^- 依る spec:\s*(\S+)\s*$", re.M)
WAITING = ("queued", "building", "wait")  # 依る spec がこの phase なら、まだ着手しない
NEXT = "lineup.py next"


def after_name(d):
    return (AFTER.search(ap.COMMENT_BLOCK.sub("", ap.section((d / "spec.md").read_text(encoding="utf-8"), "制約") or "")) or [None, None])[1]


def minutes(d):
    """承認から夜の終わりまでの見込み（予算とマージ後の予算）。"""
    import overnight

    budget, post = overnight.budgets((d / "spec.md").read_text(encoding="utf-8"))
    return budget + post


def session_of(d):
    return os.environ.get("CLAUDE_CODE_SESSION_ID") or ap.last_user_prompt(d)[1]


def queue_lint(d):
    """approve --queue の lint。前に並ぶ spec の予算を足して夜通しの前提を見る。依る spec があれば、
    init の時点との突き合わせ（前提の path・影響範囲・大きさ）は着手のときに回す。"""
    ahead = [x for x in ap.recorded_specs(session_of(d)) if x.resolve() != d.resolve()
             and ap.load_state(x).get("phase") in ("queued", "building")]
    extra = sum(minutes(x) for x in ahead)
    name = after_name(d)
    if name is None:
        return ap.lint(d, at_approve=True, ahead=extra)
    errors, warnings = ap.lint(d, at_approve=True, base=False, ahead=extra)
    if not any(x.name == name for x in ap.recorded_specs(session_of(d))):
        errors.append(f"依る spec {name} がこのセッションの記録に無い。依る spec を先に承認する")
    text = ap.COMMENT_BLOCK.sub("", ap.section((d / "spec.md").read_text(encoding="utf-8"), "制約") or "")
    if ap.stated_size(text)[0] == "S":
        errors.append("依る spec のある spec は、承認の時点で S の試作を作れない。大きさを M 以上にする")
    return errors, warnings


def enqueue(d, s, by, session, warnings):
    name = after_name(d)
    after = next((str(x.resolve()) for x in ap.recorded_specs(session) if x.name == name), None) if name else None
    s.update(phase="queued", queued_from=s.get("phase"), queued_at=time.time(), approved_by=by, spec_sha256=ap.sha(d), after=after)
    ap.take_over(d, session, "承認")
    ap.save_state(d, s)
    return ap.report([], warnings, f"queued: 承認した。{NEXT} で承認した順に着手する（人の発言は要らない）")


def begin(d, s, by, prev):
    """承認した spec を自走中（building）にする。予算の時計はここから。"""
    import overnight

    budget, post = overnight.budgets((d / "spec.md").read_text(encoding="utf-8"))
    history = s.get("history", [])
    if prev != "discovery":
        history.append({**{k: s.get(k) for k in ("approved_at", "approved_by", "blocked", "done_at", "anomalies", "reviews",
                                                 "fails", "streak", "reworks", "post_budget_min", "paused_sec", *overnight.ROUND_KEYS)}, "phase": prev})
    for k in ("size_by_user", "done_at", "anomalies", "queued_from", *overnight.ROUND_KEYS):  # 前の巡の記録は history に移した
        s.pop(k, None)
    s.update(phase="building", approved_at=time.time(), approved_by=by, spec_sha256=ap.sha(d), budget_min=budget,
             post_budget_min=post, history=history, blocked=None, paused_sec=0, reviews=[], fails={}, streak={}, reworks={})
    return budget


def block(d, s, reason):
    import overnight

    if s.get("queued_from", "discovery") != "discovery" and (s.get("approved_at") is not None or s.get("blocked")):
        # 前の巡（最上位の approved_at・blocked・paused_sec）を history に移し、最上位は空ける。次の begin が同じ巡を移し直さない
        s["history"] = list(s.get("history") or []) + [{k: s.get(k) for k in ("approved_at", "blocked", "done_at", "paused_sec", "merges")}]
        s.update(approved_at=None, paused_sec=0, done_at=None)
    s.update(phase="blocked", blocked={"req": "着手", "reason": reason, "evidence": NEXT, "at": time.time()})
    ap.save_state(d, s)
    ap.release(d)
    __import__("runlog").record(d, s, "block", s["blocked"]["at"], top_end=None)
    print(f"blocked: {d.name}（{reason}）")
    overnight.notify(d)


def git(root, *args):
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=120)


def base_of(dep, ds):
    """依る spec の先端。マージしたならマージの commit、まだなら依る spec の HEAD。"""
    if review_wait(ds):  # レビュー待ちの依る spec は、その PR の head の上に載せる
        return ds["wait"].get("head")
    merges = ds.get("merges") or []
    if merges and merges[-1].get("sha"):
        return merges[-1]["sha"]
    out = git(ap.repo_root(dep), "rev-parse", "HEAD")
    return out.stdout.strip() if out.returncode == 0 else None


def put_on(d, base):
    """spec の repo の HEAD を base の上に載せる。誤りの文か None。"""
    root = ap.repo_root(d)
    if git(root, "cat-file", "-e", f"{base}^{{commit}}").returncode != 0:
        git(root, "fetch", "--quiet")
    if git(root, "merge-base", "--is-ancestor", base, "HEAD").returncode == 0:
        return None
    out = git(root, "rebase", base)
    if out.returncode != 0:
        git(root, "rebase", "--abort")
        return f"依る spec の先端 {base[:8]} の上に載せ替えられない（{(out.stderr or out.stdout).strip()[:200]}）"
    return None


def dependency(s):
    """(依る spec のディレクトリ, その state)。依る spec が無ければ (None, None)。"""
    if not s.get("after"):
        return None, None
    dep = Path(s["after"])
    return dep, ap.load_state(dep)


def start(d, s):
    """queued の spec に着手する。着手できたら True。着手できないなら blocked にして False。"""
    if ap.sha(d) != s.get("spec_sha256"):
        block(d, s, "承認の後に spec.md か ADR の先頭が変わった。示し直して承認を受ける")
        return False
    dep, ds = dependency(s)
    if dep is not None:
        base = base_of(dep, ds)
        err = put_on(d, base) if base else f"依る spec {dep.name} の先端が読めない"
        if err:
            block(d, s, err)
            return False
        s["start"] = base
        ap.save_state(d, s)
    errors, _ = ap.lint(d, at_approve=True, base=True)
    if errors:
        block(d, s, "着手の時点で lint が通らない: " + " / ".join(errors))
        return False
    budget = begin(d, s, s.get("approved_by"), s.get("queued_from", "discovery"))
    ap.save_state(d, s)
    print(f"started: {d}。予算 {budget} 分。/autopilot の C の手順で進める")
    return True


def specs(session):
    return [(d, ap.load_state(d)) for d in ap.recorded_specs(session)]


def startable(s):
    """queued の spec に今着手してよいか（依る spec が終わったか block か、依る spec が無い）。"""
    if s.get("phase") != "queued":
        return False
    dep, ds = dependency(s)
    return dep is None or ds.get("phase") not in WAITING or review_wait(ds)


def review_wait(s):
    return s.get("phase") == "wait" and (s.get("wait") or {}).get("kind") == "review"


def demand(rows, over_budget):
    """Stop hook の要求の文か None。rows は (dir, state)。over_budget は予算の 2 倍を過ぎた building の dir の集合。"""
    if not any(startable(s) or review_wait(s) for _, s in rows):
        return None
    building = [d for d, s in rows if s.get("phase") == "building"]
    if any(d not in over_budget for d in building):
        return None
    if building:
        return (f"{'・'.join(d.name for d in building)} は予算の 2 倍を過ぎた。満たせない要件を autopilot.py block で記録してから、"
                f"{NEXT} で次の spec に着手する（まとめて承認した spec が残っている）")
    return f"まとめて承認した spec が残っている。{NEXT} で次の spec に着手する（人に聞かずに続ける）"


def resume(d, s, why):
    w = s["wait"]
    s.setdefault("history", []).append({"phase": "wait", **w})
    s.update(phase="building", wait=None, paused_sec=s.get("paused_sec", 0) + time.time() - float(w["at"]))
    ap.save_state(d, s)
    print(f"resumed: {d}。{why}")


def approved(w):
    import overnight

    try:
        v = overnight.gh_json("pr", "view", str(w["pr"]), "--json", "reviewDecision,headRefOid")
    except Exception:
        return False  # 読めないときは未承認とみなして次へ進む
    return v.get("reviewDecision") == "APPROVED" and v.get("headRefOid") == w.get("head")


def cmd_next(a):
    session = os.environ.get("CLAUDE_CODE_SESSION_ID")
    rows = specs(session)
    building = [d for d, s in rows if s.get("phase") == "building"]
    if building:
        print(f"ERROR: {building[0]} が自走中。先にそれを進める（予算の 2 倍を過ぎたなら autopilot.py block で記録する）")
        return 1
    for d, s in rows:
        if review_wait(s) and approved(s["wait"]):
            resume(d, s, "レビューの承認が付いた。マージから続ける（references/after-pr.md）")
            return 0
    for d, _ in rows:
        s = ap.load_state(d)  # 前の spec の block で、依る spec の phase が変わっている
        if not startable(s):
            continue
        dep, ds = dependency(s)
        if dep is not None and ds.get("phase") == "blocked":
            block(d, s, f"依る spec {dep.name} が block")
            continue
        if start(d, s):
            return 0
    for d, s in rows:
        if review_wait(s):
            resume(d, s, f"着手できる spec が残っていない。overnight.py await {d} --kind review --pr {s['wait']['pr']} で承認を待つ")
            return 0
    print("着手できる spec は無い")
    return 0


def cmd_hold(a):
    import overnight

    d = Path(a.dir)
    s = ap.load_state(d)
    if s.get("phase") != "building":
        ap.refuse(s, "hold は自走中（building）だけ受ける")
    gate = overnight.production_errors(d, s, done=False)
    if gate:
        sys.exit(f"本番が良くないまま脇に置かない: {gate[0]}")
    v = overnight.gh_json("pr", "view", str(a.pr), "--json", "reviewDecision,headRefOid")
    s.update(phase="wait", wait={"reason": f"PR {a.pr} のレビューの承認待ち", "kind": "review", "pr": a.pr,
                                 "head": v.get("headRefOid"), "at": time.time()})
    ap.save_state(d, s)
    print(f"hold: PR {a.pr} のレビューの承認を待つ間、{NEXT} で次の spec に着手する")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="lineup.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("next")
    h = sub.add_parser("hold")
    h.add_argument("dir")
    h.add_argument("--pr", type=int, required=True)
    a = p.parse_args(argv)
    return {"next": cmd_next, "hold": cmd_hold}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
