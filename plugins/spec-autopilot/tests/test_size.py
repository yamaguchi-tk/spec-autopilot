"""既存の repo の大きさの数え方を、入口（`autopilot.py lint`・`approve`・`size` と UserPromptSubmit hook）から通して確かめる。

大きさは、申告（「## 制約」の `- 大きさ:`）と数えた大きさの大きい側だけで決める。人の発言で小さくする道は無い。
"""
import json

import pytest

from test_autopilot import existing_spec, repo, run, state, user_says, write_files  # noqa: F401（repo は fixture）


def medium_counted_spec(repo):
    """申告 S・数えた大きさ M（変えるファイルが 2 つ）の spec。"""
    d = existing_spec(repo)
    write_files(repo, {"src/board.js": "x\n", "src/game.js": "y\n"})
    return d


@pytest.mark.parametrize("prompt", ["大きさ S", "大きさ S で OK", "大きさは S で進めて"])
def test_a_smaller_size_does_not_pass_even_if_the_user_says_it(repo, prompt):
    """申告が数えた大きさより小さければ、人が何と言っても lint・approve とも ERROR。直し方は申告を数えた大きさに上げること。"""
    d = medium_counted_spec(repo)
    user_says(repo, prompt=prompt)
    r = run(repo, "lint", str(d))
    assert r.returncode == 1
    assert "大きさ S は数えた大きさ M" in r.stdout and "`- 大きさ: M`" in r.stdout
    r = run(repo, "approve", str(d), "--by", prompt)
    assert r.returncode == 1
    assert state(d)["phase"] == "discovery"


def test_raising_the_size_to_the_counted_one_passes_without_a_size_reply(repo):
    d = medium_counted_spec(repo)
    spec = d / "spec.md"
    spec.write_text(spec.read_text(encoding="utf-8").replace("- 大きさ: S", "- 大きさ: M"), encoding="utf-8")
    user_says(repo, prompt="OK")
    r = run(repo, "approve", str(d), "--by", "OK")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "size_by_user" not in state(d)


def test_the_hook_no_longer_records_a_size(repo):
    existing_spec(repo)
    user_says(repo, prompt="大きさ S")
    rec = json.loads((repo / ".git" / "spec-autopilot-last-user-prompt").read_text(encoding="utf-8"))
    assert "size" not in rec and "size_at" not in rec


def test_lint_does_not_count_files_that_only_share_the_changed_files_name(repo):
    """変えたファイルの名前（拡張子を除く。main・app・variables など）を含むだけのファイルは、呼び出し元に数えない。"""
    d = existing_spec(repo, files={f"src/use{i}.js": "import './board.js'\n" for i in range(5)})
    write_files(repo, {"src/board.js": "function clearLines() { return 1 }\n"})
    r = run(repo, "lint", str(d))
    assert r.returncode == 0, r.stdout
    assert "数えた大きさ S（変える 1・呼び出し元 1・別の実装 0）" in r.stdout  # 影響範囲に書いた src/game.js だけ


def test_lint_does_not_count_declared_test_paths_as_changed(repo):
    impact = "".join(f"- 新規: tests/t{i}.test.js\n" for i in range(6))
    d = existing_spec(repo, size="- 大きさ: M", impact=impact)
    r = run(repo, "lint", str(d))
    assert r.returncode == 0, r.stdout
    assert "数えた大きさ S（変える 1・" in r.stdout  # src/board.js だけ


def test_lint_does_not_count_declared_docs_but_counts_other_markdown(repo):
    """書いたパスのうち docs/ の下は数えない。docs/ の外の .md（skill・agent の本体など）は数える（.md が本体の repo で 0 にしない）。"""
    impact = "".join(f"- 新規: docs/p{i}.md\n" for i in range(6)) + "".join(f"- 新規: skills/s{i}/SKILL.md\n" for i in range(5))
    d = existing_spec(repo, size="- 大きさ: M", impact=impact)
    r = run(repo, "lint", str(d))
    assert "数えた大きさ L（変える 6・" in r.stdout, r.stdout  # src/board.js と skills の 5 本


def test_lint_requires_the_caller_line_or_none(repo):
    """変えたファイルの名前では呼び出し元を数えないので、`- 呼び出し元:` の書き漏れを、`- 同じ入力:` と同じく行の有無で止める。"""
    d = existing_spec(repo, size="- 大きさ: M")
    spec = d / "spec.md"
    spec.write_text(spec.read_text(encoding="utf-8").replace("- 呼び出し元: `src/game.js:40`\n", ""), encoding="utf-8")
    r = run(repo, "lint", str(d))
    assert r.returncode == 1
    assert "`- 呼び出し元:" in r.stdout and "なし" in r.stdout
    spec.write_text(spec.read_text(encoding="utf-8").replace("- 同じ入力: なし", "- 呼び出し元: なし\n- 同じ入力: なし"), encoding="utf-8")
    r = run(repo, "lint", str(d))
    assert r.returncode == 0, r.stdout


