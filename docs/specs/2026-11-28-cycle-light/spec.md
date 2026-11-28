# light.py の判定を下の層に出し、autopilot.py が light.py を import しないようにして、import の輪を 4 から 3 モジュールに縮める

- ADR: docs/adr/2026-11-28-cycle-light.md

## 目的
人の発言:「結合度　凝集度　複雑さ 等々の必要なソフトウェアメトリクスを指標にして欲しい」「リファクタの spec」「承認する」「次の子へ進む」「次の子へ進む」「親の基準を緩める」「承認する」「入り口として扱うとどうなる？」「入口として扱う」「承認する」。親の spec（2026-11-28-metrics-refactor-goal）の R4・R5 のうち、5 本目を受け持つ。

観測: 4 本目（2026-11-28-cycle-goal）の後、輪は autopilot・light・lineup・overnight の 4 つで残る。autopilot.py が light.py から使うのは、check の中の `__import__("light").errors` だけ。light.errors と、それが呼ぶ保護 path と自走の範囲のコマンドの判定（light.py:30-149）は、autopilot.py のうち stages.py にある名前（section・COMMENT_BLOCK・classify・repo_root）と deploy.py だけを使う。light.py の残り（cmd_approve と main）は、autopilot.py の lint・take_over などを使う CLI の入口。

できあがったら、autopilot.py は light.py を import せず、light.py は autopilot.py の上に立つ入口になり、輪は autopilot・lineup・overnight の 3 つに縮む。

## 要件
- R1: plugins/spec-autopilot/scripts を測ったとき、light.py は import の輪に入らず、輪は autopilot.py・lineup.py・overnight.py の 3 つの 1 つだけになる。
- R2: autopilot.py を読んだとき、light を import する文（関数の中の import と、名前を文字列で渡す `__import__` を含む）が無く、light.py の判定は下の層のモジュールから呼ぶ。輪を `importlib`・変数で名前を渡す `__import__`・`sys.modules` に替えて道具に見えなくする形も無い。
- R3: 測ったとき、light.py から出した判定を置く下の層のモジュールは、scripts のモジュールを stages.py と deploy.py のほかに import せず、LCOM4 が 2 以下になる。
- R4: テストの全量が通り、`light.py approve` と CLI の check・lint・done の出力を、変える前と後で同じ spec（保護 path に触れる軽量フローの spec と、合意ありの spec）に回した出力が同じで、指標の前後の比べ方（着手の commit を前にする）で、親の R5 のただし書きの autopilot.py の LCOM4 と fan-out を除いて悪化が無く、「移しただけ」と出ない。除いた 2 つの値は前と後を証拠に書く。テストは名前の向け先だけを変え、期待は変えない（tests/test_import_layers.py の輪の期待は、親の R5 のとおり新しい値に直す）。

## 非目標
- lineup・overnight を輪から出すこと（後の子で扱う）
- light.py の cmd_approve が autopilot.py の名前を使うのを向け直すこと（入口は autopilot.py に依ってよい）
- premises.py・rootcause.py が受ける `sys.modules[__name__]` と、autopilot.py 経由の出し直しを直すこと（後の子で扱う）
- 複雑度・凝集度を目標にすること（親の R2・R3 の子で扱う）
- 挙動・CLI の出力・エラー文を変えること
- 版数を上げること

## 影響範囲
- 変える: plugins/spec-autopilot/scripts/light.py（全体）
  - メモ: 30-149 の DEFAULT_PROTECTED・CONFIG・EMPTY_TREE・config_lines・git・patterns・pathspecs・changed・hits・KEYS・command_errors・errors を下の層に移し、cmd_approve はそこから import して使う
- 変える: plugins/spec-autopilot/scripts/autopilot.py（全体）
  - メモ: 665 の `__import__("light").errors` を、下の層のモジュールの errors に替える
- 新規: plugins/spec-autopilot/scripts/light_rules.py
  - メモ: light.py から移す判定。stages の名前を直接 import し、`ap.` を外す
- 変える: plugins/spec-autopilot/tests/test_import_layers.py（全体）
  - メモ: 輪の期待を 3 つに直し、R1〜R3 のテストを足す
- 呼び出し元: plugins/spec-autopilot/tests/test_light.py:489
  - メモ: `light.command_errors` を読む。light.py が command_errors を import するので、テストは変えない
- 手本: plugins/spec-autopilot/scripts/session.py:1-10（stages だけを import する下の層のモジュール。前の子で足した）
- 同じ入力: なし
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_advisor_approval.py plugins/spec-autopilot/tests/test_autopilot.py plugins/spec-autopilot/tests/test_carry.py plugins/spec-autopilot/tests/test_consent_adr.py plugins/spec-autopilot/tests/test_deploy_failure.py plugins/spec-autopilot/tests/test_goal_command.py plugins/spec-autopilot/tests/test_import_layers.py plugins/spec-autopilot/tests/test_input_kinds.py plugins/spec-autopilot/tests/test_light.py plugins/spec-autopilot/tests/test_main_progress.py plugins/spec-autopilot/tests/test_merge_qa.py plugins/spec-autopilot/tests/test_overnight.py plugins/spec-autopilot/tests/test_qa_evidence.py plugins/spec-autopilot/tests/test_rollback.py plugins/spec-autopilot/tests/test_runlog.py plugins/spec-autopilot/tests/test_size.py plugins/spec-autopilot/tests/test_stages.py plugins/spec-autopilot/tests/test_stop_bounds.py -q -n auto
  - メモ: light・check を回すテストと、autopilot を直接 import するテストのファイル（`grep -lE '\blight\b|import autopilot|autopilot as ap|check.*--stage|"check"' plugins/spec-autopilot/tests/*.py`）。全量は PR の CI が回す（CLAUDE.md:5）

