"""自走中に統合先（origin の既定ブランチ）が進んでも、承認と大きさの判定が狂わないことを、入口（`autopilot.py lint`・`approve`・`size`・`check`）から確かめる。

- 大きさは「init の時点から変わったファイル」のうち、統合先の中身と同じになったもの（統合先だけが変えたファイル）を数えない。統合先が引けないときは今どおり init の時点から数える（多く数える側）。
- 承認の印（spec の hash）は、先頭の `- ADR:` 行の番号の桁に依らない。本文は正規化しない代わりに、本文が自分の連番の ADR を名前・番号で書いていたら承認の前に止める。ADR が無くなったら check が止める。
"""
import re
import subprocess

import pytest

from test_autopilot import (EXISTING_SECTIONS, GOOD_SPEC, approve, existing_spec, init_spec, make_done, repo, run,  # noqa: F401
                            user_says, write_files)

ADR_LINE_TEST = re.compile(r"^- ADR:\s*(\S+)\s*$", re.M)
MAIN_ONLY = {f"lib/m{i}.js": f"m{i}\n" for i in range(6)}  # 統合先だけが変える 6 ファイル（自分の分と合わせると L になる数）


def git(repo, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args], cwd=repo,
                          capture_output=True, text=True, check=True).stdout.strip()


def commit(repo, files, msg="x"):
    write_files(repo, files)
    git(repo, "add", "--", *files)
    git(repo, "commit", "-qm", msg)


def with_origin(repo):
    """今の HEAD を origin の既定ブランチ（origin/main、origin/HEAD がそこを指す）にする。"""
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")


def advance_main(repo, files):
    """origin/main に commit を 1 つ積む（手元の branch は動かさない）。"""
    here = git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    git(repo, "switch", "-q", "--detach", "refs/remotes/origin/main")
    commit(repo, files, "main")
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    git(repo, "switch", "-q", here)


def spec_on_branch(repo, size="- 大きさ: S"):
    """origin/main から切った branch で init した既存の repo の spec。"""
    d = existing_spec(repo, size=size)
    with_origin(repo)
    git(repo, "switch", "-q", "-c", "feature")
    return d


def lint_out(repo, d):
    r = run(repo, "lint", str(d))
    return r.returncode, r.stdout + r.stderr


# --- 大きさ: 統合先の取り込み ---

def test_merging_main_does_not_count_files_only_main_changed(repo):
    d = spec_on_branch(repo)
    commit(repo, {"src/board.js": "function clearLines() { return 1 }\n"})
    advance_main(repo, MAIN_ONLY)
    git(repo, "merge", "-q", "--no-edit", "refs/remotes/origin/main")
    code, out = lint_out(repo, d)
    assert code == 0, out
    assert "数えた大きさ S（変える 1・" in out


def test_a_file_both_sides_changed_is_still_counted(repo):
    d = spec_on_branch(repo, size="- 大きさ: M")
    commit(repo, {"src/board.js": "function clearLines() { return 1 }\n", "lib/m0.js": "mine\n"})
    advance_main(repo, {**MAIN_ONLY, "lib/m0.js": "theirs\n"})
    git(repo, "merge", "-q", "--no-edit", "-X", "ours", "refs/remotes/origin/main")
    code, out = lint_out(repo, d)
    assert "数えた大きさ M（変える 2・" in out, out


def test_untracked_new_files_are_counted_after_merging_main(repo):
    d = spec_on_branch(repo, size="- 大きさ: M")
    commit(repo, {"src/board.js": "function clearLines() { return 1 }\n"})
    advance_main(repo, MAIN_ONLY)
    git(repo, "merge", "-q", "--no-edit", "refs/remotes/origin/main")
    write_files(repo, {"src/new.js": "new\n"})  # まだ add していない新しいファイル
    code, out = lint_out(repo, d)
    assert "数えた大きさ M（変える 2・" in out, out


def test_rebasing_onto_main_does_not_count_files_only_main_changed(repo):
    d = spec_on_branch(repo)
    commit(repo, {"src/board.js": "function clearLines() { return 1 }\n"})
    advance_main(repo, MAIN_ONLY)
    git(repo, "rebase", "-q", "refs/remotes/origin/main")
    code, out = lint_out(repo, d)
    assert code == 0, out
    assert "数えた大きさ S（変える 1・" in out


def test_without_origin_head_it_counts_from_init_as_before(repo):
    """統合先が引けないときは、init の時点からの差分を全部数える（多く数える側に倒す）。"""
    d = spec_on_branch(repo)
    commit(repo, {"src/board.js": "function clearLines() { return 1 }\n"})
    advance_main(repo, MAIN_ONLY)
    git(repo, "merge", "-q", "--no-edit", "refs/remotes/origin/main")
    git(repo, "symbolic-ref", "--delete", "refs/remotes/origin/HEAD")
    code, out = lint_out(repo, d)
    assert "数えた大きさ L（変える 7・" in out, out


