# 範囲・デプロイ・本番の判定と待ちの記録を、overnight.py から deploy.py に移す

- ADR: docs/adr/2026-11-27-split-deploy.md

## 目的
人の発言:「リファクタしてから改善を始めたい」「別のセッションで改善中なので被らないようにして」「全部終わるまで自走して欲しい」。親の spec（2026-11-26-split-modules）の R2 を受け持つ。overnight.py は別のセッションの PR のマージで 1510 行になり、利用者の規則の上限（1500 行）を超えた。できあがったら overnight.py は約 550 行減り、行を足す改善を上限の内で始められる。挙動・CLI の出力・テストの期待は変わらない。

## 要件
- R1: 範囲・デプロイ・本番・ロールバックの判定と、待ちの記録と予算を overnight.py の外に移したとき、overnight.py は 1100 行以下になり、overnight.py に移した名前を外へ出し直す行（re-export）は無く、テストの全量が通り、CLI（overnight.py と autopilot.py。移す名前を通る overnight.py の `report`・`qa`・`ready`・`await`・`merged`・`notify` と、autopilot.py の `lint`・`check`・`status`・`block`・`wait` を含む）の出力とエラー文は変わらない。

## 非目標
- 関数の中身を書き換えること（移すだけ。import の行と参照の名前の頭だけを変える）
- 入力の種類の検査・review_gate・CLI の関数（overnight.py:512-651、753 以降）を移すこと
- gh・gh_json を移すこと（CLI の側で使い、移す区画は使わない）
- テストの期待を変えること（参照の向け先だけを変える）
- 版数を上げること

## 影響範囲
- 変える: plugins/spec-autopilot/scripts/overnight.py:50-510（SCOPE_SECTION、FULL、MERGE、PR、SCOPES、SCOPE_KEYS、REQUIRED_FOR_FULL、AUTO_DEPLOY、NO_DEPLOY、ROUND_KEYS、OPTIONAL_KEYS、NOTIFY、PROFILE、SCOPE_ROW、SMOKE、BROKEN、UNKNOWN、CONFIRMED、RESTORED、POST_BUDGET、PARK_KINDS、OK、SKIP、PENDING、FLAKE、RUN_ID、MAX_DEPLOY_FIXES、DEFAULT_TIMEOUT、GRACE_SEC、AWAIT_FILE、AWAITS_LOG、scope_rows、budgets、REVERT、ROLLBACK_CMD、rollback_cmd、WORKFLOW_NAME、workflow_names、deploy_check_lint、scope_lint、scope_of、head、contains、only_tests_and_docs、scope_errors、no_deploy、qa_origins、deploy_stage、deploy_parked、failed_deploys、deploy_exhausted、deploy_smoke、deploy_view、deploy_workflows、deploys_of_last_merge、stage_errors、going_back、production、production_label、production_errors、stage_failures、rollback_error）
- 変える: plugins/spec-autopilot/scripts/overnight.py:652-752（awaits、deploy_floor、UNREADABLE_PROD、UnreadableAwaits、_awaits、parked_ops、exempt_kinds、budget_view、await_record）
- 新規: plugins/spec-autopilot/scripts/deploy.py
- 呼び出し元: plugins/spec-autopilot/scripts/overnight.py:614-651
  - メモ: sha_errors・review_gate が head・only_tests_and_docs を使う。残る区画の本文は変えず、冒頭の import で取り込む
- 呼び出し元: plugins/spec-autopilot/scripts/overnight.py:768-1452
- 呼び出し元: plugins/spec-autopilot/scripts/autopilot.py:611-612
- 呼び出し元: plugins/spec-autopilot/scripts/autopilot.py:643-646
- 呼び出し元: plugins/spec-autopilot/scripts/autopilot.py:747-750
- 呼び出し元: plugins/spec-autopilot/scripts/autopilot.py:1058
  - メモ: cmd_block が `__import__("overnight").production_errors` を呼ぶ。`__import__` の形も deploy へ向ける
- 呼び出し元: plugins/spec-autopilot/scripts/autopilot.py:1079
  - メモ: cmd_wait が同じ形で production_errors を呼ぶ。1042-1044 の report・notify は overnight に残るので変えない
- 呼び出し元: plugins/spec-autopilot/scripts/autopilot.py:1120-1124
- 呼び出し元: plugins/spec-autopilot/scripts/lineup.py:40-42
- 呼び出し元: plugins/spec-autopilot/scripts/lineup.py:119-132
- 呼び出し元: plugins/spec-autopilot/scripts/lineup.py:328-334
- 呼び出し元: plugins/spec-autopilot/scripts/light.py:115-131
- 呼び出し元: plugins/spec-autopilot/scripts/preflight.py:53-54
- 呼び出し元: plugins/spec-autopilot/scripts/preflight.py:132-136
- 呼び出し元: plugins/spec-autopilot/scripts/watch.py:142-144
  - メモ: awaiting と tick_one は、モジュールを引数で受け取って await_record を呼ぶ。cmd_tick（296-305）が渡すモジュールを deploy にする
- 呼び出し元: plugins/spec-autopilot/scripts/watch.py:250-305
- 呼び出し元: plugins/spec-autopilot/hooks/stop.py:71-99
  - メモ: judge_building が budget_view・production_errors を呼び、awaiting にモジュールを渡して await_record を呼ばせる。import は今の overnight の import と同じく関数の中に置く
