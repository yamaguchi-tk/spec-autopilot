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
    if command.name == "autopilot.md":
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


def test_version_is_raised_past_0_1_21():
    v = _load(MANIFEST)["version"]
    assert tuple(int(x) for x in v.split(".")) > (0, 1, 21)


def test_setup_command_exists_and_its_ladder_commands_run(tmp_path):
    """commands/setup.md は ladder.py のコマンドを書き、<...> を含まない行は一時の置き場でそのまま通る。"""
    import os
    import shlex
    import subprocess
    import sys

    setup = PLUGIN / "commands" / "setup.md"
    assert setup.is_file(), "commands/setup.md が無い"
    text = setup.read_text(encoding="utf-8")
    cmds = re.findall(r'^python3 "\$\{CLAUDE_PLUGIN_ROOT\}/scripts/ladder\.py" ([^\n<>]+)$', text, re.M)
    assert any(c.split()[0] == "show" for c in cmds), "setup.md に ladder.py show の行が無い"
    env = {**os.environ, "SPEC_AUTOPILOT_HOME": str(tmp_path)}
    for c in cmds:
        r = subprocess.run([sys.executable, str(PLUGIN / "scripts" / "ladder.py"), *shlex.split(c)], env=env, capture_output=True, text=True)
        assert r.returncode == 0, f"{c}: {r.stdout}{r.stderr}"


def _setup_options(rungs, default, cur):
    """commands/setup.md 手順 2 の選択肢の作り方を写したもの。"""
    opts = [f"今のまま（{cur}）"]
    if cur == default:
        return opts + [r for r in rungs if r != cur]
    return opts + [f"既定に戻す（{default}）"] + [r for r in rungs if r not in (cur, default)]


@pytest.mark.parametrize("role", ["実装", "評価", "相談", "検証", "照合"])
def test_setup_options_fit_ask_user_question_limit_for_every_current_rung(role, tmp_path):
    """show の受ける段と既定から作る選択肢は、今の段がどれでも 2〜4 個で、受ける段のどれにも届く。"""
    import os
    import subprocess
    import sys

    env = {**os.environ, "SPEC_AUTOPILOT_HOME": str(tmp_path)}
    out = subprocess.run([sys.executable, str(PLUGIN / "scripts" / "ladder.py"), "show"], env=env, capture_output=True, text=True).stdout
    m = re.search(rf"^{role}: 受ける段 (\S+) / 既定 (\S+) /", out, re.M)
    assert m, out
    rungs, default = m.group(1).split("・"), m.group(2)
    for cur in rungs:
        opts = _setup_options(rungs, default, cur)
        assert 2 <= len(opts) <= 4, f"{role} 今 {cur}: {opts}"
        reach = {cur, *(r for r in rungs if r in opts), *([default] if cur != default else [])}
        assert reach == set(rungs), f"{role} 今 {cur}: {opts}"


def test_setup_command_writes_every_role_with_a_flag_ladder_setup_takes_and_resets_every_role(tmp_path):
    """setup.md が書く setup の旗は ladder.py setup が受ける旗の全部（5 つの役）で、show の役の全部を reset で戻せる。"""
    import os
    import subprocess
    import sys

    text = (PLUGIN / "commands" / "setup.md").read_text(encoding="utf-8")
    env = {**os.environ, "SPEC_AUTOPILOT_HOME": str(tmp_path)}
    ladder = [sys.executable, str(PLUGIN / "scripts" / "ladder.py")]
    helptext = subprocess.run([*ladder, "setup", "-h"], env=env, capture_output=True, text=True).stdout
    taken = set(re.findall(r"--(?!reset|help|session)([a-z-]+)", helptext))
    lines = re.findall(r'^python3 "\$\{CLAUDE_PLUGIN_ROOT\}/scripts/ladder\.py" setup ([^\n]+)$', text, re.M)
    used = {f for ln in lines for f in re.findall(r"--(?!reset|session)([a-z-]+)", ln)}
    assert taken == {"impl", "review", "advisor", "checker", "spec-checker"}
    assert used == taken, f"setup.md の旗: {sorted(used)} / setup が受ける旗: {sorted(taken)}"
    show = subprocess.run([*ladder, "show"], env=env, capture_output=True, text=True).stdout
    roles = re.findall(r"^(\S+): 受ける段", show, re.M)
    assert len(roles) == 5
    for role in roles:
        assert f"--reset {role}" in text, f"setup.md に --reset {role} が無い"
