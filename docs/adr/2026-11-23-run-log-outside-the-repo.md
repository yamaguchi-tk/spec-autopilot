# ADR: 自走の結果の記録を、repo の外の追記だけのファイルに残す

- 状態: 採用（2026-11-23）
- spec: docs/specs/2026-11-23-record-for-reading/spec.md

## 背景

この plugin 自身の開発の進め方（CLAUDE.md）は、`/autopilot` で回した最初の 5 本で、承認からの分数・blocked の回数と理由・マージ後の手戻りの PR の数を読むと決めた。ところが、範囲が「マージまで」の spec は done がマージの後に state.json を書くので、その記録は main に入らず、worktree を消すと消える（Issue #6）。再承認では `approved_at` が書き直され、前の巡の確認待ちの時間も history に残らない。手戻りの spec を元の spec とつなぐ欄も無い。

## 決定

- done と block のたびに、1 行の JSON を `SPEC_AUTOPILOT_HOME`（既定は `~/.claude/spec-autopilot`）の `runs.jsonl` に追記する。読むのは人か agent で、`tail` と `jq` で足りる
- 再承認のとき、前の巡の確認待ちの秒数（`paused_sec`）も history に移し、承認からの分数は巡ごとに足して出す
- 手戻りの spec は「## 制約」に `- 手戻り元: <元の spec のディレクトリ名>` を書き、done の記録に写す

- 書く関数は `scripts/runlog.py` に分ける。autopilot.py は 1,493 行で、ほかの部品（overnight・premises・stages）と同じく行の予算のため分けてきた

## 退けた案

- **state.json を main に入れる（マージ後の commit を push する）**: マージの後に main へ直接 push するか、記録だけの PR を毎回作ることになる。範囲の終点を変え、公開 repo の main に手元の時刻と理由が積もる
- **done の出力を PR のコメントに残す**: 範囲が「PR まで」の spec は PR の前に done になる。block の記録も残らない。gh が使えない環境で残らない
- **記録を読む CLI（`CLI runs`）を足す**: 5 本を読むだけなら `jq` で足りる。読む形が決まってから足す
