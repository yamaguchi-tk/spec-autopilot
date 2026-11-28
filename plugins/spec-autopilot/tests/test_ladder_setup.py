"""ladder.py の setup・show（手元の設定 models.md の読み書き）を、CLI の入口から確かめる。"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

LADDER = Path(__file__).resolve().parents[1] / "scripts" / "ladder.py"
IMPL = "実装: 受ける段 sonnet-high・opus-medium・opus-xhigh・fable"
REVIEW = "評価: 受ける段 opus-high・opus-xhigh・fable"


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    monkeypatch.setenv("SPEC_AUTOPILOT_HOME", str(h))
    return h


def ladder(*args):
    return subprocess.run([sys.executable, str(LADDER), *args], capture_output=True, text=True)


def both(r):
    return r.stdout + r.stderr


def test_setup_writes_the_given_roles_and_keeps_the_other_row(home):
    r = ladder("setup", "--impl", "opus-medium")
    assert r.returncode == 0, both(r)
    assert str(home / "models.md") in r.stdout and "- 実装: opus-medium" in r.stdout
    r = ladder("setup", "--review", "opus-xhigh")
    assert r.returncode == 0, both(r)
    assert (home / "models.md").read_text(encoding="utf-8") == "- 実装: opus-medium\n- 評価: opus-xhigh\n"
    assert "- 評価: opus-xhigh" in r.stdout
    assert ladder("setup", "--impl", "fable", "--review", "fable").returncode == 0
    assert (home / "models.md").read_text(encoding="utf-8") == "- 実装: fable\n- 評価: fable\n"


@pytest.mark.parametrize("args", [["--impl", "haiku"], ["--review", "sonnet-high"], ["--review", "opus-medium"],
                                  ["--impl", "opus-high"], ["--impl", ""], [], ["--impl", "fable", "--review", "haiku"]])
def test_setup_refuses_a_rung_it_does_not_take_and_leaves_models_md(home, args):
    assert ladder("setup", "--impl", "opus-medium").returncode == 0
    before = (home / "models.md").read_bytes()
    r = ladder("setup", *args)
    assert r.returncode != 0
    assert "sonnet-high・opus-medium・opus-xhigh・fable" in both(r) and "opus-high・opus-xhigh・fable" in both(r)
    assert (home / "models.md").read_bytes() == before


def test_setup_that_is_refused_does_not_create_models_md(home):
    assert ladder("setup", "--impl", "haiku").returncode != 0
    assert not (home / "models.md").exists()


def test_show_lists_rungs_default_and_the_local_setting_with_the_path(home):
    r = ladder("show")
    assert r.returncode == 0, both(r)
    assert f"{IMPL} / 既定 sonnet-high / 手元の設定 なし" in r.stdout
    assert f"{REVIEW} / 既定 opus-high / 手元の設定 なし" in r.stdout
    assert str(home / "models.md") in r.stdout
    ladder("setup", "--impl", "opus-medium")
    r = ladder("show")
    assert f"{IMPL} / 既定 sonnet-high / 手元の設定 opus-medium" in r.stdout
    assert f"{REVIEW} / 既定 opus-high / 手元の設定 なし" in r.stdout


def test_reset_removes_models_md_and_is_fine_when_there_is_none(home):
    ladder("setup", "--impl", "opus-medium", "--review", "opus-xhigh")
    r = ladder("setup", "--reset")
    assert r.returncode == 0 and "既定に戻" in r.stdout
    assert not (home / "models.md").exists()
    r = ladder("setup", "--reset")
    assert r.returncode == 0 and "既定に戻" in r.stdout


def test_reset_of_one_role_removes_only_its_row_and_the_file_when_no_row_is_left(home):
    ladder("setup", "--impl", "opus-medium", "--review", "opus-xhigh")
    r = ladder("setup", "--reset", "実装")
    assert r.returncode == 0 and "実装" in r.stdout and "既定に戻" in r.stdout
    assert (home / "models.md").read_text(encoding="utf-8") == "- 評価: opus-xhigh\n"
    assert ladder("setup", "--reset", "評価").returncode == 0
    assert not (home / "models.md").exists()
    assert ladder("setup", "--reset", "実装").returncode == 0  # 無くても 0


@pytest.mark.parametrize("args", [["--reset", "合意"], ["--reset", "実装", "--impl", "fable"], ["--reset", "--review", "fable"]])
def test_reset_refuses_an_unknown_role_or_a_mix_with_setting(home, args):
    ladder("setup", "--impl", "opus-medium")
    r = ladder("setup", *args)
    assert r.returncode != 0
    assert (home / "models.md").read_text(encoding="utf-8") == "- 実装: opus-medium\n"


@pytest.mark.parametrize("content", [b"- \xe5\xae\x9f\xe8\xa3\x85: haiku\n- \xe8\xa9\x95\xe4\xbe\xa1: fable\n", b"\xff\xfe\x00",
                                     "- 実装: fable\n- 実装: opus-medium\n".encode(), "ふつうの文\n- 評価: opus-xhigh\n".encode()])
def test_a_broken_models_md_is_kept_aside_each_time_and_the_good_rows_stay(home, content):
    home.mkdir()
    (home / "models.md").write_bytes(content)
    r = ladder("setup", "--impl", "opus-medium")
    assert r.returncode == 0, both(r)
    assert "退避" in r.stderr
    saved = sorted(home.glob("models.md.bad-*"))
    assert [p.read_bytes() for p in saved] == [content]
    assert "- 実装: opus-medium" in (home / "models.md").read_text(encoding="utf-8")
    (home / "models.md").write_bytes(content)  # もう 1 回壊れた
    assert ladder("setup", "--review", "fable").returncode == 0
    assert len(list(home.glob("models.md.bad-*"))) == 2


def test_concurrent_setups_of_the_two_roles_both_stay(home):
    env = dict(os.environ)
    procs = [subprocess.Popen([sys.executable, str(LADDER), "setup", flag, rung], env=env, stdout=subprocess.DEVNULL)
             for flag, rung in [("--impl", "opus-medium"), ("--review", "opus-xhigh")] * 8]
    assert [p.wait() for p in procs] == [0] * 16
    assert (home / "models.md").read_text(encoding="utf-8") == "- 実装: opus-medium\n- 評価: opus-xhigh\n"


ADVISOR = "相談: 受ける段 fable-medium・fable-high・opus-high"
CHECKER = "検証: 受ける段 opus-high・fable-high"
SPEC_CHECKER = "照合: 受ける段 sonnet-high・opus-high"


def test_setup_writes_the_advisor_and_checker_rows_with_the_others_and_prints_path_and_content(home):
    r = ladder("setup", "--advisor", "opus-high", "--checker", "opus-high")
    assert r.returncode == 0, both(r)
    assert str(home / "models.md") in r.stdout and "- 相談: opus-high" in r.stdout and "- 検証: opus-high" in r.stdout
    r = ladder("setup", "--impl", "opus-medium")
    assert r.returncode == 0, both(r)
    assert (home / "models.md").read_text(encoding="utf-8") == "- 実装: opus-medium\n- 相談: opus-high\n- 検証: opus-high\n"
    assert ladder("setup", "--advisor", "fable-high", "--review", "fable").returncode == 0
    assert (home / "models.md").read_text(encoding="utf-8") == "- 実装: opus-medium\n- 評価: fable\n- 相談: fable-high\n- 検証: opus-high\n"


@pytest.mark.parametrize("args", [["--advisor", "sonnet-high"], ["--advisor", "opus-medium"], ["--advisor", "fable"], ["--checker", "fable-medium"], ["--checker", "fable"],
                                  ["--spec-checker", "fable"], ["--spec-checker", "fable-high"], ["--spec-checker", "opus-medium"], ["--advisor", "fable-high", "--checker", "haiku"], ["--impl", "fable", "--advisor", "haiku"]])
def test_setup_refuses_an_advisor_or_checker_rung_it_does_not_take_and_lists_each_role(home, args):
    assert ladder("setup", "--advisor", "fable-high", "--impl", "opus-medium").returncode == 0
    before = (home / "models.md").read_bytes()
    r = ladder("setup", *args)
    assert r.returncode != 0
    for line in (IMPL, REVIEW, ADVISOR, CHECKER, SPEC_CHECKER):
        assert line in both(r), line
    assert (home / "models.md").read_bytes() == before


def test_reset_of_the_advisor_or_checker_removes_only_that_row_and_reset_removes_all(home):
    ladder("setup", "--impl", "opus-medium", "--advisor", "opus-high", "--checker", "opus-high")
    r = ladder("setup", "--reset", "相談")
    assert r.returncode == 0 and "相談" in r.stdout and "既定に戻" in r.stdout
    assert (home / "models.md").read_text(encoding="utf-8") == "- 実装: opus-medium\n- 検証: opus-high\n"
    assert ladder("setup", "--reset", "検証").returncode == 0
    assert (home / "models.md").read_text(encoding="utf-8") == "- 実装: opus-medium\n"
    ladder("setup", "--advisor", "fable-high", "--checker", "opus-high")
    assert ladder("setup", "--reset").returncode == 0
    assert not (home / "models.md").exists()


def test_show_lists_the_advisor_and_checker_rungs_default_and_setting_then_the_path_last(home):
    r = ladder("show")
    assert r.returncode == 0, both(r)
    lines = r.stdout.splitlines()
    assert lines == [f"{IMPL} / 既定 sonnet-high / 手元の設定 なし", f"{REVIEW} / 既定 opus-high / 手元の設定 なし",
                     f"{ADVISOR} / 既定 fable-medium / 手元の設定 なし", f"{CHECKER} / 既定 opus-high / 手元の設定 なし",
                     f"{SPEC_CHECKER} / 既定 sonnet-high / 手元の設定 なし",
                     f"設定のファイル: {home / 'models.md'}"]
    ladder("setup", "--advisor", "opus-high", "--checker", "opus-high")
    lines = ladder("show").stdout.splitlines()
    assert f"{ADVISOR} / 既定 fable-medium / 手元の設定 opus-high" in lines
    assert f"{CHECKER} / 既定 opus-high / 手元の設定 opus-high" in lines
    ladder("setup", "--spec-checker", "opus-high", "--checker", "fable-high")
    lines = ladder("show").stdout.splitlines()
    assert f"{SPEC_CHECKER} / 既定 sonnet-high / 手元の設定 opus-high" in lines
    assert f"{CHECKER} / 既定 opus-high / 手元の設定 fable-high" in lines


def test_a_models_md_with_an_unknown_advisor_rung_is_kept_aside_and_the_good_rows_stay(home):
    home.mkdir()
    content = "- 相談: haiku\n- 検証: opus-high\n- 実装: fable\n".encode()
    (home / "models.md").write_bytes(content)
    r = ladder("setup", "--review", "fable")
    assert r.returncode == 0, both(r)
    assert "退避" in r.stderr and [p.read_bytes() for p in home.glob("models.md.bad-*")] == [content]
    assert (home / "models.md").read_text(encoding="utf-8") == "- 実装: fable\n- 評価: fable\n- 検証: opus-high\n"


def test_concurrent_setups_of_the_four_roles_all_stay(home):
    env = dict(os.environ)
    flags = [("--impl", "opus-medium"), ("--review", "opus-xhigh"), ("--advisor", "opus-high"), ("--checker", "opus-high")]
    procs = [subprocess.Popen([sys.executable, str(LADDER), "setup", flag, rung], env=env, stdout=subprocess.DEVNULL) for flag, rung in flags * 6]
    assert [p.wait() for p in procs] == [0] * 24
    assert (home / "models.md").read_text(encoding="utf-8") == "- 実装: opus-medium\n- 評価: opus-xhigh\n- 相談: opus-high\n- 検証: opus-high\n"


# --- SessionStart の相談役の読み替え（R5）---

def start_context(tmp_path):
    from test_autopilot import context, session_start
    cwd = tmp_path / "cwd"
    cwd.mkdir(exist_ok=True)
    return context(session_start(cwd, "startup"))


def test_session_start_names_the_advisor_agent_of_a_non_default_stage(home, tmp_path):
    home.mkdir(exist_ok=True)
    for rung, name in [("fable-high", "fable-advisor-high"), ("opus-high", "fable-advisor-opus")]:
        (home / "models.md").write_text(f"- 相談: {rung}\n", encoding="utf-8")
        text = start_context(tmp_path)
        assert f"fable-advisor → spec-autopilot:{name}" in text and "読み替え" in text


def test_session_start_is_unchanged_when_the_rows_are_absent_or_the_default_stage(home, tmp_path):
    base = start_context(tmp_path)
    assert "読み替え" not in base and "ladder.py" not in base
    home.mkdir(exist_ok=True)
    (home / "models.md").write_text("- 実装: opus-medium\n- 相談: fable-medium\n- 検証: opus-high\n", encoding="utf-8")
    assert start_context(tmp_path) == base


@pytest.mark.parametrize("content", [b"\xff\xfe", "- 相談: sonnet-high\n".encode(), "- 相談: opus-high\n- 検証: fable\n".encode(), "- 照合: fable\n".encode()])
def test_session_start_adds_how_to_fix_an_unreadable_setting(home, tmp_path, content):
    base = start_context(tmp_path)
    home.mkdir(exist_ok=True)
    (home / "models.md").write_bytes(content)
    text = start_context(tmp_path)
    assert "setup --reset" in text and str(LADDER) in text and text.startswith(base.split("\n")[0])


# --- 照合役の段と検証の fable-high（2 本目: R1・R2・R4）---

def test_setup_writes_the_spec_checker_row_and_the_fable_checker_row_after_the_other_rows(home):
    r = ladder("setup", "--spec-checker", "opus-high", "--checker", "fable-high", "--impl", "opus-medium")
    assert r.returncode == 0, both(r)
    assert (home / "models.md").read_text(encoding="utf-8") == "- 実装: opus-medium\n- 検証: fable-high\n- 照合: opus-high\n"
    assert "- 照合: opus-high" in r.stdout and str(home / "models.md") in r.stdout
    assert ladder("setup", "--spec-checker", "sonnet-high").returncode == 0
    assert "- 照合: sonnet-high\n" in (home / "models.md").read_text(encoding="utf-8")


def test_reset_of_the_spec_checker_removes_only_its_row(home):
    ladder("setup", "--spec-checker", "opus-high", "--checker", "fable-high")
    r = ladder("setup", "--reset", "照合")
    assert r.returncode == 0 and "照合" in r.stdout and "既定に戻" in r.stdout
    assert (home / "models.md").read_text(encoding="utf-8") == "- 検証: fable-high\n"


def test_a_models_md_with_an_unknown_spec_checker_rung_is_kept_aside_and_the_good_rows_stay(home):
    home.mkdir()
    content = "- 照合: fable\n- 実装: fable\n".encode()
    (home / "models.md").write_bytes(content)
    r = ladder("setup", "--spec-checker", "opus-high")
    assert r.returncode == 0, both(r)
    assert [p.read_bytes() for p in home.glob("models.md.bad-*")] == [content]
    assert (home / "models.md").read_text(encoding="utf-8") == "- 実装: fable\n- 照合: opus-high\n"


def test_concurrent_setups_of_the_five_roles_all_stay(home):
    flags = [("--impl", "opus-medium"), ("--review", "opus-xhigh"), ("--advisor", "opus-high"), ("--checker", "fable-high"), ("--spec-checker", "opus-high")]
    procs = [subprocess.Popen([sys.executable, str(LADDER), "setup", flag, rung], stdout=subprocess.DEVNULL) for flag, rung in flags * 5]
    assert [p.wait() for p in procs] == [0] * 25
    assert (home / "models.md").read_text(encoding="utf-8") == "- 実装: opus-medium\n- 評価: opus-xhigh\n- 相談: opus-high\n- 検証: fable-high\n- 照合: opus-high\n"


def test_session_start_names_the_spec_checker_and_fable_checker_agents_of_a_non_default_stage(home, tmp_path):
    home.mkdir(exist_ok=True)
    (home / "models.md").write_text("- 検証: fable-high\n- 照合: opus-high\n", encoding="utf-8")
    text = start_context(tmp_path)
    assert "autopilot-spec-checker → spec-autopilot:autopilot-spec-checker-opus" in text
    assert "advice-checker → spec-autopilot:advice-checker-fable" in text and "読み替え" in text
    (home / "models.md").write_text("- 照合: sonnet-high\n- 検証: opus-high\n", encoding="utf-8")
    assert "読み替え" not in start_context(tmp_path)
