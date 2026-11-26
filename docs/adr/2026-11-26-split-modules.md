# ADR: autopilot.py と overnight.py を、目的の spec 1 本と子 2 本で、挙動を変えずに分ける

- 日付: 2026-11-26
- 状態: Accepted
- spec: docs/specs/2026-11-26-split-modules

## Context
autopilot.py が 1500 行で、利用者の規則の上限に届いている。別のセッションの open の PR（#51・#63・#57）と未 PR のブランチ（trust-marker-origin）が、autopilot.py・overnight.py・preflight.py を変えている。人は「被らないようにして」「リファクタしてから改善を始めたい」「全部終わるまで自走して欲しい」と頼んだ。

## 選択肢
1. 目的の spec を 1 回承認し、子 1（transcript.py）を今、子 2（deploy.py）を #51・#63・#57 のマージ後に作る: 人の承認は 1 回。子 2 はマージ後の行番号で書けるので、被らない。マージが朝までに終わらなければ子 2 が残る
2. 子 1・子 2 を今まとめて承認する（`--queue`）: 子 2 の spec を今の行番号で書くので、#51 のマージで影響範囲が変わり、承認の後に spec を直す必要が出て止まる。子 2 の切り出しが #51 の足す `overnight.budgets` の呼び出しを壊す
3. open の PR が全部マージされるのを待ち、1 本で分ける: 待つ間、autopilot.py に足す PR が全部上限に当たる。差分が大きい 1 本になる
4. 区画を移して、元のモジュールに名前を出し直す（re-export）: 呼び出し元を変えずに済むが、利用者の規則（互換レイヤーを足さない）に反する

## Decision
1 を選ぶ。被りを避ける依頼と、人の承認を 1 回にする依頼の両方を満たす。子 1 は autopilot.py の 237-279 行（trust-marker-origin が変える予定）を書き換えず、冒頭の import で名前を取り込む。transcript の区画の中の `session_transcript`・`done_anomalies`・`cmd_anomalies` は `prompt_file` と `cmd_done` に絡むので、循環 import を避けるため autopilot.py に残す。

## Consequences
- autopilot.py は約 135 行、overnight.py は約 450 行減る
- テストの monkeypatch の向け先が `autopilot` から `transcript` に変わる（テストの期待は変えない）
- 子 2 は他のセッションのマージの時期に依る
