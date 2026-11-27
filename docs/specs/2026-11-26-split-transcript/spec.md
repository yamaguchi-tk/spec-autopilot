# transcript を読んで数える部分を、autopilot.py から transcript.py に移す

- ADR: docs/adr/2026-11-26-split-transcript.md

## 目的
人の発言:「リファクタしてから改善を始めたい」「別のセッションで改善中なので被らないようにして」。親の spec（2026-11-26-split-modules）の R1 を受け持つ。autopilot.py は別のセッションの PR（#51・#63・trust-marker-origin）のマージで 1526 行になり、利用者の規則の上限（1500 行）を超えた。できあがったら autopilot.py は約 135 行減り、挙動・CLI の出力・テストの期待は変わらない。

## 要件
- R1: transcript を読んで数える部分を autopilot.py の外に移したとき、autopilot.py は 1400 行以下になり、autopilot.py に移した名前を外へ出し直す行（re-export）は無く、テストの全量が通り、CLI（autopilot.py と overnight.py。移す名前を通る `anomalies`・`approve`・`resume`・`done`・overnight.py の `report` を含む）の出力とエラー文は変わらない。

## 非目標
- 関数の中身を書き換えること（移すだけ。import の行と参照の名前の頭だけを変える）
- autopilot.py の human_said_at・require_user_after の本文（251-303）を変えること（移した名前は冒頭の import で取り込む）
- session_transcript・done_anomalies・cmd_anomalies を移すこと（prompt_file と cmd_done に絡み、循環 import になる）
- テストの期待を変えること（参照の向け先だけを変える）
- 版数を上げること

## 影響範囲
- 変える: plugins/spec-autopilot/scripts/autopilot.py:1304-1440（ANOMALY_KINDS、EMPTY_BLOCKS、POLL_SEC、APPROVED_OUT、DONE_OUT、WAIT_OUT、RESUME_OUT、_LOOP、_LOOP_SLEEP、_SLEEP_SEC、_LONE_SLEEP、_NOT_HUMAN、_iso_epoch、_text、_results、Overdue、transcript_lines、_polls、anomalies、anomaly_line）
- 新規: plugins/spec-autopilot/scripts/transcript.py
- 呼び出し元: plugins/spec-autopilot/scripts/autopilot.py:251-275
  - メモ: human_said_at が transcript_lines と _iso_epoch を使う。本文は変えず、冒頭の import で取り込む
- 呼び出し元: plugins/spec-autopilot/scripts/autopilot.py:1013-1027
- 呼び出し元: plugins/spec-autopilot/scripts/autopilot.py:1443-1474
- 呼び出し元: plugins/spec-autopilot/hooks/stop.py:185-195
  - メモ: 190 の `from autopilot import transcript_lines` と 189 の docstring
- 呼び出し元: plugins/spec-autopilot/hooks/stop.py:395-410
  - メモ: 400・401・408。12 行目の docstring も直す
- 呼び出し元: plugins/spec-autopilot/scripts/overnight.py:1316
  - メモ: overnight.py の冒頭（44-47 の import の並び）に `import transcript` を足し、1316 を `transcript.anomaly_line` にする
- 呼び出し元: plugins/spec-autopilot/tests/test_stop_bounds.py:36-116
  - メモ: autopilot.Overdue・autopilot.anomalies・autopilot._polls と、88 行目の monkeypatch の向け先。19-20 で tests のヘルパ関数 `transcript` を import しているので、モジュールは別名で import する
- 手本: plugins/spec-autopilot/scripts/stages.py:1
- 同じ入力: なし
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_stop_bounds.py plugins/spec-autopilot/tests/test_anomalies.py plugins/spec-autopilot/tests/test_autopilot.py plugins/spec-autopilot/tests/test_overnight.py -q -n auto

## 変えない挙動
- Stop hook の transcript の走査は予算を過ぎたら止める側に倒れ、import の失敗を最初の停止なら止める: plugins/spec-autopilot/tests/test_stop_bounds.py
- 自走の異常の件数の数え方と出力: plugins/spec-autopilot/tests/test_anomalies.py
- 承認の人の発言の門（human_said_at が transcript を読む経路）: plugins/spec-autopilot/tests/test_autopilot.py::test_refuses_when_the_transcript_has_no_origin
- 印を立てても origin のある transcript の判定は緩めない: plugins/spec-autopilot/tests/test_autopilot.py::test_the_opt_in_does_not_loosen_a_transcript_with_origin
- 印を立てた run で origin の無い人の役の発言を数える: plugins/spec-autopilot/tests/test_autopilot.py::test_trust_mark_passes_an_originless_human_row_in_a_transcript_with_origin

