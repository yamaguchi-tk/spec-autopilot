#!/usr/bin/env python3
"""人との spec 合意を省く軽量フロー。

  light.py approve <dir> --source <Issue の URL か依頼文の要約>   人の返事を待たずに自走を始める（phase=building、light=true）

- 入れるのは、受入条件が Issue に書いてあるか、依頼文だけで要件・範囲・完了が決まるときだけ（commands/autopilot.md の L）
- 自走の上限は PR 作成まで。`- 範囲:` が「PR まで」でなければ approve しない。マージ・デプロイ・QA の書き込み・ロールバックの記録
  （overnight.py ready・merged・qa・rolled-back）を受けない。範囲をマージ以降に広げる根拠は人が承認した spec なので、合意を省いた run には及ばない
- 止まる条件は、保護された path（下の既定と、起点の commit の `.spec-autopilot/protected-paths`）に触れたとき。init の時点の
  commit から、PR が持ち込む差（追っているファイルの HEAD・index・作業ツリー）の path で機械的に決め、照合は git の glob pathspec に任せる。
  追っていないファイル・git が無視するファイル・途中の commit で触れて戻したものは見ない（手元の書き換えは防がない。限界）。承認の前から当たっているなら approve しない。spec.md が承認の後に変わったとき（範囲が広がる）は、合意ありと同じく check が止める
- 印は block・done の後の approve でも外さない（その返事は spec の全体を見たものではない）。合意ありで進めるなら spec を作り直す

範囲: 軽量フローの承認・保護 path の判定・PR 作成までの上限（ready・merged・qa・rolled-back の拒否）だけを足す。合意ありの run の挙動は変えない
想定する脅威: 事故（agent が範囲を広げる・保護 path に触れる・マージに進む）。敵対的な agent が state.json を書き換えて印を消すことは防がない
やらないこと: 影響範囲の宣言と差分の突き合わせ、hook での編集・`gh pr merge` の拒否、利用する repo の設定の形の検査、追っていないファイル・git が無視するファイル・途中の commit の判定
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import autopilot as ap  # noqa: E402

# pattern の当て方は pathspecs() の docstring を見る
DEFAULT_PROTECTED = ("*.tf", "*.tf.json", "*.tfvars", "*.tfvars.json", "*.tfstate", "*.tfstate.*", ".terraform", "*.tofu", "*.tofu.json", "*.hcl", "terraform", "infra",
                     "*guardrails*", "CLAUDE.md", "CLAUDE.local.md", "AGENTS.md", "GEMINI.md", ".claude", ".mcp.json", ".github",
                     ".spec-autopilot")
CONFIG = Path(".spec-autopilot") / "protected-paths"
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
CEILING = "軽量フロー（人と spec を合意していない run）の自走の上限は PR 作成まで。マージ・デプロイ・QA の書き込みはしない（人の指示を待つ）"


def config_lines(text):
    return [x.strip() for x in text.splitlines() if x.strip() and not x.strip().startswith("#")]


def patterns(root, base):
    """既定と、起点（base）の commit の設定。設定を PR の中で変えると、`.spec-autopilot` 自体が既定の保護なので止まる。"""
    old = subprocess.run(["git", "show", f"{base}:{CONFIG.as_posix()}"], cwd=root, capture_output=True, text=True)
    return list(dict.fromkeys([*DEFAULT_PROTECTED, *config_lines(old.stdout if old.returncode == 0 else "")]))


def pathspecs(pats, fold=False):
    """pattern を git の glob pathspec にする。`/` を含まない行はどの深さにも、含む行は repo の root から当て、どちらも配下に当てる。"""
    magic = "glob,icase" if fold else "glob"
    out = []
    for p in pats:
        core = p.strip("/")
        if not core:
            continue
        if "/" not in core:
            core = "**/" + core
        out += [f":({magic}){core}", f":({magic}){core}/**"]
    return out


def hits(d, s):
    """起点から、PR が持ち込む差（HEAD と index と作業ツリーの、追っているファイル）で触れた保護 path。
    追っていないファイル・git が無視するファイル・途中の commit で触れて戻したものは数えない（限界）。照合は git がする。"""
    root = ap.repo_root(d)
    base = s.get("light_base") or EMPTY_TREE
    fold = subprocess.run(["git", "config", "--bool", "core.ignorecase"], cwd=root, capture_output=True, text=True).stdout.strip() == "true"
    own = Path(d).resolve().relative_to(Path(root).resolve()).as_posix()
    specs = pathspecs(patterns(root, base), fold) + [f":(exclude){own}"]
    # rename は両側の名前を出し（--no-renames）、非 ASCII の名前は引用しない（git_lines の -z と quotePath=false）
    return sorted(set(ap.git_lines(root, "diff", "--name-only", "--no-renames", base, "--", *specs)))


def errors(d, s):
    """軽量フローの run の check の ERROR。合意ありの run では []。"""
    if not s.get("light"):
        return []
    import overnight

    out = []
    scope = (overnight.scope_rows((d / "spec.md").read_text(encoding="utf-8")) or {}).get("範囲")
    if scope != overnight.PR:
        out.append(f"{CEILING}。`- 範囲:` は「{overnight.PR}」にする（今は「{scope}」）")
    try:
        found = hits(d, s)
    except (RuntimeError, OSError, ValueError) as e:  # 数えられないときは止める側に倒す
        return out + [f"保護された path を確かめられない（{e}）"]
    if found:
        out.append(f"保護された path に触れた: {', '.join(found)}。軽量フローでは進めない。"
                   "`autopilot.py block` で記録して人に戻る（spec の全体を人に示す。合意ありで進めるなら spec を作り直す）")
    return out


def refuse(s, what):
    """overnight.py の ready・merged・qa・rolled-back が、軽量フローの run で呼ばれたら止める。"""
    if s.get("light"):
        print(f"ERROR: {CEILING}。{what}は受けない")
        sys.exit(1)


def report(s):
    return [CEILING] if s.get("light") else []


def cmd_approve(a):
    d = Path(a.dir)
    import lineup
    import overnight

    s = ap.load_state(d)
    if s.get("phase") != "discovery":
        sys.exit(f"軽量フローの approve は壁打ち中（discovery）だけ受ける（phase={s.get('phase')}）")
    if not a.source.strip():
        sys.exit("--source（Issue の URL か依頼文の要約）は空にできない")
    errs, warnings = ap.lint(d, at_approve=True)
    scope = (overnight.scope_rows((d / "spec.md").read_text(encoding="utf-8")) or {}).get("範囲")
    if scope != overnight.PR:
        errs.append(f"{CEILING}。`- 範囲:` を「{overnight.PR}」にする（今は「{scope}」）")
    adr = ap.adr_error(d)
    if adr:
        errs.append(adr)
    if lineup.after_name(d):
        errs.append("依る spec のある spec は軽量フローで始めない（合意ありで --queue で承認する）")
    text = (d / "spec.md").read_text(encoding="utf-8")
    if ap.stated_size(ap.COMMENT_BLOCK.sub("", ap.section(text, "制約") or ""))[0] != "S":
        errs.append("軽量フローは `- 大きさ: S` の spec だけで始める（予算も人が見ないので、小さい修正に限る）")
    if errs:
        ap.report(errs, warnings, "")
        return 1
    root = ap.repo_root(d)
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
    ap.report([], warnings, f"approved（軽量フロー）: 予算 {budget} 分。{CEILING}")
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
