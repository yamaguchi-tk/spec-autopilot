# ADR: transcript の数え上げを transcript.py に移し、呼び出し元を直接向け直す

- 日付: 2026-11-26
- 状態: Accepted
- spec: docs/specs/2026-11-26-split-transcript

## Context
autopilot.py が 1526 行で上限（1500 行）を超えている。transcript を読んで数える区画（1306-1442）は、autopilot.py のほかの関数を呼ばず、外（stop.py・overnight.py・テスト）からも呼ばれる、まとまった塊である。

## 選択肢
1. 1306-1442 を transcript.py に移し、外の呼び出し元を transcript へ向け直す。autopilot.py は自分で使う名前だけを import する: 循環 import が無く、re-export も残らない。テストの参照の向け先が変わる
2. 1306-1478（session_transcript・done_anomalies・cmd_anomalies を含む）を移す: prompt_file と cmd_done に絡み、autopilot と transcript が互いを import する
3. 移した名前を autopilot.py から出し直す: 呼び出し元を変えずに済むが、互換レイヤーになる

## Decision
1 を選ぶ。循環を作らず、利用者の規則（互換レイヤーを足さない）に合う。human_said_at の本文を書き換えずに済む。

## Consequences
- autopilot.py は約 135 行減る
- テストの monkeypatch の向け先が autopilot から transcript に変わる
