"""qa.md の pass の証拠の形を、入口（`autopilot.py check`）から通して確かめる。

評価役が書く形（pytest の node id、複数のテスト、テストに続けた cmd・注記）を受け、
受けた形でも、どれか 1 つのテストが無ければ落とす。
"""
import subprocess

import pytest

from test_autopilot import approved, make_done, repo, run  # noqa: F401（repo は fixture）

TEST_X = "class TestA:\n    def test_b(self):\n        pass\n\n\ndef test_a():\n    pass\n\n\ndef test_c():\n    pass\n"
TEST_Y = "def test_y():\n    pass\n"


def check_with(repo, evidence):
    d = approved(repo)
    make_done(repo, d)
    (repo / "tests").mkdir(exist_ok=True)
    (repo / "tests" / "test_x.py").write_text(TEST_X, encoding="utf-8")
    (repo / "tests" / "test_y.py").write_text(TEST_Y, encoding="utf-8")
    qa = d / "qa.md"
    text = qa.read_text(encoding="utf-8").replace("| R1 | pass | core.test.js::clears a full line |",
                                                  f"| R1 | pass | {evidence} |")
    qa.write_text(text, encoding="utf-8")
    return run(repo, "check", str(d))


@pytest.mark.parametrize("evidence", [
    "tests/test_x.py::TestA::test_b",
    "tests/test_x.py::test_a・::test_c",
    "tests/test_x.py::test_a・tests/test_y.py::test_y",
    "tests/test_x.py::test_a, ::test_c",
    "tests/test_x.py::test_a、::TestA::test_b",
    "tests/test_x.py::test_a と cmd: 評価役の検査で 3 通りとも通った",
    "tests/test_x.py::test_a・::test_c。cmd: 評価役の検査で 3 通りとも通った",
    "tests/test_x.py::test_a（全体の pytest で 10 passed）",
    "tests/test_x.py::test_a[case-1]",
    "tests/test_x.py::test_a（加えて cmd: 検査で（空・壊れた）入力を渡し、落ちなかった）",
    "tests/test_x.py::test_a（2 件の落ちは差分の外の tests/test_z.py::test_stuck）",
    "`tests/test_x.py::TestA::test_b`",
    "tests/test_x.py::test_a、 ・cmd: 評価役の検査で通った",
    "tests/test_x.py::test_a。加えて cmd: 評価役の検査で 3 通りとも通った",
    "tests/test_x.py::test_a（このほかに cmd: 評価役の検査で通った）",
    "cmd: 評価役の検査で通った（tests/test_x.py::TestNope::test_nope も通過）",
])
def test_check_accepts_the_forms_the_reviewer_writes(repo, evidence):
    r = check_with(repo, evidence)
    assert r.returncode == 0, r.stdout


def test_check_keeps_accepting_a_jest_name_with_colons_and_commas(repo):
    d = approved(repo)
    make_done(repo, d)
    (repo / "core.test.js").write_text("test('R8: 表示とスコア、Enter で再開', () => {})\n", encoding="utf-8")
    qa = d / "qa.md"
    qa.write_text(qa.read_text(encoding="utf-8").replace(
        "core.test.js::clears a full line", "core.test.js::R8: 表示とスコア、Enter で再開"), encoding="utf-8")
    r = run(repo, "check", str(d))
    assert r.returncode == 0, r.stdout


@pytest.mark.parametrize("evidence, missing", [
    ("tests/test_x.py::TestNope::test_b", "TestNope"),
    ("tests/test_x.py::TestA::test_nope", "test_nope"),
    ("tests/test_x.py::test_a・::test_nope", "test_nope"),
    ("tests/test_x.py::test_a・tests/test_nope.py::test_y", "tests/test_nope.py"),
    ("tests/test_x.py::test_a, tests/test_y.py::test_nope", "test_nope"),
    ("tests/test_x.py::test_nope と cmd: 評価役の検査で通った", "test_nope"),
    ("tests/test_x.py::test_nope（全体の pytest で 10 passed）", "test_nope"),
    ("tests/test_x.py::test_nope[case-1]", "test_nope"),
    ("tests/test_x.py::test_a（注）・tests/test_y.py::test_nope（注）", "R1 の証拠"),
    ("tests/test_x.py::test_a・tests/test_y.py::test_nope（加えて cmd: 検査で通った）", "test_nope"),
])
def test_check_fails_when_any_listed_test_is_missing(repo, evidence, missing):
    r = check_with(repo, evidence)
    assert r.returncode == 1
    assert "R1 の証拠" in r.stdout and missing in r.stdout


