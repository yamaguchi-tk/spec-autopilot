"""承認の対象のハッシュ（head_and_body・sha）と、承認した spec を自走中（building）にする begin。
autopilot.py・lineup.py・light.py が使う下の層（stages・consent・deploy・carry だけに依る）。"""
import hashlib
import time

import carry
import deploy
from consent import numberless
from stages import repo_root, section


def head_and_body(text):
    """spec を、最初の `## ` より前（先頭）と、それ以降（作り方の節を除く本文）に分ける。"""
    head, _, body = text.partition("\n## ")
    body = "\n## " + body if body else ""
    how = section(body, "作り方")
    if how is not None:
        body = body.replace(how, "\n", 1)
    return head, body


def sha(d):
    """承認の対象のハッシュ。作り方の節は、自走中に作り直してよい（ADR に残す）ので外す。
    先頭の `- ADR:` 行の連番の桁は、並行の branch との番号の取り合いで改番されるので外す（ディレクトリと slug は残す）。
    本文は正規化しない。本文が自分の連番の ADR を名前・番号で書くのは lint が承認の前に止める。ADR があるかは check が確かめる。"""
    head, body = head_and_body((d / "spec.md").read_text(encoding="utf-8"))

    return hashlib.sha256((numberless(head) + body).encode("utf-8")).hexdigest()


def begin(d, s, by, prev):
    """承認した spec を自走中（building）にする。予算の時計はここから。"""
    budget, post = deploy.budgets((d / "spec.md").read_text(encoding="utf-8"))
    history = s.get("history", [])
    kept, note = carry.plan(repo_root(d), s, prev)  # コードが同じなら、前の巡のマージとデプロイの記録を持ち越す
    since = s.get("awaits_since") or s.get("approved_at")
    if prev != "discovery":
        history.append({**{k: s.get(k) for k in ("approved_at", "approved_by", "blocked", "done_at", "anomalies", "reviews",
                                                 "fails", "streak", "reworks", "post_budget_min", "paused_sec", "light", *deploy.ROUND_KEYS)}, "phase": prev})
    ds = s.get("dispatches") or []
    keep = ("dispatches", "handoffs") if ds and all(x.get("prototype") for x in ds) else ()  # 承認の前の試作の dispatch（印は dispatch が打つ）は、承認の後の handoff で閉じる
    for x in ds if keep else ():
        x.pop("prototype")  # 持ち越したら印を外す。次の巡の再承認では history に移す
    dispatch_kept, dispatch_note = (False, None) if keep else carry.dispatch_plan(repo_root(d), d, s, prev)  # 閉じた dispatch で spec の外が同じなら、実装役を起こさず handoff から進める
    keep = ("dispatches", "handoffs") if dispatch_kept else keep
    for k in (*(("light", "light_base") if prev == "discovery" else ()), "size_by_user", "done_at", "anomalies", "queued_from", "awaits_since", *(k for k in deploy.ROUND_KEYS if k not in keep)):  # 前の巡の記録は history に移した
        s.pop(k, None)
    now = time.time()
    s.update(phase="building", approved_at=now, approved_by=by, spec_sha256=sha(d), budget_min=budget,
             post_budget_min=post, history=history, blocked=None, paused_sec=0, reviews=[], fails={}, streak={}, reworks={})
    if kept:
        s.update(merges=kept, merged_at=now, paused_at_merge=0, awaits_since=since)  # マージ後の予算の時計は自走に戻した時刻から数え直す
    if note:
        print(note)
    if dispatch_note:
        print(dispatch_note)
    return budget
