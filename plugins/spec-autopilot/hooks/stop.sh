#!/bin/sh
# Stop hook の入口。stop.py の答えを返すのは、終了コードが 0 のときだけ。
# ほかの終わり方（シグナル・SyntaxError などの例外・python3 が無い 127 など）は、判定が出なかったものとして、
# 最初の停止は止め、続行中（payload の stop_hook_active が true）は放す。stop.py の例外の扱いと同じにする。
payload=$(cat)
out=$(printf '%s' "$payload" | python3 "$(dirname "$0")/stop.py")
rc=$?
if [ "$rc" -eq 0 ]; then
  [ -n "$out" ] && printf '%s\n' "$out"
  exit 0
fi
case $payload in
  *'"stop_hook_active": true'* | *'"stop_hook_active":true'*)
    printf '%s\n' "{\"systemMessage\": \"spec-autopilot の Stop hook が判定を出さずに終わった（終了コード ${rc}）ので放す\"}" ;;
  *)
    printf '%s\n' "{\"decision\": \"block\", \"reason\": \"spec-autopilot の Stop hook が判定を出さずに終わった（終了コード ${rc}）。docs/specs の state.json と成果物を確かめて続ける\"}" ;;
esac
exit 0