## 変えない挙動
- テストの全量: plugins/spec-autopilot/tests/
- 軽量フローの承認と保護 path の判定: plugins/spec-autopilot/tests/test_light.py
- マージ・QA の段の判定: plugins/spec-autopilot/tests/test_merge_qa.py

## 前提
- 目的に届く: 輪は 4 から 3 モジュールに縮むが、0 にはならない。残りの lineup・overnight と、premises・rootcause の `sys.modules[__name__]` と出し直しは、後の子で扱う
- 運用: 指標は repo の外の測る道具（refactor-metrics の skill）で測る。評価役は、手元の道具で着手の commit と tip を比べる
- 普通のやり方: import の輪は、共通の部分を役ごとの下の層に出し、依存の向きを 1 つにそろえて切る。親の spec は、light・lineup・overnight を autopilot.py の上に立つ CLI の入口として扱う
  - メモ: 親の spec の R4 と作り方の子 2、この spec の ADR
- 過去: 4 本目は、goal.py が借りる補助を state・out・session に出して goal.py を輪から外した（PR 133）
  - メモ: docs/specs/2026-11-28-cycle-goal/spec.md
- 前提: 今の輪は autopilot・light・lineup・overnight の 4 つで、autopilot.py の fan-out は 18・LCOM4 は 8、light.py の fan-out は 3・LCOM4 は 1
  - コマンド: `uv run --with lizard python <refactor-metrics の skill>/scripts/measure.py plugins/spec-autopilot/scripts --json` → 上の値（main の b264566 の上で測った）
- 前提: autopilot.py が light.py を使うのは 665 の `__import__("light").errors` の 1 か所だけ
  - コマンド: `grep -nE 'import light|__import__\("light"\)|\blight\.' plugins/spec-autopilot/scripts/autopilot.py` → 665 の 1 行
- 前提: light.py の 30-149 が使う autopilot.py の名前は section・COMMENT_BLOCK・classify・repo_root の 4 つで、どれも stages.py にあり、ほかに deploy.py の名前を使う
  - コマンド: `sed -n 30,149p plugins/spec-autopilot/scripts/light.py | grep -oE 'ap\.[A-Za-z_]+' | sort -u` → 上の 4 つ
  - path: plugins/spec-autopilot/scripts/autopilot.py:46（stages から import する名前の並び）
- 前提: light.py の判定を light_rules.py に移すと、輪は autopilot・lineup・overnight の 3 つ、light_rules.py の fan-out は 2・LCOM4 は 1、autopilot.py の fan-out は 18・LCOM4 は 8 のまま
  - 未確認: main の b264566 の上の写しで移して道具で測った値で、repo の中では確かめられない

## 作り方
この spec の ADR のとおり、light.py の 30-149 を中身を変えずに light_rules.py に移す（`ap.` の名前は stages から import して直接使う）。light.py は cmd_approve が使う名前（EMPTY_TREE・command_errors・hits）を light_rules から import し、ほかは今のまま autopilot.py を使う。autopilot.py の check は light_rules の errors を呼ぶ。判定・文・順は変えない。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | 着手の commit を前、tip を後にして、指標の前後の比べ方を回し、輪を読む | 輪が 3 モジュールの 1 つで、light が入らない |
| R2 | 手元で実物 | tests/test_import_layers.py で autopilot.py が import する scripts のモジュールを読み、autopilot.py を `light` で grep する | autopilot.py の import 先に light が無く、grep が 0 件（文字列の中の語を除く） |
| R3 | 手元で実物 | 移した先のモジュールの import を読み、指標の前後の比べ方で LCOM4 を読む | stages.py と deploy.py のほかに scripts を import せず、LCOM4 が 2 以下 |
| R4 | 手元で実物 | 回帰テストと足したテストを回し、着手の commit と tip で同じ spec に `light.py approve` と CLI の check・lint・done を一時の SPEC_AUTOPILOT_HOME で回して出力を突き合わせ、指標の前後の比べ方を回す。全量は PR の CI で回す | 回帰テストと足したテストが通り、出力が同じ（時刻・パスを除く）で、autopilot.py の LCOM4 と fan-out を除いて悪化 0、「移しただけ」と出ず、除いた値の前と後が証拠にあり、マージの前に CI の全量が通る |

## 制約
- 予算: 45 分
- 大きさ: M
- playbook: なし（refactor の playbook は手元の plugin を更新するまで lint が読めない）
- 親 spec: 2026-11-28-metrics-refactor-goal
- 親の要件: R4、R5
- 想定する脅威: なし（hook と判定の結果を変えない。保護 path の判定の置き場だけを変えるので、test_light.py の回帰テストで守る）

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
- 合意した要件を満たす方法が無いと分かったとき（park に積む。どの要件も進められないときだけ block）
- 承認した自走の範囲の外の操作が要るとき（実行せずに park に積む）
- 指標の前後の比べ方で悪化が出て、直すと別の指標が悪化するとき（その要件を park に積み、朝の報告に書く）
