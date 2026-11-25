"""作り直しの ADR の「直し方」の行を、rework の入口から確かめる（R1・R2）。"""
import json
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


def test_two_requirement_sentence_rejections_on_one_req_both_land_in_parked(repo):
    d = ready(repo)
    w1 = "a \"b\" $(touch PWNED) c'd"
    p = adr(repo, "two.md", "- 直し方: 局所の継ぎ足し", f"- 要件の文で退けた: 要らなくする（R1 の「{w1}」）",
            "- 要件の文で退けた: 入力の約束を変える（R1 の「盤面」）", "- 退けた: 設計を変える（y）")
    r = rework(repo, d, p)
    cmds = [l for l in r.stdout.splitlines() + r.stderr.splitlines() if "overnight.py" in l and " park " in l]
    for c in cmds:
        subprocess.run(["sh", "-c", c], cwd=repo, capture_output=True, text=True)
    assert not (repo / "PWNED").exists() and not (d / "PWNED").exists()
    parked = json.dumps(state(d).get("parked"), ensure_ascii=False)
    assert "要らなくする" in parked and "入力の約束を変える" in parked and "盤面" in parked and "PWNED" in parked


def test_requirement_sentence_rejection_of_unknown_req_is_refused_at_once(repo):
    d = ready(repo)
    p = adr(repo, "unk.md", "- 直し方: 設計を変える", "- 要件の文で退けた: 要らなくする（R9 の「x」）",
            "- 退けた: 入力の約束を変える（y）")
    r = rework(repo, d, p)
    assert r.returncode != 0 and "R9 は spec.md の要件に無い" in r.stdout + r.stderr
    assert " park " not in r.stdout + r.stderr


REFS = Path(__file__).resolve().parents[1] / "references"


def _section2(text):
    return text.split("\n## 2.", 1)[1].split("\n## 3.", 1)[0]


def _positions(text):
    return [text.index(st) for st in rootcause.FIX_ORDER]


def test_dead_end_section2_lists_fix_stages_in_fix_order():
    pos = _positions(_section2((REFS / "dead-end.md").read_text(encoding="utf-8")))
    assert pos == sorted(pos)


def test_adr_template_lists_fix_stages_in_fix_order():
    pos = _positions((REFS / "adr-template.md").read_text(encoding="utf-8"))
    assert pos == sorted(pos)


def test_documented_line_examples_match_the_shapes_rootcause_reads():
    for name in ("dead-end.md", "adr-template.md"):
        text = (REFS / name).read_text(encoding="utf-8")
        text = _section2(text) if name == "dead-end.md" else text
        ex = "\n".join(l.strip().strip("`") for l in text.splitlines() if l.strip().strip("`").startswith("- ") and "段" not in l[:3])
        fixed = (ex.replace("<段>", "設計を変える").replace("<理由>", "理由").replace("R<n>", "R1")
                 .replace("<要件の語>", "語"))
        assert rootcause.FIX_LINE.search(fixed), name
        assert rootcause.REJECT.search(fixed), name
        assert rootcause.REQ_REJECT.search(fixed), name


def test_rework_output_tells_to_keep_the_premise_memo_lines(repo):
    d = ready(repo)
    p = adr(repo, "ok.md", "- 直し方: 要らなくする")
    r = rework(repo, d, p)
    assert r.returncode == 0 and "メモ: 前提:" in r.stdout