def test_origin_head_pointing_at_a_missing_branch_counts_from_init(repo):
    d = spec_on_branch(repo)
    commit(repo, {"src/board.js": "function clearLines() { return 1 }\n"})
    advance_main(repo, MAIN_ONLY)
    git(repo, "merge", "-q", "--no-edit", "refs/remotes/origin/main")
    git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/gone")
    code, out = lint_out(repo, d)
    assert "数えた大きさ L（変える 7・" in out, out


def test_merging_main_alone_is_not_a_prototype_for_size_s(repo):
    """自分の試作が無いまま統合先を取り込んでも、S の承認は「試作の差分が無い」で止まる。"""
    d = spec_on_branch(repo)
    advance_main(repo, {"src/board.js": "function clearLines() { return 2 }\n"})
    git(repo, "merge", "-q", "--no-edit", "refs/remotes/origin/main")
    r = approve(repo, d)
    assert r.returncode == 1
    assert "試作の差分が無い" in r.stdout


def test_a_stacked_spec_counts_reverting_the_previous_specs_change(repo):
    """前の spec の branch から init した spec が、前の spec の変更を元に戻したファイルも数える。"""
    existing_spec(repo)
    with_origin(repo)
    git(repo, "switch", "-q", "-c", "first")
    commit(repo, {"src/board.js": "function clearLines() { return 1 }\n"})
    d = init_spec(repo, "second")
    (d / "spec.md").write_text(GOOD_SPEC + EXISTING_SECTIONS, encoding="utf-8")
    write_files(repo, {"src/board.js": "function clearLines() {}\n"})  # main と同じ中身に戻す
    code, out = lint_out(repo, d)
    assert "数えた大きさ S（変える 1・" in out, out


def test_size_with_a_tip_does_not_count_files_only_main_changed(repo):
    d = spec_on_branch(repo)
    commit(repo, {"src/board.js": "function clearLines() { return 1 }\n"})
    advance_main(repo, MAIN_ONLY)
    git(repo, "merge", "-q", "--no-edit", "refs/remotes/origin/main")
    r = run(repo, "size", str(d), "--tip", git(repo, "rev-parse", "HEAD"))
    assert r.returncode == 0, r.stdout
    assert "数えた大きさ S（変える 1・" in r.stdout


# --- 承認の印: 自分の ADR の改番 ---

def numbered(repo, d, number, slug="game"):
    """先頭の `- ADR:` 行を連番の ADR（docs/adr/<番号>-<slug>.md）にし、そのファイルだけを置く。"""
    adr_dir = repo / "docs" / "adr"
    for f in adr_dir.glob("*.md"):
        f.unlink()
    (adr_dir / f"{number}-{slug}.md").write_text(f"# ADR-{number}: canvas で描く\n\n- 直し方: 要らなくする\n", encoding="utf-8")
    spec = d / "spec.md"
    spec.write_text(re.sub(r"^- ADR: .*$", f"- ADR: docs/adr/{number}-{slug}.md", spec.read_text(encoding="utf-8"), count=1, flags=re.M),
                    encoding="utf-8")


def with_r1(d, extra):
    spec = d / "spec.md"
    spec.write_text(re.sub(r"^(- R1: .*)$", lambda m: m.group(1) + extra, spec.read_text(encoding="utf-8"), count=1, flags=re.M),
                    encoding="utf-8")


def approved_numbered(repo, number="0261", extra=""):
    d = init_spec(repo)
    numbered(repo, d, number)
    with_r1(d, extra)
    user_says(repo)
    r = run(repo, "approve", str(d), "--by", "OK")
    assert r.returncode == 0, r.stdout + r.stderr
    return d


def check_after(repo, d, change):
    spec = d / "spec.md"
    spec.write_text(change(spec.read_text(encoding="utf-8")), encoding="utf-8")
    make_done(repo, d)
    return run(repo, "check", str(d))


def test_renumbering_the_own_adr_keeps_the_approval(repo):
    """先頭の `- ADR:` 行の番号だけを改番しても、check は承認の後に変わったと言わない。"""
    d = approved_numbered(repo)
    adr = repo / "docs" / "adr"
    (adr / "0261-game.md").rename(adr / "0264-game.md")
    r = check_after(repo, d, lambda t: t.replace("- ADR: docs/adr/0261-game.md", "- ADR: docs/adr/0264-game.md"))
    assert r.returncode == 0, r.stdout


def test_changing_a_requirement_after_approval_still_fails_check(repo):
    d = approved_numbered(repo)
    r = check_after(repo, d, lambda t: t.replace("横 1 列", "横 2 列"))
    assert r.returncode == 1
    assert "承認の後に変わった" in r.stdout