def test_lint_rejects_none_together_with_caller_paths(repo):
    d = existing_spec(repo, size="- 大きさ: M", impact="- 呼び出し元: なし\n")
    r = run(repo, "lint", str(d))
    assert r.returncode == 1
    assert "`- 呼び出し元:` に `なし` とパスを両方" in r.stdout


def test_size_falls_to_large_when_the_caller_line_is_missing(repo):
    """評価役の観点 8 に使う大きさは、影響範囲が読めないとき（呼び出し元の行が無い spec を含む）大きい側に倒す。"""
    d = existing_spec(repo, size="- 大きさ: S")
    spec = d / "spec.md"
    spec.write_text(spec.read_text(encoding="utf-8").replace("- 呼び出し元: `src/game.js:40`\n", ""), encoding="utf-8")
    r = run(repo, "size", str(d))
    assert "観点 8 の大きさ: L" in r.stdout


def test_lint_counts_markdown_in_the_diff_outside_docs(repo):
    """影響範囲に書いていなくても、差分の docs/ の外の .md（skill の本体など）は数える。docs/ の下は数えない。"""
    d = existing_spec(repo, size="- 大きさ: M")
    write_files(repo, {"src/board.js": "x\n", **{f"skills/s{i}/SKILL.md": "s\n" for i in range(5)},
                       **{f"docs/p{i}.md": "p\n" for i in range(6)}})
    r = run(repo, "lint", str(d))
    assert "数えた大きさ L（変える 6・" in r.stdout, r.stdout  # src/board.js と skills の 5 本


def test_lint_counts_readme_changelog_and_files_named_like_them(repo):
    """数えないのは docs/ の下だけ。README・CHANGELOG や、その名前で始まるコードのファイルは数える（小さい側に倒さない）。"""
    d = existing_spec(repo, size="- 大きさ: M")
    write_files(repo, {"src/board.js": "x\n", "tools/CHANGELOG_gen.py": "g\n", "scripts/README_builder.js": "b\n",
                       "README.md": "r\n", "CHANGELOG.md": "c\n", "docs/README.md": "d\n"})
    r = run(repo, "lint", str(d))
    assert "（変える 5・" in r.stdout, r.stdout



def six_changed_files(repo):
    write_files(repo, {f"src/m{i}.js": "x\n" for i in range(6)})


@pytest.mark.parametrize("stated", ["S", "M", "L"])
def test_a_large_count_does_not_pass_the_first_agreement_and_says_to_split(repo, stated):
    """初回の合意（discovery）では、数えた大きさが L なら申告によらず lint・approve とも止め、申告を L に上げる案内ではなく spec を分ける案内を出す。"""
    d = existing_spec(repo, size=f"- 大きさ: {stated}")
    six_changed_files(repo)
    user_says(repo, prompt="OK")
    for r in (run(repo, "lint", str(d)), run(repo, "approve", str(d), "--by", "OK")):
        assert r.returncode == 1, r.stdout
        assert "spec を分け" in r.stdout and "`- 大きさ: L` に直し" not in r.stdout, r.stdout
    assert state(d)["phase"] == "discovery"


def test_a_declared_large_size_does_not_pass_even_when_the_count_is_smaller(repo):
    d = existing_spec(repo, size="- 大きさ: L")
    write_files(repo, {"src/board.js": "x\n", "src/game.js": "y\n"})
    r = run(repo, "lint", str(d))
    assert r.returncode == 1, r.stdout
    assert "spec を分け" in r.stdout


def new_repo_spec(repo, size_lines):
    from test_autopilot import GOOD_SPEC, init_spec
    d = init_spec(repo)
    (d / "spec.md").write_text(GOOD_SPEC.replace("- 大きさ: S", size_lines), encoding="utf-8")
    return d


def test_a_new_repo_spec_declared_large_does_not_pass_lint(repo):
    r = run(repo, "lint", str(new_repo_spec(repo, "- 大きさ: L")))
    assert r.returncode == 1, r.stdout
    assert "spec を分け" in r.stdout


@pytest.mark.parametrize("size_lines", ["- 大きさ: L（分けない）", "- 大きさ: l", "- 大きさ: Ｌ", "- 大きさ: **L**", "- 大きさ: M\n- 大きさ: L"])
def test_an_unreadable_or_repeated_size_line_does_not_pass_in_a_new_repo(repo, size_lines):
    """読めない形の大きさの行と 2 行の大きさの行は、L の判定をすり抜けないよう、新しい repo でも ERROR にする。"""
    r = run(repo, "lint", str(new_repo_spec(repo, size_lines)))
    assert r.returncode == 1, r.stdout
    assert "大きさの行" in r.stdout, r.stdout