## 前提
- 目的に届く: autopilot.py は約 135 行減る。overnight.py の分割（親の R2）は別の子で行う
- 運用: transcript の数え上げを直すときは transcript.py を直す。CLI の入口は autopilot.py のまま。着手の前とマージの前に `gh pr list --state open` で、別の open の PR が autopilot.py の 1304-1440・stop.py・overnight.py の 1316・test_stop_bounds.py を触っていないかを確かめ、触っていれば先にその PR のマージを待つか、載せ替えてから進める（spec の承認の時点で open の PR は 0 本）
- 普通のやり方: 外から呼ばれる名前の塊を別のモジュールへ移し、呼び出し元を新しいモジュールへ向け直す（互換の re-export を残さない。利用者の規則の「互換レイヤーを足さない」）
- 過去: stages.py・ladder.py・goal.py・light.py は autopilot.py の横に置いた小さいモジュールで、scripts/ を sys.path に入れて import している（`git log --oneline -- plugins/spec-autopilot/scripts/stages.py` で確かめた）
- 前提: transcript の区画（1304-1440）は json・re・time・datetime だけを使い、autopilot.py のほかの関数を呼ばない
  - path: plugins/spec-autopilot/scripts/autopilot.py:1304-1440
- 前提: autopilot.py の中では human_said_at（257・270・272）、cmd_done（1027）、done_anomalies（1458）、cmd_anomalies（1469）が区画の名前を使う
  - path: plugins/spec-autopilot/scripts/autopilot.py:251-275
  - path: plugins/spec-autopilot/scripts/autopilot.py:1013-1027
  - path: plugins/spec-autopilot/scripts/autopilot.py:1443-1474
- 前提: stop.py は autopilot の import を main の try の中（434）と関数の中（190）に置き、import の失敗を最初の停止なら止め、続行中なら放す
  - path: plugins/spec-autopilot/hooks/stop.py:425-443
  - path: plugins/spec-autopilot/tests/test_stop_bounds.py:202-212
- 前提: hooks/stop.py と overnight.py は scripts/ を sys.path に入れてから import する
  - path: plugins/spec-autopilot/hooks/stop.py:45
  - path: plugins/spec-autopilot/scripts/overnight.py:43

## 作り方
この spec の ADR のとおり、定数 `ANOMALY_KINDS` から `anomaly_line` まで（autopilot.py:1304-1440）を新しい `scripts/transcript.py` にそのまま移す。

- autopilot.py は冒頭で `from transcript import ...` と、自分の中で使う名前だけを取り込む（human_said_at の本文を書き換えないため）。外へ出し直すための import はしない（外の呼び出し元は transcript を直接参照する）
- stop.py は、transcript の import を今の autopilot の import と同じく関数の中に置く（import の失敗の守りを外さない）
- overnight.py は冒頭の import の並びに `import transcript` を足し、1316 を `transcript.anomaly_line` にする
- test_stop_bounds.py は、19-20 で tests のヘルパ関数 `transcript` を import しているので、モジュールを `import transcript as tr` のように別名で取り込み、`autopilot.Overdue` などを `tr.Overdue` に、88 行目の monkeypatch を `tr` に向ける。期待は変えない

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | テストの全量を回し、`wc -l` で行数を数え、移した名前ごとに autopilot.py の中の定義が無いことと、外の呼び出し元が `autopilot.<名前>` を使っていないことを grep で確かめる。CLI の `anomalies` を移す前（origin/main）と後で同じ transcript に、overnight.py の `report` を同じ spec に回し、出力を突き合わせる | テストが全部通り、autopilot.py が 1400 行以下、外の `autopilot.<移した名前>` が 0 件、出力が同じ |

## 制約
- 予算: 60 分
- 大きさ: M
- playbook: なし（挙動を変えないリファクタで、feature・bug-fix・iac・external-service のどれにも当たらない）
- 親 spec: 2026-11-26-split-modules
- 親の要件: R1

## モデル

## 自走の範囲
- 範囲: マージまで
- QA の環境:
- QA の書き込み先:
- デプロイの起動:
- デプロイの確かめ:
- ロールバック: revert の PR をマージし、デプロイの完了を確かめる
- 通知: デスクトップ
- AWS の profile: なし

## 止まる条件
- 合意した要件のどれかを満たす方法が無いと分かったとき（その要件だけを park に積み、ほかを進める。どの要件も進められないときだけ block）
- 承認した自走の範囲の外の操作が要るとき（実行せずに park に積む）
