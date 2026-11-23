#!/usr/bin/env bash
# 使い方: CLAUDE_CODE_OAUTH_TOKEN=<claude setup-token の値> drive.sh <元の repo> <課題ファイル> <腕 H|P0> <回> <出力ディレクトリ>
# 元の repo を remote の無い手元の複製にし、許可リストの環境（HOME は空）で、模擬ユーザーと対話させる。
set -eu
case "${3:-}" in H|P0) ;; *) echo "腕は H か P0" >&2; exit 2;; esac
[ -n "${CLAUDE_CODE_OAUTH_TOKEN:-}" ] || { echo "CLAUDE_CODE_OAUTH_TOKEN が要る（claude setup-token で作る。HOME を空にするので、キーチェーンのログインは使えない）" >&2; exit 2; }
SRC=$(cd "$1" && pwd -P); TASK=$(cd "$(dirname "$2")" && pwd)/$(basename "$2"); ARM=$3; N=$4
OUT=$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$5")
case "$OUT/" in "$SRC"/*) echo "出力を元の repo の外に置く" >&2; exit 2;; esac
V=$(cd "$(dirname "$0")" && pwd)
PL=$(cd "$V/../../../plugins/spec-autopilot" && pwd)
R=$OUT/$(basename "$TASK" .md)-$ARM-$N; P=$R/proj
[ -e "$R" ] && { echo "$R はもうある" >&2; exit 2; }
BASE=$(sed -n 's/^base: //p' "$TASK"); REQ=$(sed -n 's/^依頼: //p' "$TASK")
[ -n "$BASE" ] && [ -n "$REQ" ] || { echo "課題ファイルに base: と 依頼: が要る" >&2; exit 2; }

snap() {  # 元の repo の、終わった後に比べる状態。パス・config・ref を含むので、agent の届く $R の下には置かない
  git -C "$SRC" for-each-ref; git -C "$SRC" stash list; git -C "$SRC" config --local --list
  git -C "$SRC" worktree list --porcelain; git -C "$SRC" status --porcelain
}
mkdir -p "$R/home" "$R/gh" "$R/tmp"
SNAP=$(mktemp -d "${TMPDIR:-/tmp}/drive-snap.XXXXXX")
snap > "$SNAP/before.txt"

git clone -q --no-hardlinks "$SRC" "$P"
git -C "$P" checkout -q -B bench "$BASE"
git -C "$P" remote | xargs -n1 git -C "$P" remote remove
git -C "$P" config user.name bench; git -C "$P" config user.email bench@example.invalid
# git が追っている認証の設定（.envrc・.env・.aws-config。雛形の .example などは残す）を消す
SECRETS=$(git -C "$P" ls-files | grep -E '(^|/)(\.envrc|\.env|\.env\.[^/]+|\.aws-config)$' | grep -vE '\.(example|sample|template)$' || true)
if [ -n "$SECRETS" ]; then
  printf '%s\n' "$SECRETS" | (cd "$P" && xargs git rm -q --)
  git -C "$P" commit -qm "bench: 認証の設定を外す"
fi
START=$(git -C "$P" rev-parse HEAD)
# 答えになる commit と元の repo のパスを残さない: bench 以外の ref を消し、reflog とたどれない object を消す
git -C "$P" for-each-ref --format='%(refname)' | grep -vx 'refs/heads/bench' | xargs -n1 git -C "$P" update-ref -d || true
git -C "$P" reflog expire --expire=now --all; git -C "$P" gc -q --prune=now

# 渡す環境は許可リストだけ。HOME は空、git の global・system の設定と credential helper は効かせず、転送は https だけ
ENV=(env -i HOME="$R/home" PATH="$PATH" USER="$USER" LANG="${LANG:-ja_JP.UTF-8}" TERM=xterm SHELL=/bin/bash TMPDIR="$R/tmp"
  CLAUDE_CODE_OAUTH_TOKEN="$CLAUDE_CODE_OAUTH_TOKEN" CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1
  AWS_CONFIG_FILE=/dev/null AWS_SHARED_CREDENTIALS_FILE=/dev/null AWS_EC2_METADATA_DISABLED=true GH_CONFIG_DIR="$R/gh"
  GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
  GIT_ALLOW_PROTOCOL=https GIT_TERMINAL_PROMPT=0 GIT_SSH_COMMAND=false SPEC_AUTOPILOT_HOME="$R/sa"
  SPEC_AUTOPILOT_TRUST_PROMPT_RECORD=1)  # claude -p は transcript に origin を書かないので、人の役の返事を hook の記録で確かめる
[ -d "$HOME/.cache/uv" ] && ENV+=(UV_CACHE_DIR="$HOME/.cache/uv")
cd "$P"

# 起動の前に、閉じたことを同じ環境で確かめる。1 つでも通れば止める
leak=""
[ -z "$("${ENV[@]}" git config --get-regexp '^credential' || true)" ] || leak="$leak credential.helper"
"${ENV[@]}" git ls-remote "$SRC" >/dev/null 2>&1 && leak="$leak 元の repo への転送"
command -v gh >/dev/null && "${ENV[@]}" gh auth token >/dev/null 2>&1 && leak="$leak gh"
command -v aws >/dev/null && "${ENV[@]}" aws sts get-caller-identity >/dev/null 2>&1 && leak="$leak aws"
[ -z "$leak" ] || { echo "閉じていない:$leak" >&2; exit 2; }

ISO=(--setting-sources project --strict-mcp-config --permission-mode bypassPermissions --disallowedTools "Bash(aws:*)" --output-format json)
SID=$(uuidgen | tr A-Z a-z)
touch "$R/started"; echo "start $(date +%s) base $BASE start $START" > "$R/log.txt"
claude_turn() {  # $1 は役（agent か user）。標準入力を prompt にし、結果の本文を last.txt に、費用を cost.log に書く
  role=$1; shift
  "${ENV[@]}" claude -p "$@" > "$R/last.json" 2> "$R/last.err" || true
  python3 - "$R" "$role" <<'PY'
import json, sys
r, role = sys.argv[1], sys.argv[2]
try:
    d = json.load(open(f"{r}/last.json"))
except ValueError:
    d = {"is_error": True, "result": open(f"{r}/last.json").read() + open(f"{r}/last.err").read()}
open(f"{r}/last.txt", "w").write(str(d.get("result", "")))
with open(f"{r}/cost.log", "a") as f:
    f.write(f"{role}\t{d.get('total_cost_usd', '')}\t{d.get('is_error')}\n")
sys.exit(1 if d.get("is_error") else 0)
PY
}
run() {
  if [ "$ARM" = H ]; then claude_turn agent --plugin-dir "$PL" --model opus "${ISO[@]}" "$@"; else claude_turn agent --model opus "${ISO[@]}" "$@"; fi
  rc=$?
  { echo "=== assistant"; cat "$R/last.txt"; } >> "$R/dialog.txt"
  echo "turn-end $(date +%s)" >> "$R/log.txt"
  return $rc
}
set +e
if [ "$ARM" = H ]; then echo "/spec-autopilot:autopilot $REQ" | run --session-id "$SID"; else echo "$REQ" | run --session-id "$SID"; fi
ok=$?
for i in $(seq 1 10); do
  [ $ok -eq 0 ] || { echo "error $(date +%s)" >> "$R/log.txt"; break; }
  if [ "$ARM" = H ]; then
    st=$(find "$R" -path '*/docs/specs/*/state.json' -newer "$R/started" -not -path '*/node_modules/*' | head -1)
    phase=$([ -n "$st" ] && python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['phase'])" "$st")
    echo "phase $phase" >> "$R/log.txt"
    case "$phase" in done|blocked) break;; esac
  fi
  last=$(cat "$R/last.txt")
  { cat "$V/persona-prompt.md"; echo; cat "$TASK"; echo; echo "相手の最後の発言:"; echo "$last"; } | claude_turn user --model sonnet --tools "" "${ISO[@]}"
  ok=$?; reply=$(cat "$R/last.txt")
  { echo "=== user"; echo "$reply"; } >> "$R/dialog.txt"
  echo "user $(date +%s)" >> "$R/log.txt"
  [ $ok -eq 0 ] || continue
  [ "$(printf %s "$reply" | tr -d '[:space:]')" = "<<END>>" ] && break
  echo "${reply//<<END>>/}" | run --resume "$SID"; ok=$?
done
echo "end $(date +%s)" >> "$R/log.txt"

# 変更の大きさ: すべての worktree の、commit していない変更を含めた差分（spec と ADR を除いた行数も）
git -C "$P" worktree list --porcelain | sed -n 's/^worktree //p' | while read -r wt; do
  echo "== $wt"
  git -C "$wt" add -A -N .
  git -C "$wt" diff --stat "$START"
  echo "-- docs/specs・docs/adr を除く"; git -C "$wt" diff --shortstat "$START" -- . ':(exclude)docs/specs' ':(exclude)docs/adr'
done > "$R/diffstat.txt"
snap > "$SNAP/after.txt"
if cmp -s "$SNAP/before.txt" "$SNAP/after.txt"; then echo "元の repo の状態: 変わらない" >> "$R/log.txt"; rm -r "$SNAP"
else echo "元の repo の状態: 変わった" >> "$R/log.txt"; echo "元の repo の状態が変わった: diff $SNAP/before.txt $SNAP/after.txt" >&2; fi
echo "$R"
