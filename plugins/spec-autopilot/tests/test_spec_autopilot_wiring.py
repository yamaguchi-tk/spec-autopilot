"""spec-autopilot の配線を確かめる。

- manifest と marketplace.json の name・description がそろっている
- command が `references/<名前>.md` の形で指すファイルが、plugin の中に実在する
"""
import json
import re
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[1]
REPO = PLUGIN.parents[1]
MANIFEST = PLUGIN / ".claude-plugin" / "plugin.json"
MARKETPLACE = REPO / ".claude-plugin" / "marketplace.json"
COMMANDS = sorted((PLUGIN / "commands").glob("*.md"))


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_manifest_has_semver_and_name():
    manifest = _load(MANIFEST)
    assert manifest["name"] == "spec-autopilot"
    assert re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", manifest["version"])


def test_marketplace_entry_matches_manifest():
    market = _load(MARKETPLACE)
    entries = [p for p in market["plugins"] if p["name"] == "spec-autopilot"]
    assert len(entries) == 1, "marketplace.json に spec-autopilot がちょうど 1 件ない"
    entry = entries[0]
    assert entry["source"] == "./plugins/spec-autopilot"
    assert entry["description"] == _load(MANIFEST)["description"]


def test_commands_exist():
    assert COMMANDS, "commands/ に command が無い"


@pytest.mark.parametrize("command", COMMANDS, ids=lambda p: p.name)
def test_referenced_files_exist(command):
    refs = set(re.findall(r"references/[A-Za-z0-9_/-]+\.md", command.read_text(encoding="utf-8")))
    assert refs, f"{command.name} が references/ を 1 つも指していない"
    missing = sorted(r for r in refs if not (PLUGIN / r).is_file())
    assert not missing, f"{command.name} が指す実在しないファイル: {missing}"


def test_hooks_json_points_to_existing_scripts():
    hooks = _load(PLUGIN / "hooks" / "hooks.json")["hooks"]
    commands = [h["command"] for groups in hooks.values() for g in groups for h in g["hooks"]]
    assert commands, "hooks.json に hook が無い"
    for command in commands:
        for rel in re.findall(r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\"\s]+)", command):
            assert (PLUGIN / rel).is_file(), f"hooks.json が指す {rel} が無い"


def test_cli_messages_point_to_existing_command_sections():
    """CLI の案内が指す /autopilot の節が、command の見出しにある。"""
    names = set(re.findall(r"/autopilot の「([^」]+)」", (PLUGIN / "scripts" / "autopilot.py").read_text(encoding="utf-8")))
    assert names, "autopilot.py に /autopilot の節を指す案内が無い"
    heads = {m.strip() for m in re.findall(r"^#+ (?:[A-Z0-9]+\. )?(.+)$", (PLUGIN / "commands" / "autopilot.md").read_text(encoding="utf-8"), re.M)}
    assert not names - heads, f"見出しに無い節: {sorted(names - heads)}"


def test_version_is_raised_past_0_1_12():
    v = _load(MANIFEST)["version"]
    assert tuple(int(x) for x in v.split(".")) > (0, 1, 12)
