"""夜通しの前提の確認（autopilot.py の lint〔人に示す前〕と approve から呼ぶ）。(errors, warnings) を返す。

- AWS の SSO: spec の自走の範囲の `- AWS の profile:` が名前なら、その profile の SSO のセッションの終わりを ~/.aws/config と
  ~/.aws/sso/cache の expiresAt で読む。承認から予算とマージ後の予算を足した時刻（見込みの夜の終わり）より前に切れるなら
  ERROR、その 2 倍（Stop hook が放す時点）より前なら NOTE。cache に refreshToken があれば expiresAt は延びるので、`aws sts get-caller-identity` が今通るなら NOTE、通らなければ ERROR。
  読めなければ止める側に倒す。
- GDD: repo の `.claude/gdd-dev.local.md` の `active:` が false 以外（大文字・字下げ・注釈・読めない値を含む）で、Claude Code の設定で
  GDD の plugin が有効なら ERROR（GDD の hook が自走を止める）。有効でなければ、GDD を外した後に残った lock なので NOTE。
  設定は user（CLAUDE_CONFIG_DIR か ~/.claude）・project・local の settings.json の順に後が勝つ。読めない設定は有効とみなす。
  この判定は user・project・local の settings.json だけを読む。それ以外の経路（--plugin-dir・--setting-sources・--settings など）で GDD が読み込まれていれば、GDD の hook が止めうる（NOTE の文でもそう知らせる）。
- 夜の NOTE（keep-awake・バッテリー・macOS の更新・見回り役）は、見込みの長さ（予算とマージ後の予算と前に並ぶ分）が 60 分を超えるか、
  予算が読めないときだけ出す。1 時間以内の昼の run には関係しない。SSO と GDD は長さによらず検査する。
- keep-awake: pmset があり、PreventUserIdleSystemSleep も PreventSystemSleep も 0 なら NOTE（承認のときに人に示す）。
  `pmset -g batt` がバッテリー駆動（'Battery Power'）なら NOTE（蓋を閉じるとバッテリーのまま眠り、keep-awake では止められない）。
- macOS の更新: SoftwareUpdate の AutomaticallyInstallMacOSUpdates が 1 なら NOTE（夜に更新が入ると再起動しうる。システムの
  設定なので agent は変えず、人に委ねる）。
"""
import configparser
import json
import os
import re
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

GDD_ACTIVE = re.compile(r"^\s*active\s*:\s*(.*?)\s*(?:#.*)?$", re.M | re.I)
NIGHT_MINUTES = 60  # 見込みの長さがこれ以下なら、夜通し向けの NOTE を出さない
AWAKE = re.compile(r"^\s*(PreventUserIdleSystemSleep|PreventSystemSleep)\s+(\d+)\s*$", re.M)


def check(text, now=None, cwd=None):
    errors, warnings = sso(text, now or time.time())
    root = git_root(cwd)
    gdd = (root / ".claude" / "gdd-dev.local.md") if root else None
    values = [v.lower() for v in GDD_ACTIVE.findall(gdd.read_text(encoding="utf-8", errors="replace"))] if gdd and gdd.is_file() else []
    if values and values != ["false"]:  # false 以外（true・yes・読めない値・複数の行）は GDD が有効と読みうる
        if gdd_plugin_on(root):
            errors.append("GDD のワークフローが有効（.claude/gdd-dev.local.md の active: が false 以外）。GDD の hook が自走を止めるので、"
                          "/gdd-dev を終えるか active: false にしてから承認する")
        else:
            warnings.append(f"{gdd} の active: が false 以外のまま残っているが、settings.json で GDD の plugin が有効でないので"
                            "自走は止めない（この判定は user・project・local の settings.json だけを読む。それ以外の経路（--plugin-dir・--setting-sources・--settings など）で GDD が読み込まれていれば、GDD の hook が止めうる）。"
                            "GDD を使わないなら、このファイルは消してよい")
    if overnight_run(text, now):
        warnings += keep_awake() + power() + auto_update() + watcher()
    return errors, warnings


def overnight_run(text, now):
    """夜通し回しうる run か。予算が読めなければ長さが分からないので True。now は前に並ぶ分を足した時刻。"""
    import overnight  # sso と同じ読み手（overnight.budgets）で読む
    budget, post = overnight.budgets(text)
    if budget is None:
        return True
    ahead = max(0, ((now or time.time()) - time.time()) / 60)
    return budget + post + ahead > NIGHT_MINUTES


def gdd_plugin_on(root):
    """Claude Code の設定（user → project → local の順に後が勝つ）で GDD の plugin が有効か。読めない設定は有効とみなす。"""
    user = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    on = {}
    for f in (user / "settings.json", root / ".claude" / "settings.json", root / ".claude" / "settings.local.json"):
        if not f.is_file():
            continue
        try:
            plugins = json.loads(f.read_text(encoding="utf-8")).get("enabledPlugins", {})
            on.update({k: v for k, v in plugins.items() if k.startswith("gate-driven-development@")})
        except (OSError, ValueError, AttributeError):
            return True
    return any(v is not False for v in on.values())


def watcher():
    """見回り役（scripts/watch.py）が launchd に入っているか。入っていない・古い場所を指すなら NOTE。"""
    f = Path.home() / "Library" / "LaunchAgents" / "com.spec-autopilot.watch.plist"
    how = (f"入れ方: python3 {Path(__file__).resolve().parent / 'watch.py'} plist > {f} と "
           f"launchctl bootstrap gui/$(id -u) {f}")
    if not f.is_file():
        return [f"見回り役が入っていない。夜の間に Claude アプリが再起動すると、止まった run を朝まで誰も起こさない。{how}"]
    paths = re.findall(r"<string>([^<]*watch\.py)</string>", f.read_text(encoding="utf-8", errors="replace"))
    if not paths or not all(Path(p).is_file() for p in paths):
        return [f"見回り役の plist が無いファイルを指している（plugin の更新の後など）。{how}"]
    return []


