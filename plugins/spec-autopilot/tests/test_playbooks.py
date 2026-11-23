"""spec の「## 制約」の `- playbook:` を、入口（CLI lint）から確かめる。名前は references/playbooks/ のファイル一覧で閉じる。"""
import pytest

from test_autopilot import GOOD_SPEC, PLUGIN, repo  # noqa: F401（repo は fixture）
from test_stages import lint

LINE = "- playbook: feature\n"


def with_playbook(*lines):
    return GOOD_SPEC.replace(LINE, "".join(f"{x}\n" for x in lines))


def test_the_playbooks_are_the_files_in_the_folder():
    assert sorted(p.stem for p in (PLUGIN / "references" / "playbooks").glob("*.md")) == [
        "bug-fix", "external-service", "feature", "iac"]


def test_lint_requires_the_playbook_line(repo):
    r = lint(repo, with_playbook())
    assert r.returncode == 1 and "playbook" in r.stdout


@pytest.mark.parametrize("value", ["feature", "feature、external-service", "bug-fix、iac", "なし（依存の更新だけ）"])
def test_lint_accepts_known_names_or_none_with_a_reason(repo, value):
    r = lint(repo, with_playbook(f"- playbook: {value}"))
    assert r.returncode == 0, r.stdout


@pytest.mark.parametrize("value, word", [
    ("refactor", "refactor"),  # ファイルの無い名前
    ("small-prototype", "small-prototype"),  # 大きさ S で読むもので、playbook の名前ではない
    ("../after-pr", "../after-pr"),  # パスでファイルの有無の確かめを抜けない
    ("Feature", "Feature"),
    ("feature、feature", "feature"),  # 重複
    ("feature、なし（x）", "なし"),  # 名前となしを混ぜない
    ("なし", "なし"),  # 理由が要る
    ("なし（）", "なし"),
    ("", "playbook"),
    ("feature, iac", "feature, iac"),  # 区切りは「、」だけ
])
def test_lint_rejects_unknown_or_malformed_values(repo, value, word):
    r = lint(repo, with_playbook(f"- playbook: {value}"))
    assert r.returncode == 1 and word in r.stdout, r.stdout


def test_lint_rejects_two_playbook_lines(repo):
    r = lint(repo, with_playbook("- playbook: feature", "- playbook: iac"))
    assert r.returncode == 1 and "playbook" in r.stdout


def test_a_playbook_line_in_a_comment_does_not_count(repo):
    r = lint(repo, with_playbook("<!-- - playbook: feature -->"))
    assert r.returncode == 1 and "playbook" in r.stdout
