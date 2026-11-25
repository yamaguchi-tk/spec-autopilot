"""作り直しの ADR の「直し方」の行を、rework の入口から確かめる（R1・R2）。"""
import shlex
import subprocess
import sys
from pathlib import Path

from test_autopilot import approved, make_done, repo, run, state, three_fails  # noqa: F401（repo は fixture）

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import rootcause  # noqa: E402

ORDER = ["要らなくする", "入力の約束を変える", "設計を変える", "局所の継ぎ足し"]


def adr(repo, name, *lines):
    (repo / "docs" / "adr" / name).write_text("# ADR\n\n" + "\n".join(lines) + "\n", encoding="utf-8")
    return f"docs/adr/{name}"


def rework(repo, d, path):
    return run(repo, "rework", str(d), "--req", "R1", "--adr", path)


def ready(repo):
    d = approved(repo)
    make_done(repo, d)
    three_fails(repo, d)
    return d


def reworks(repo, d):
    return state(d).get("reworks", {}).get("R1", [])


def test_fix_order_is_the_four_stages_in_order():
    assert list(rootcause.FIX_ORDER) == ORDER


def test_rework_records_adr_with_chosen_stage_and_every_upper_stage_rejected(repo):
    d = ready(repo)
    p = adr(repo, "ok.md", "- 直し方: 設計を変える", "- 退けた: 要らなくする（使う人がいる）",
            "- 退けた: 入力の約束を変える（呼び出し元が多い）")
    assert rework(repo, d, p).returncode == 0
    assert reworks(repo, d) == [p]


def test_top_stage_needs_no_rejected_lines(repo):
    d = ready(repo)
    assert rework(repo, d, adr(repo, "top.md", "- 直し方: 要らなくする")).returncode == 0


def test_rework_refuses_missing_unknown_or_duplicate_fix_line(repo):
    d = ready(repo)
    for i, lines in enumerate([[], ["- 直し方: 根本"], ["- 直し方: 要らなくする", "- 直し方: 設計を変える"]]):
        r = rework(repo, d, adr(repo, f"bad{i}.md", *lines))
        assert r.returncode != 0 and "- 直し方:" in r.stderr + r.stdout
    assert reworks(repo, d) == []


def test_rework_names_the_missing_rejected_stage(repo):
    d = ready(repo)
    r = rework(repo, d, adr(repo, "short.md", "- 直し方: 局所の継ぎ足し", "- 退けた: 要らなくする（x）"))
    assert r.returncode != 0
    out = r.stdout + r.stderr
    assert "入力の約束を変える" in out and "設計を変える" in out
    assert reworks(repo, d) == []


def test_requirement_sentence_rejection_is_refused_with_a_pasteable_park_command(repo):
    d = ready(repo)
    word = 'a "b" $(echo x) c'
    p = adr(repo, "req.md", "- 直し方: 設計を変える", f"- 要件の文で退けた: 要らなくする（R1 の「{word}」）",
            "- 退けた: 入力の約束を変える（y）")
    r = rework(repo, d, p)
    assert r.returncode != 0 and reworks(repo, d) == []
    cmds = [l for l in r.stdout.splitlines() + r.stderr.splitlines() if "overnight.py" in l and " park " in l]
    assert len(cmds) == 1
    parts = shlex.split(cmds[0])
    assert "$(echo x)" in cmds[0] and word in " ".join(parts)
    assert parts[parts.index("--req") + 1] == "R1" and parts[parts.index("--kind") + 1] == "other"
    assert parts[parts.index("--op") + 1] == "要件の文を直す"
    reason = parts[parts.index("--reason") + 1]
    assert "要らなくする" in reason and word in reason and p in reason