def run_out(*cmd):
    try:
        return subprocess.run(list(cmd), capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def power():
    if not shutil.which("pmset") or "'Battery Power'" not in run_out("pmset", "-g", "batt"):
        return []
    return ["Mac がバッテリーで動いている。蓋を閉じるとバッテリーのまま眠り、keep-awake でも止められない。"
            "電源につなぎ、蓋を開けておく（閉じるなら外部ディスプレイと電源をつなぐ）"]


def auto_update():
    if not shutil.which("defaults"):
        return []
    out = run_out("defaults", "read", "/Library/Preferences/com.apple.SoftwareUpdate", "AutomaticallyInstallMacOSUpdates")
    if out.strip() != "1":
        return []
    return ["macOS の更新の自動インストールが有効（AutomaticallyInstallMacOSUpdates = 1）。夜に更新が入ると再起動して自走が止まる。"
            "夜通し回す夜は、システム設定のソフトウェアアップデートで自動インストールを切る"]


def git_root(cwd):
    r = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=cwd, capture_output=True, text=True)
    return Path(r.stdout.strip()) if r.returncode == 0 else None


def keep_awake():
    if not shutil.which("pmset"):
        return []
    try:
        out = subprocess.run(["pmset", "-g", "assertions"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired):
        out = ""
    if any(int(v) > 0 for _, v in AWAKE.findall(out)):
        return []
    return ["keep-awake が効いていない（pmset の PreventUserIdleSystemSleep・PreventSystemSleep が 0）。夜の間に Mac が眠ると"
            "自走が止まる。Claude Desktop の keep-awake か caffeinate を入れてから寝る"]


def sso(text, now):
    import overnight  # lint・approve と同じ読み手（overnight.scope_rows・overnight.budgets）で読む
    profile = (overnight.scope_rows(text) or {}).get("AWS の profile")
    if not profile or profile == "なし" or not overnight.PROFILE.match(profile):
        return [], []
    budget, post = overnight.budgets(text)
    budget, post = budget or 0, post or 0
    end, twice = now + (budget + post) * 60, now + 2 * (budget + post) * 60
    login = f"`aws sso login --profile {profile}` でログインし直してから承認する"
    url, err = start_url(profile)
    if err:
        return [f"AWS の profile「{profile}」: {err}"], []
    caches = [f for f in (Path.home() / ".aws" / "sso" / "cache").glob("*.json") if start_url_of(f) == url]
    expires = [x for x in (expires_at(f) for f in caches) if x is not None]
    if not expires:
        return [f"AWS の profile「{profile}」の SSO のセッションが ~/.aws/sso/cache に無い。{login}"], []
    left = max(0, (max(expires) - time.time()) / 60)
    if any(refreshable(f) for f in caches):
        if not alive(profile):
            return [f"AWS の profile「{profile}」の SSO は refresh token の形だが、今 `aws sts get-caller-identity` が通らない。{login}"], []
        return [], [f"AWS の profile「{profile}」の SSO は refresh token で延びる形で、終わりの時刻を読めない（今の残り {left:.0f} 分）"]
    if max(expires) < end:
        return [f"AWS の profile「{profile}」の SSO のセッションが残り {left:.0f} 分で、見込みの夜の終わり（予算とマージ後の予算）"
                f"より前に切れる。{login}"], []
    if max(expires) < twice:
        return [], [f"AWS の profile「{profile}」の SSO のセッションは残り {left:.0f} 分で、予算の 2 倍までは続かない。"
                    "切れたら残りの操作を park に積む"]
    return [], []


def alive(profile):
    """今のセッションで profile の資格情報を引けるか。aws が無い・時間切れ・失敗は止める側に倒す。"""
    if not shutil.which("aws"):
        return False
    try:
        return subprocess.run(["aws", "sts", "get-caller-identity", "--profile", profile],
                              capture_output=True, timeout=30).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def start_url(profile):
    c = configparser.RawConfigParser()
    try:
        c.read(Path.home() / ".aws" / "config", encoding="utf-8")
    except (OSError, configparser.Error) as e:
        return None, f"~/.aws/config が読めない（{type(e).__name__}）"
    section = "default" if profile == "default" else f"profile {profile}"
    if not c.has_section(section):
        return None, "~/.aws/config に無い"
    if c.has_option(section, "sso_start_url"):
        return c.get(section, "sso_start_url"), None
    session = c.get(section, "sso_session", fallback=None)
    if session and c.has_option(f"sso-session {session}", "sso_start_url"):
        return c.get(f"sso-session {session}", "sso_start_url"), None
    return None, "SSO の profile でない（sso_start_url が無い）。夜通しで切れない認証かを人が確かめ、この行を「なし」にする"


def load(f):
    try:
        v = json.loads(f.read_text(encoding="utf-8"))
        return v if isinstance(v, dict) else {}
    except (OSError, ValueError):
        return {}


def start_url_of(f):
    return load(f).get("startUrl")


def refreshable(f):
    return bool(load(f).get("refreshToken"))


def expires_at(f):
    try:
        raw = load(f).get("expiresAt", "")
        return datetime.fromisoformat(raw.replace("UTC", "+00:00").replace("Z", "+00:00")).timestamp()
    except (ValueError, AttributeError, TypeError):
        return None
