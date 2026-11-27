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


@pytest.mark.parametrize("args", [["--reset", "照合"], ["--reset", "実装", "--impl", "fable"], ["--reset", "--review", "fable"]])
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
