"""commands/spec.md（壁打ちの手順）と commands/autopilot.md の A のつなぎを、コードと突き合わせる。
文に語があるかは見ない。command が呼ぶ CLI が argparse で通ることと、指す path が実在することだけを見る。"""
import re
import shlex
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN / "scripts"))

import autopilot as ap  # noqa: E402

SPEC_CMD = PLUGIN / "commands" / "spec.md"
AUTOPILOT_CMD = PLUGIN / "commands" / "autopilot.md"


def test_spec_command_has_frontmatter_description_and_argument_hint():
    text = SPEC_CMD.read_text(encoding="utf-8")
    head = re.match(r"---\n(.*?)\n---\n", text, re.S)
    assert head, "commands/spec.md に frontmatter が無い"
    assert re.search(r"^description: .+", head.group(1), re.M)
    assert re.search(r"^argument-hint: .+", head.group(1), re.M)


def test_spec_command_cli_invocations_parse_with_the_real_argparse(monkeypatch):
    """spec.md が書く `CLI <sub> ...` は、本物の argparse で通る（<..> は x に置き換える）。"""
    seen = []
    for name in ("cmd_init", "cmd_lint", "cmd_approve"):
        monkeypatch.setattr(ap, name, lambda a, n=name: seen.append((n, a)) or 0)
    spans = [s for s in re.findall(r"`CLI ([^`]+)`", SPEC_CMD.read_text(encoding="utf-8")) if not s.startswith("<sub>")]
    assert spans, "spec.md に `CLI ...` の呼び出しが無い"
    for sp in spans:
        ap.main(shlex.split(re.sub(r"<[^>]*>", "x", sp)))
    assert {n for n, _ in seen} >= {"cmd_init", "cmd_lint"}


def test_every_commands_md_reference_in_commands_exists():
    """commands/*.md が書く `commands/<x>.md` の参照は、全部実在する（spec.md と autopilot.md の相互参照を含む）。"""
    refs = set()
    for f in (PLUGIN / "commands").glob("*.md"):
        refs |= set(re.findall(r"commands/[\w.-]+\.md", f.read_text(encoding="utf-8")))
    assert refs, "commands/*.md に commands/<x>.md の参照が無い"
    missing = sorted(r for r in refs if not (PLUGIN / r).is_file())
    assert not missing, f"実在しない参照: {missing}"
    assert SPEC_CMD.is_file() and AUTOPILOT_CMD.is_file()