- 呼び出し元: plugins/spec-autopilot/hooks/stop.py:378-383
- 呼び出し元: plugins/spec-autopilot/tests/test_overnight.py:408-415
- 呼び出し元: plugins/spec-autopilot/tests/test_overnight.py:472
- 呼び出し元: plugins/spec-autopilot/tests/test_overnight.py:1137-1191
- 呼び出し元: plugins/spec-autopilot/tests/test_carry.py:16-235
- 呼び出し元: plugins/spec-autopilot/tests/test_merge_qa.py:99-162
- 呼び出し元: plugins/spec-autopilot/tests/test_rollback.py:1080-1087
- 手本: plugins/spec-autopilot/scripts/transcript.py:1
- 同じ入力: なし
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_overnight.py plugins/spec-autopilot/tests/test_carry.py plugins/spec-autopilot/tests/test_merge_qa.py plugins/spec-autopilot/tests/test_rollback.py plugins/spec-autopilot/tests/test_lineup.py plugins/spec-autopilot/tests/test_light.py plugins/spec-autopilot/tests/test_watch.py plugins/spec-autopilot/tests/test_autopilot.py plugins/spec-autopilot/tests/test_stop_bounds.py plugins/spec-autopilot/tests/test_goal.py -q -n auto

## 変えない挙動
- マージ・デプロイ・QA の段の判定: plugins/spec-autopilot/tests/test_merge_qa.py
- ロールバックの判定と本番の表示: plugins/spec-autopilot/tests/test_rollback.py
- 承認し直しでのマージとデプロイの記録の持ち越し: plugins/spec-autopilot/tests/test_carry.py
- 朝の報告の行: plugins/spec-autopilot/tests/test_overnight.py::test_the_morning_report_lists_per_requirement_merges_fixes_and_parks
- 見回り役が機械の待ちを生きているとみなす判定: plugins/spec-autopilot/tests/test_watch.py
- Stop hook の予算と import の失敗の守り: plugins/spec-autopilot/tests/test_stop_bounds.py

## 前提
- 目的に届く: overnight.py は約 550 行減り、親の R2（1100 行以下）に届く。親の R1 は子 1（split-transcript）で done。改善そのものは入らない
- 運用: 範囲・デプロイ・本番・待ちの記録の判定を直すときは deploy.py を直す。CLI の入口は overnight.py のまま。着手の前とマージの前に `gh pr list --state open` で、別の open の PR が overnight.py の 50-510・652-752 と影響範囲の呼び出し元を触っていないかを確かめ、触っていれば先にその PR のマージを待つか、載せ替えてから進める（spec を書いた時点で open の PR は 0 本）
- 普通のやり方: 外から呼ばれる名前の塊を別のモジュールへ移し、呼び出し元を新しいモジュールへ向け直す（互換の re-export を残さない。利用者の規則の「互換レイヤーを足さない」）
- 過去: 子 1（PR #95）で autopilot.py の transcript の区画を transcript.py に同じやり方で移した（`git log --oneline -- plugins/spec-autopilot/scripts/transcript.py` で確かめた）
- 前提: 移す 2 つの区画は、overnight.py の残る区画の名前を呼ばない（移す区画の中の名前と、標準ライブラリ・autopilot・carry・stages だけを使う）
  - path: plugins/spec-autopilot/scripts/overnight.py:50-510
  - path: plugins/spec-autopilot/scripts/overnight.py:652-752
  - メモ: ast で最上位の名前の参照を数えた。移す区画から残る区画への参照は 0 件。残る区画から移す区画へは 34 個の名前
- 前提: 外のファイルは overnight を関数の中で import するか、モジュールを引数で渡し、overnight を monkeypatch するテストは無い
  - path: plugins/spec-autopilot/hooks/stop.py:71-99
  - path: plugins/spec-autopilot/scripts/watch.py:142-144
  - コマンド: `grep -rn "setattr(overnight" plugins` → 0 件
- 前提: carry.py は overnight を import しない（deploy.py が carry を import しても循環しない）
  - path: plugins/spec-autopilot/scripts/carry.py:1-10
- 前提: overnight.py は scripts/ を sys.path に入れてから import する
  - path: plugins/spec-autopilot/scripts/overnight.py:43

## 作り方
この spec の ADR のとおり、overnight.py:50-510（範囲・デプロイ・本番・ロールバック）と 652-752（待ちの記録と予算）を、新しい `scripts/deploy.py` にそのまま移す。

- deploy.py は、移す区画が使う標準ライブラリ（json・os・re・subprocess・time・Path）と autopilot・carry・stages を import する
- overnight.py は冒頭で `from deploy import ...` と、自分の中で使う名前だけを取り込む（残る関数の本文を書き換えないため）。外へ出し直すための import はしない
- 外の呼び出し元（autopilot.py・lineup.py・light.py・preflight.py・watch.py・stop.py・テスト）は、移した名前を deploy から直接参照する。関数の中で import しているものは、同じ場所で `import deploy` する（stop.py の import の失敗の守りを外さない）
- watch.py と stop.py の awaiting に渡すモジュールは deploy にする

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | テストの全量を回し、`wc -l` で行数を数え、移した名前ごとに overnight.py の中の定義が無いことと、外の呼び出し元が `overnight.<名前>` を使っていないことを grep で確かめる。移す前（origin/main）と後で、同じ spec の写しに overnight.py の `report` と autopilot.py の `lint`・`check`・`status` を回し、出力を突き合わせる | テストが全部通り、overnight.py が 1100 行以下、外の `overnight.<移した名前>` が 0 件、出力が同じ |

## 制約
- 予算: 60 分
- 大きさ: M
- playbook: なし（挙動を変えないリファクタで、feature・bug-fix・iac・external-service のどれにも当たらない）
- 親 spec: 2026-11-26-split-modules
- 親の要件: R2

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