@pytest.mark.parametrize("evidence", [
    "::test_a",
    "tests/test_x.py::",
    "tests/test_x.py::test_a・::",
    "tests/test_x.py::test_a と cmd:",
    "（全体の pytest で 10 passed）",
    "tests/test_x.py",
    "tests/test_x.py::[case-1]",
    "tests/test_x.py::（注記）",
    "tests/test_x.py::TestA::",
    "tests/test_x.py::::test_a",
    "tests/test_x.py::test_a。tests/test_y.py::test_y",
    "x" * 300 + ".py::test_a",
])
def test_check_fails_on_evidence_it_cannot_read(repo, evidence):
    r = check_with(repo, evidence)
    assert r.returncode == 1
    assert "R1 の証拠" in r.stdout


@pytest.mark.parametrize("evidence", [
    "tests/test_x.py::test_a" + " " * 3900 + "x",
    "tests/test_x.py::test_a" + " " * 3900 + "・x",
    "tests/test_x.py::test_nope" + " と" * 1900,
], ids=["spaces", "spaces-then-separator", "repeated-to"])
def test_check_ends_quickly_on_a_long_run_of_spaces(repo, evidence, monkeypatch):
    """行の長さの上限の内側でも、Stop hook の timeout（30 秒）より十分早く、落ちる側で終わる。"""
    real = subprocess.run
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: real(*a, **{**k, "timeout": k.get("timeout", 10)}))
    r = check_with(repo, evidence)
    assert r.returncode == 1
    assert "R1 の証拠" in r.stdout


def quick(monkeypatch, sec=3):
    real = subprocess.run
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: real(*a, **{**k, "timeout": k.get("timeout", sec)}))


LONG = {
    # 長すぎる行は正規表現に通さない（TASK は [ の連なりで行の長さの 2 乗の時間がかかる）
    "qa-spaces": ("qa.md", "| R1 | pass | x" + " " * 50000 + "x |"),
    "tasks-brackets": ("tasks.md", "- [x] T9: " + "[" * 50000),
}


@pytest.mark.parametrize("name,line", LONG.values(), ids=LONG.keys())
def test_check_rejects_a_too_long_line_without_parsing_it(repo, monkeypatch, name, line):
    quick(monkeypatch)
    d = approved(repo)
    make_done(repo, d)
    with (d / name).open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    r = run(repo, "check", str(d))
    assert r.returncode == 1
    assert f"{name} の" in r.stdout and "長すぎる" in r.stdout


def test_check_accepts_a_line_at_the_limit(repo):
    d = approved(repo)
    make_done(repo, d)
    with (d / "tasks.md").open("a", encoding="utf-8") as f:
        f.write("  - メモ: " + "あ" * (4000 - len("  - メモ: ")) + "\n")
    r = run(repo, "check", str(d))
    assert r.returncode == 0, r.stdout


@pytest.mark.parametrize("name", ["qa.md", "tasks.md"])
def test_check_rejects_a_too_large_file_without_parsing_it(repo, monkeypatch, name):
    quick(monkeypatch)
    d = approved(repo)
    make_done(repo, d)
    with (d / name).open("a", encoding="utf-8") as f:
        f.write(("<!-- " + "x" * 3000 + " -->\n") * 80)
    r = run(repo, "check", str(d))
    assert r.returncode == 1
    assert f"{name} が大きすぎる" in r.stdout


def test_check_rejects_a_line_just_over_the_limit(repo):
    d = approved(repo)
    make_done(repo, d)
    with (d / "tasks.md").open("a", encoding="utf-8") as f:
        f.write("  - メモ: " + "あ" * (4001 - len("  - メモ: ")) + "\n")
    r = run(repo, "check", str(d))
    assert r.returncode == 1 and "tasks.md の 4 行目が長すぎる" in r.stdout


