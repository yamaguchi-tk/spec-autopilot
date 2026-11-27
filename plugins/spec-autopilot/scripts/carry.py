"""承認し直しのとき、コードが同じならマージとデプロイの記録を持ち越す（docs/adr/2026-11-27-reapproval-carry-merge.md）。

持ち越すかは、最後のマージの PR の head と今の HEAD の間で、spec の置き場（docs/specs と docs/adr）の外が同じかで決める。
照合は git の pathspec に任せ、決められないときは持ち越さない（止める側に倒す）。"""
import subprocess

OUTSIDE = (".", ":(exclude)docs/specs", ":(exclude)docs/adr")
NOT_CARRIED = "持ち越さなかった: "


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


def holds_head(root, s, merge_head):
    """持ち越した spec（awaits_since がある）の「今の HEAD を含むマージ」。マージの head と今の HEAD の間が spec の置き場の中だけ。"""
    return bool(s.get("awaits_since")) and same_outside(root, merge_head)
