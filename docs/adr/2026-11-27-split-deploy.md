# ADR: 範囲・デプロイ・本番の判定と待ちの記録を deploy.py に移し、呼び出し元を直接向け直す

- 日付: 2026-11-27
- 状態: Accepted
- spec: docs/specs/2026-11-27-split-deploy

## Context
overnight.py が 1510 行で上限（1500 行）を超えている。範囲・デプロイ・本番・ロールバックの判定（50-510）は、待ちの記録と予算の区画（652-752）の awaits・parked_ops・exempt_kinds・budget_view を呼ぶ。待ちの記録の区画は、ほかの区画を呼ばない。2 つの区画は、overnight.py の残る区画（入力の種類の検査・review_gate・CLI）を呼ばない。

## 選択肢
1. 2 つの区画をまとめて deploy.py に移す。overnight.py は自分で使う名前だけを import し、外の呼び出し元は deploy へ向け直す: 循環 import が無く、overnight.py は約 950 行になる
2. 判定（50-510）だけを deploy.py に移し、待ちの記録は overnight.py に残す: deploy.py が overnight を import し、overnight が deploy を import する循環になる
3. 判定を deploy.py、待ちの記録を awaits.py の 2 つに分ける: 循環は無いが、モジュールが 1 つ増え、呼び出し元の向け先が 2 つに分かれる。2 つの区画は一緒に呼ばれることが多い
4. 移した名前を overnight.py から出し直す: 呼び出し元を変えずに済むが、互換レイヤーになる

## Decision
1 を選ぶ。循環を作らず、親の R2（1100 行以下）に 1 回で届き、利用者の規則（互換レイヤーを足さない）に合う。子 1（transcript.py）と同じやり方で、残る関数の本文を書き換えずに済む。

## Consequences
- overnight.py は約 550 行減る
- 外の呼び出し元とテストの向け先が overnight から deploy に変わる
- deploy.py は約 560 行で、範囲・デプロイ・本番・待ちの記録の判定がまとまる