WORST = {
    # 閉じの | が無く空白が続く qa.md の行（行の長さの 3 乗の時間がかかる形があった）
    "qa-open-row": ("qa.md", ["| R1 | pass |" + " " * 3980 + "x"] * 49),
    # [ が続く tasks.md の行（2 乗）
    "tasks-brackets": ("tasks.md", ["- [x] T9: " + "[" * 3980] * 49),
}


@pytest.mark.parametrize("name,lines", WORST.values(), ids=WORST.keys())
def test_check_ends_quickly_on_the_worst_lines_within_the_limits(repo, monkeypatch, name, lines):
    d = approved(repo)
    make_done(repo, d)
    quick(monkeypatch, 5)
    with (d / name).open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    r = run(repo, "check", str(d))
    assert r.returncode == 1


def big_evidence(repo, size, names):
    (repo / "tests").mkdir(exist_ok=True)
    body = "x" * (size - sum(len(n) + 1 for n in names)) + "".join(n + "\n" for n in names)
    (repo / "tests" / "test_big.py").write_text(body, encoding="utf-8")


def test_check_rejects_an_evidence_file_over_the_limit(repo):
    big_evidence(repo, 2_000_001, ["test_a"])
    r = check_with(repo, "tests/test_big.py::test_a")
    assert r.returncode == 1 and "tests/test_big.py が大きすぎる" in r.stdout


def test_check_accepts_an_evidence_file_at_the_limit(repo):
    big_evidence(repo, 2_000_000, ["test_a"])
    r = check_with(repo, "tests/test_big.py::test_a")
    assert r.returncode == 0, r.stdout


def test_check_ends_quickly_on_many_names_in_a_large_evidence_file(repo, monkeypatch):
    """1 行に並べた別々の名前を、上限いっぱいのファイルの末尾から探す形でも、探す量の上限で早く終わる。"""
    names = [f"n{i}" for i in range(700)]
    big_evidence(repo, 2_000_000, names)
    quick(monkeypatch, 10)
    r = check_with(repo, "tests/test_big.py::" + "・::".join(names))
    assert r.returncode in (0, 1)


JEST = ("describe('得点・レベル', () => { test('1 行消すと、100 点', () => {}) })\n"
        "describe('得点、レベル', () => { test('A', () => {}) })\n"
        "describe('a,b', () => { test('C', () => {}) })\n")


def check_with_jest(repo, evidence):
    d = approved(repo)
    make_done(repo, d)
    (repo / "tests").mkdir(exist_ok=True)
    (repo / "tests" / "test_y.py").write_text(TEST_Y, encoding="utf-8")
    (repo / "core.test.js").write_text(JEST, encoding="utf-8")
    qa = d / "qa.md"
    qa.write_text(qa.read_text(encoding="utf-8").replace(
        "core.test.js::clears a full line", evidence), encoding="utf-8")
    return run(repo, "check", str(d))


@pytest.mark.parametrize("evidence", [
    "core.test.js::得点・レベル::1 行消すと、100 点",
    "core.test.js::得点、レベル::A",
    "core.test.js::a,b::C",
    "core.test.js::得点・レベル::1 行消すと、100 点・tests/test_y.py::test_y",
    "core.test.js::得点・レベル::1 行消すと、100 点・::得点、レベル::A",
])
def test_check_accepts_a_test_name_with_a_separator_before_a_double_colon(repo, evidence):
    r = check_with_jest(repo, evidence)
    assert r.returncode == 0, r.stdout


@pytest.mark.parametrize("evidence", [
    "core.test.js::得点・レベル::A・::nope",
    "core.test.js::得点・レベル::1 行消すと、100 点・tests/test_y.py::test_nope",
    "core.test.js::得点・レベル::1 行消すと、100 点・nofile.py::test_y",
    "core.test.js::得点・nofile.py::test_y",
])
def test_check_still_fails_when_a_listed_test_after_a_separator_is_missing(repo, evidence):
    r = check_with_jest(repo, evidence)
    assert r.returncode == 1, r.stdout