@pytest.mark.parametrize("target", ["docs/adr/0261-other.md", "docs/other/0261-game.md", "README.md"])
def test_pointing_the_adr_line_elsewhere_fails_check(repo, target):
    """先頭の行で外すのは番号の桁だけで、ディレクトリと slug（番号の無い名前なら名前全体）は印に残る。"""
    d = approved_numbered(repo)
    (repo / target).parent.mkdir(parents=True, exist_ok=True)
    (repo / target).write_text("x\n", encoding="utf-8")
    r = check_after(repo, d, lambda t: t.replace("- ADR: docs/adr/0261-game.md", f"- ADR: {target}"))
    assert r.returncode == 1
    assert "承認の後に変わった" in r.stdout


def test_a_body_reference_is_not_normalized(repo):
    """本文は 1 字も正規化しない。承認の時点で本文にあった別の ADR の番号を、改番と一緒に書き換えたら止める。"""
    d = approved_numbered(repo, extra="（上流の ADR-0100 に合わせる）")
    adr = repo / "docs" / "adr"
    (adr / "0261-game.md").rename(adr / "0264-game.md")
    r = check_after(repo, d, lambda t: t.replace("0261-game.md", "0264-game.md").replace("ADR-0100", "ADR-0101"))
    assert r.returncode == 1
    assert "承認の後に変わった" in r.stdout


@pytest.mark.parametrize("word", ["ADR-0261", "ADR-261", "docs/adr/0261-game.md", "../../adr/0261-game.md", "0261-game.md",
                                  "migrations/0261-game.md", "上流のADR-0261", "team:ADR-0261"])
def test_approve_stops_a_body_that_names_the_own_numbered_adr(repo, word):
    """本文（作り方の節と先頭の行を除く）が自分の連番の ADR を名前・番号で書いていたら、承認の前に止める。改番で承認が外れるため。"""
    d = init_spec(repo)
    numbered(repo, d, "0261")
    with_r1(d, f"（{word}）")
    user_says(repo)
    r = run(repo, "approve", str(d), "--by", "OK")
    assert r.returncode == 1
    assert "自分の ADR" in r.stdout


def test_the_own_adr_may_be_named_in_how_to_build(repo):
    """作り方の節は承認の印の外なので、自分の ADR を名前で書いてよい。"""
    d = init_spec(repo)
    numbered(repo, d, "0261")
    spec = d / "spec.md"
    spec.write_text(spec.read_text(encoding="utf-8").replace("## 作り方\n", "## 作り方\n\nADR-0261（docs/adr/0261-game.md）のとおり。\n"),
                    encoding="utf-8")
    user_says(repo)
    r = run(repo, "approve", str(d), "--by", "OK")
    assert r.returncode == 0, r.stdout


def test_a_longer_number_is_not_the_own_adr(repo):
    """自分が ADR-026 のとき、本文の ADR-0263 は自分の ADR と読まない（承認は通り、書き換えは止める）。"""
    d = approved_numbered(repo, "026", extra="（ADR-0263 のとおり）")
    r = check_after(repo, d, lambda t: t.replace("ADR-0263", "ADR-0273"))
    assert r.returncode == 1
    assert "承認の後に変わった" in r.stdout


def test_a_date_named_adr_is_neither_normalized_nor_linted(repo):
    """日付の名前の ADR は番号の取り合いが無いので、本文で名前を書いてよく、名前を変えたら止める。"""
    d = init_spec(repo)
    adr = ADR_LINE_TEST.search((d / "spec.md").read_text(encoding="utf-8")).group(1)
    with_r1(d, f"（{adr}）")
    user_says(repo)
    assert run(repo, "approve", str(d), "--by", "OK").returncode == 0
    new = adr.replace("2026", "2027")
    (repo / adr).rename(repo / new)
    r = check_after(repo, d, lambda t: t.replace(adr, new))
    assert r.returncode == 1
    assert "承認の後に変わった" in r.stdout


def test_check_fails_when_the_adr_file_is_gone(repo):
    """check は ADR の行とファイルを確かめる（改番でファイルだけ動かした形を止める）。"""
    d = approved_numbered(repo)
    (repo / "docs" / "adr" / "0261-game.md").rename(repo / "docs" / "adr" / "0264-game.md")
    make_done(repo, d)
    r = run(repo, "check", str(d))
    assert r.returncode == 1
    assert "ADR" in r.stdout and "0261-game.md" in r.stdout


def test_check_fails_when_the_adr_line_is_removed(repo):
    d = approved_numbered(repo)
    r = check_after(repo, d, lambda t: t.replace("- ADR: docs/adr/0261-game.md\n", ""))
    assert r.returncode == 1
    assert "- ADR:" in r.stdout