def test_a_repeated_size_line_does_not_pass_in_an_existing_repo(repo):
    d = existing_spec(repo, size="- 大きさ: M\n- 大きさ: L")
    write_files(repo, {"src/board.js": "x\n", "src/game.js": "y\n"})
    r = run(repo, "lint", str(d))
    assert r.returncode == 1, r.stdout
    assert "大きさの行" in r.stdout, r.stdout


def test_a_spec_that_grew_large_can_be_reapproved_after_done_and_done_says_to_split_the_pr(repo):
    """自走の途中で L に育った spec は、done が PR を塊ごとに分けるよう知らせる。done の後の再承認は L を見ない。"""
    from test_autopilot import make_done
    d = existing_spec(repo, size="- 大きさ: M")
    write_files(repo, {"src/board.js": "x\n", "src/game.js": "y\n"})
    user_says(repo, prompt="OK")
    assert run(repo, "approve", str(d), "--by", "OK").returncode == 0
    six_changed_files(repo)
    make_done(repo, d)
    r = run(repo, "done", str(d))
    assert r.returncode == 0, r.stdout + r.stderr
    assert "数えた大きさ L" in r.stdout and "stacked PR に分ける" in r.stdout, r.stdout
    spec = d / "spec.md"
    spec.write_text(spec.read_text(encoding="utf-8").replace("- 大きさ: M", "- 大きさ: L"), encoding="utf-8")
    user_says(repo, prompt="大きさを L にしてレビューの 1 件を直して")
    r = run(repo, "approve", str(d), "--by", "レビューの 1 件を直す")
    assert r.returncode == 0, r.stdout + r.stderr
    assert state(d)["phase"] == "building"



def test_a_reapproval_does_not_look_at_the_size_and_done_says_to_split_the_pr(repo):
    """合意し直しでは L を理由には止めない（申告が数えた大きさより小さければ、今までどおり上げさせる）。申告か数えた大きさが L の経路では、done の NOTE が PR を分けるよう知らせる。"""
    from test_autopilot import make_done
    d = existing_spec(repo, size="- 大きさ: M")
    write_files(repo, {"src/board.js": "x\n", "src/game.js": "y\n"})
    user_says(repo, prompt="OK")
    assert run(repo, "approve", str(d), "--by", "OK").returncode == 0
    make_done(repo, d)
    r = run(repo, "done", str(d))
    assert r.returncode == 0 and "stacked PR" not in r.stdout, r.stdout
    spec = d / "spec.md"
    spec.write_text(spec.read_text(encoding="utf-8").replace("- 大きさ: M", "- 大きさ: L"), encoding="utf-8")  # 申告だけが L（数えた大きさは M）
    user_says(repo, prompt="機能を足して")
    r = run(repo, "approve", str(d), "--by", "機能を足す")
    assert r.returncode == 0, r.stdout + r.stderr
    make_done(repo, d)
    r = run(repo, "done", str(d))
    assert r.returncode == 0 and "stacked PR に分ける" in r.stdout and "申告 L" in r.stdout, r.stdout


def test_done_treats_an_unreadable_size_line_as_large(repo):
    """done は、大きさの行が読めないときは大きい側に倒して PR を分けるよう知らせる（cmd_size と同じ向き）。"""
    from test_autopilot import approved, make_done
    d = approved(repo)
    make_done(repo, d)
    spec = d / "spec.md"
    spec.write_text(spec.read_text(encoding="utf-8").replace("- 大きさ: S", "- 大きさ: S（人の指定）"), encoding="utf-8")
    import sys
    from test_autopilot import PLUGIN
    sys.path.insert(0, str(PLUGIN / "scripts"))
    import autopilot  # この版より前に、大きさの行の形を検査せずに承認した spec を作る
    s = state(d)
    s["spec_sha256"] = autopilot.sha(d)
    (d / "state.json").write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")
    r = run(repo, "done", str(d))
    assert "stacked PR に分ける" in r.stdout and "大きさの行" in r.stdout, r.stdout


def test_a_new_repo_reapproval_passes_a_declared_large_size_and_done_says_to_split_the_pr(repo):
    from test_autopilot import approved, make_done
    d = approved(repo)
    make_done(repo, d)
    r = run(repo, "done", str(d))
    assert r.returncode == 0 and "stacked PR" not in r.stdout, r.stdout
    spec = d / "spec.md"
    spec.write_text(spec.read_text(encoding="utf-8").replace("- 大きさ: S", "- 大きさ: L"), encoding="utf-8")
    user_says(repo, prompt="大きさを L にして機能を足して")
    r = run(repo, "approve", str(d), "--by", "機能を足す")
    assert r.returncode == 0, r.stdout + r.stderr
    make_done(repo, d)
    r = run(repo, "done", str(d))
    assert r.returncode == 0 and "stacked PR に分ける" in r.stdout, r.stdout


