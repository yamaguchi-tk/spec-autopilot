#!/usr/bin/env python3
"""人との spec 合意を省く軽量フロー。

  light.py approve <dir> --source <Issue の URL か依頼文の要約>   人の返事を待たずに自走を始める（phase=building、light=true）

- 入れるのは、受入条件が Issue に書いてあるか、依頼文だけで要件・範囲・完了が決まるときだけ（commands/autopilot.md の L）
- 自走の範囲は、合意ありと同じく spec の `- 範囲:` で決める。ただし `デプロイの起動:` と `ロールバック:` はコマンドにできない（人が見ないまま打たない）。
  デプロイの workflow が無い repo は、`デプロイの起動:` を「なし（マージした commit で QA）」にして、マージの後に QA へ進む（打つコマンドは無い）
- 止まる条件は、保護された path（下の既定と、起点の commit の `.spec-autopilot/protected-paths`）に触れたとき。init の時点の
  commit から、PR が持ち込む差（HEAD・index・作業ツリー）と追っていないファイルの path で機械的に決め、照合は git の glob pathspec に任せる。
  init より前の commit・git が無視するファイル・途中の commit で触れて戻したもの・spec の置き場の中の `/` を含む pattern は見ない（手元の書き換えは防がない。限界）。承認の前から当たっているなら approve しない。spec.md が承認の後に変わったとき（範囲が広がる）は、合意ありと同じく check が止める
- 印は block・done の後の approve でも外さない（その返事は spec の全体を見たものではない）。合意ありで進めるなら spec を作り直す

範囲: 軽量フローの承認と保護 path の判定だけを足す。合意ありの run の挙動は変えない
想定する脅威: 事故（agent が範囲を広げる・保護 path に触れる）。敵対的な agent が state.json を書き換えて印を消すことは防がない
やらないこと: 影響範囲の宣言と差分の突き合わせ、hook での編集・`gh pr merge` の拒否、利用する repo の設定の中身の意味の検査（Git LFS などの filter の pointer、見える文字の取り違え。種類・UTF-8・表示できない文字だけは確かめて止める）、git が無視するファイル・途中の commit の判定
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import autopilot as ap  # noqa: E402
from light_rules import EMPTY_TREE, command_errors, hits  # noqa: E402


def cmd_approve(a):
    d = Path(a.dir)
    import lineup
    s = ap.load_state(d)
    if s.get("phase") != "discovery":
        sys.exit(f"軽量フローの approve は壁打ち中（discovery）だけ受ける（phase={s.get('phase')}）")
    if not a.source.strip():
        sys.exit("--source（Issue の URL か依頼文の要約）は空にできない")
    errs, warnings = ap.lint(d, at_approve=True)
    adr = ap.adr_error(d)
    if adr:
        errs.append(adr)
    if lineup.after_name(d):
        errs.append("依る spec のある spec は軽量フローで始めない（合意ありで --queue で承認する）")
    text = (d / "spec.md").read_text(encoding="utf-8")
    if ap.stated_size(ap.COMMENT_BLOCK.sub("", ap.section(text, "制約") or ""))[0] != "S":
        errs.append("軽量フローは `- 大きさ: S` の spec だけで始める（予算も人が見ないので、小さい修正に限る）")
    errs += command_errors(text)
    if errs:
        ap.report(errs, warnings, "")
        return 1
    base = s.get("start") or EMPTY_TREE  # init の時点（S の試作の commit も判定に入れる）。新しく作る repo は空の木から
    try:
        before = hits(d, {"light_base": base})
    except (RuntimeError, OSError, ValueError) as e:
        sys.exit(f"保護された path を確かめられない（{e}）ので承認しない")
    if before:  # init より後の変更が、もう保護 path に当たっている
        sys.exit(f"保護された path に承認の前から当たっている: {', '.join(before)}。軽量フローでは始めない（合意ありで進めるか、人が片づける）")
    budget = lineup.begin(d, s, f"軽量フロー（人の承認なし）: {a.source.strip()}", "discovery")
    s.update(light=True, light_base=base)
    ap.take_over(d, os.environ.get("CLAUDE_CODE_SESSION_ID"), "軽量フローの承認")
    ap.save_state(d, s)
    ap.report([], warnings, f"approved（軽量フロー）: 予算 {budget} 分")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="light.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    x = sub.add_parser("approve")
    x.add_argument("dir")
    x.add_argument("--source", required=True)
    a = p.parse_args(argv)
    return cmd_approve(a)


if __name__ == "__main__":
    sys.exit(main())
