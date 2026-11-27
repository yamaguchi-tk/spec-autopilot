"""「大きさが L になった」の NOTE（`autopilot.py done` と、`check --stage pr` が出す）。

PR を作る前に、PR を分けるかを決められるようにする。範囲がマージ以上の spec は done が PR の後になるので、check --stage pr でも出す。
"""


def notes(autopilot, d, s):
    """申告の大きさか数えた大きさが L のとき出す NOTE の本文の一覧を返す（NOTE: は付けない）。
    大きさの行が読めないときは L とみなす（cmd_size と同じ向き）。新しく作る repo は数えない。"""
    text = (d / "spec.md").read_text(encoding="utf-8")
    out = []
    stated, size_err = autopilot.stated_size(autopilot.COMMENT_BLOCK.sub("", autopilot.section(text, "制約") or ""))
    size, detail = None, "数えていない"
    if size_err:
        stated, detail = "L", size_err
    if not autopilot.is_new_repo(s):
        try:
            size, _, detail, _ = autopilot.counted_size(d, autopilot.COMMENT_BLOCK.sub("", autopilot.section(text, "影響範囲") or ""))
        except RuntimeError as e:
            out.append(f"大きさを数えられない（{e}）。PR の大きさは差分を見て決める")
    if "L" in (stated, size):  # 合意し直しと自走中に育った L も、PR を作る前に受け持つ
        out.append(f"{autopilot.SPLIT_PR}（申告 {stated or 'なし'}・{detail}）")
    return out
