"""承認し直しのとき、コードが同じならマージとデプロイの記録を持ち越す（docs/adr/2026-11-27-reapproval-carry-merge.md）。

持ち越すかは、最後のマージの PR の head と今の HEAD の間で、spec の置き場（docs/specs と docs/adr）の外が同じかで決める。
照合は git の pathspec に任せ、決められないときは持ち越さない（止める側に倒す）。"""
import subprocess

OUTSIDE = (".", ":(exclude)docs/specs", ":(exclude)docs/adr")
NOT_CARRIED = "持ち越さなかった: "
DISPATCH_CARRIED = "dispatch を引き継いだ: "
DISPATCH_NOT_CARRIED = "dispatch を引き継がなかった: "


def same_outside(root, head):
    """head と今の HEAD の間で、spec の置き場の外のファイルが同じ。git が 0 で終わったときだけ True（差分あり・読めない・例外は False）。"""
    if not head:
        return False
    try:
        out = subprocess.run(["git", "diff", "--quiet", head, "HEAD", "--", *OUTSIDE], cwd=root, capture_output=True, timeout=120)
    except (OSError, subprocess.SubprocessError):
        return False
    return out.returncode == 0


def why_not(root, s, prev):
    """持ち越さない理由。持ち越せるなら None。"""
    merges = s.get("merges") or []
    if prev != "blocked":
        return f"前の phase が {prev}（blocked の承認し直しだけ持ち越す）"
    if s.get("rolled_back"):
        return "前の巡でコマンドで本番を戻した（戻した記録は持ち越さない）"
    if merges[-1].get("rollback"):
        return "最後のマージが戻しのマージ"
    if not merges[-1].get("head"):
        return "マージの記録に PR の head が無い"
    if not s.get("approved_at"):
        return "前の承認の時刻が無い（着手の block の後）"
    if not same_outside(root, merges[-1]["head"]):
        return "最後のマージの後に、spec の置き場の外のファイルが変わったか、git で比べられない"
    return None


def plan(root, s, prev):
    """(持ち越すマージの記録, print する 1 行)。前の巡にマージが無ければ ([], None)。"""
    merges = s.get("merges") or []
    if not merges:
        return [], None
    reason = why_not(root, s, prev)
    if reason:
        return [], NOT_CARRIED + reason
    return list(merges), f"持ち越した: マージ {len(merges)} 件（PR {'、'.join(str(m.get('pr')) for m in merges)}）"


def dispatch_plan(root, d, s, prev):
    """(dispatch と handoff を持ち越すか, print する 1 行)。blocked の承認し直しだけ。最後の dispatch を閉じた handoff のうち最後のものの tip と
    今の HEAD で、spec の置き場の外が同じなら持ち越す（docs/adr/2026-11-28-reapproval-carry-dispatch.md）。前の phase が blocked でなければ (False, None)。"""
    if prev != "blocked":
        return False, None
    dispatches = s.get("dispatches") or []
    if not dispatches:
        return False, DISPATCH_NOT_CARRIED + "前の巡に dispatch が無い"
    n = len(dispatches) - 1
    closed = [h for h in s.get("handoffs") or [] if h.get("dispatch") == n]
    if not closed:
        return False, DISPATCH_NOT_CARRIED + "最後の dispatch が handoff で閉じていない"
    if not same_outside(root, closed[-1].get("tip")):
        return False, DISPATCH_NOT_CARRIED + "最後の handoff の後に、spec の置き場の外のファイルが変わったか、git で比べられない"
    tasks = dispatches[-1].get("tasks") or []
    return True, f"{DISPATCH_CARRIED}{', '.join(tasks)}。dispatch を打たずに overnight.py handoff {d} {' '.join(f'--task {t}' for t in tasks)} から進む"


def holds_head(root, s, merge_head):
    """持ち越した spec（awaits_since がある）の「今の HEAD を含むマージ」。マージの head と今の HEAD の間が spec の置き場の中だけ。"""
    return bool(s.get("awaits_since")) and same_outside(root, merge_head)


def this_round_timeouts(records, s):
    """上限を過ぎた待ち。持ち越した spec でも、今の承認より後のものだけ（前の巡の timeout は新しい巡で数え直す）。
    成功・失敗の事実は、持ち越した分も読む awaits の記録のまま使う。"""
    approved = float(s.get("approved_at") or 0)
    return [a for a in records if a.get("result") == "timeout" and a["at"] > approved]