def approved_medium_spec(repo):
    """申告 M・数えた大きさ M で承認した、既存の repo の spec。"""
    d = existing_spec(repo, size="- 大きさ: M")
    write_files(repo, {"src/board.js": "x\n", "src/game.js": "y\n"})
    user_says(repo, prompt="OK")
    assert run(repo, "approve", str(d), "--by", "OK").returncode == 0
    return d


def test_check_stage_pr_says_to_split_the_pr_when_the_counted_size_grew_to_large(repo):
    """範囲がマージ以上の spec は done が PR の後になるので、PR を作る前の check --stage pr が L の NOTE を出す。終了コードは変えない。"""
    from test_autopilot import make_done
    d = approved_medium_spec(repo)
    six_changed_files(repo)
    make_done(repo, d)
    r = run(repo, "check", str(d), "--stage", "pr")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "NOTE: 大きさが L になった" in r.stdout and "数えた大きさ L" in r.stdout and "申告 M" in r.stdout, r.stdout


def test_check_stage_pr_says_to_split_the_pr_when_the_declared_size_is_large(repo):
    from test_autopilot import make_done
    d = approved_medium_spec(repo)
    make_done(repo, d)
    assert run(repo, "done", str(d)).returncode == 0
    spec = d / "spec.md"
    spec.write_text(spec.read_text(encoding="utf-8").replace("- 大きさ: M", "- 大きさ: L"), encoding="utf-8")
    user_says(repo, prompt="機能を足して")
    assert run(repo, "approve", str(d), "--by", "機能を足す").returncode == 0
    make_done(repo, d)
    r = run(repo, "check", str(d), "--stage", "pr")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "NOTE: 大きさが L になった" in r.stdout and "申告 L" in r.stdout, r.stdout


def test_check_stage_pr_does_not_say_it_when_neither_size_is_large(repo):
    from test_autopilot import make_done
    d = approved_medium_spec(repo)
    make_done(repo, d)
    r = run(repo, "check", str(d), "--stage", "pr")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "大きさが L になった" not in r.stdout, r.stdout


def test_check_without_stage_does_not_say_it_even_when_large(repo):
    from test_autopilot import make_done
    d = approved_medium_spec(repo)
    six_changed_files(repo)
    make_done(repo, d)
    r = run(repo, "check", str(d))
    assert "大きさが L になった" not in r.stdout, r.stdout


def test_check_stage_pr_prints_only_the_base_error_when_the_spec_is_not_approved_and_does_not_traceback(repo):
    """承認前（check が errors を返す）の spec では、大きさの NOTE を出さず、base と同じ ERROR だけで終わる。"""
    d = existing_spec(repo, size="- 大きさ: L")
    r = run(repo, "check", str(d), "--stage", "pr")
    assert r.returncode == 1 and "ERROR: 承認されていない（phase=discovery）" in r.stdout, r.stdout + r.stderr
    assert "Traceback" not in r.stderr and "大きさが L になった" not in r.stdout, r.stdout + r.stderr


def test_check_stage_pr_prints_the_base_error_when_spec_md_is_missing_and_does_not_traceback(repo):
    """spec.md が無い spec でも、check --stage pr は Traceback にせず base と同じ ERROR で終わる。"""
    d = existing_spec(repo)
    (d / "spec.md").unlink()
    r = run(repo, "check", str(d), "--stage", "pr")
    assert r.returncode == 1 and "ERROR: 承認されていない（phase=discovery）" in r.stdout, r.stdout + r.stderr
    assert "Traceback" not in r.stderr, r.stderr


def test_check_prints_a_spec_md_missing_error_for_an_approved_spec_without_traceback(repo):
    """承認した spec（building と done）から spec.md を消しても、check は Traceback にせず `spec.md が無い` の ERROR 1 行で終わる。"""
    from test_autopilot import make_done
    d = approved_medium_spec(repo)
    for phase in ("building", "done"):
        if phase == "done":
            make_done(repo, d)
        (d / "spec.md").rename(d / "spec.md.bak")
        for args in (("check", str(d)), ("check", str(d), "--stage", "pr")):
            r = run(repo, *args)
            assert r.returncode == 1 and "ERROR: spec.md が無い" in r.stdout, (phase, args, r.stdout + r.stderr)
            assert "Traceback" not in r.stderr, (phase, args, r.stderr)
        (d / "spec.md.bak").rename(d / "spec.md")
