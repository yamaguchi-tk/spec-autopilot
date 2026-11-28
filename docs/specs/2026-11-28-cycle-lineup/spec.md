# lineup.py の名前を下の層と autopilot.py に分けて出し、autopilot.py が lineup.py を import しないようにする

- ADR: docs/adr/2026-11-28-cycle-lineup.md

## 目的
人の発言:「結合度　凝集度　複雑さ 等々の必要なソフトウェアメトリクスを指標にして欲しい」「リファクタの spec」「承認する」「次の子へ進む」「次の子へ進む」「親の基準を緩める」「承認する」「入り口として扱うとどうなる？」「入口として扱う」「承認する」。親の spec（2026-11-28-metrics-refactor-goal）の R4・R5 のうち、6 本目を受け持つ。

観測: 5 本目（2026-11-28-cycle-light）の後、輪は autopilot・lineup・overnight の 3 つで残る。autopilot.py は lineup.py の after_name・queue_lint・enqueue・begin を呼ぶ（autopilot.py:505・535・887-912）。after_name と begin は autopilot.py のうち stages.py の名前と sha だけを使い、queue_lint と enqueue は autopilot.py の lint・take_over などを使う。

できあがったら、autopilot.py は lineup.py を import せず、lineup.py は autopilot.py の上に立つ入口になる。輪は overnight.py が lineup.after_name を呼ぶ 1 か所（overnight.py:325）で残り、overnight の子で外す。

## 要件
- R1: autopilot.py を読んだとき、lineup を import する文（関数の中の import と、名前を文字列で渡す `__import__` を含む）が無い。lineup の呼び出しを `importlib`・変数で名前を渡す `__import__`・`sys.modules` に替えて道具に見えなくした形も無い（autopilot.py に今ある入口の dispatch の `__import__(a.cmd)` と、premises・rootcause に渡す `sys.modules[__name__]` は後の子で扱う）。
- R2: plugins/spec-autopilot/scripts を測ったとき、輪は autopilot.py・lineup.py・overnight.py の 3 つの 1 つだけで、autopilot.py から lineup.py への import が無い。
- R3: 測ったとき、lineup.py から出した名前を置く下の層のモジュールは、scripts のモジュールを lineup・overnight・autopilot・light から import せず、どれも LCOM4 が 2 以下になる。
- R4: テストの全量が通り、CLI の approve（--queue と、依る spec のある spec を含む）・lint・check・done と `lineup.py next`・`light.py approve` の出力を、変える前と後で同じ spec に回した出力が同じで、指標の前後の比べ方（着手の commit を前にする）で、親の R5 のただし書きの autopilot.py の LCOM4 と fan-out を除いて悪化が無く、「移しただけ」と出ない。除いた 2 つの値は前と後を証拠に書く。テストは名前の向け先だけを変え、期待は変えない（tests/test_import_layers.py の輪と import 先の数の期待は、親の R5 のとおり新しい値に直す）。

## 非目標
- overnight.py を輪から出すことと、overnight.py:325 の lineup.after_name を向け直すこと（overnight の子で扱う）
- lineup.py・light.py の、autopilot.py の名前を使う呼び出しを向け直すこと（入口は autopilot.py に依ってよい）
- premises.py・rootcause.py が受ける `sys.modules[__name__]` と、autopilot.py 経由の出し直しを直すこと（後の子で扱う）
- 複雑度・凝集度を目標にすること（親の R2・R3 の子で扱う）
- 挙動・CLI の出力・エラー文を変えること
- 版数を上げること

## 影響範囲
- 変える: plugins/spec-autopilot/scripts/lineup.py（全体）
  - メモ: after_name・AFTER・NEXT・pairs_file・pairs・remember を after.py に、begin を building.py に移す。queue_lint・enqueue・minutes・session_of を autopilot.py に移す。lineup.py は移した名前を after・building から import して、今の名前のまま使う
- 変える: plugins/spec-autopilot/scripts/autopilot.py（全体）
  - メモ: 505・535・887-912 の lineup の呼び出しを、after・building の名前と、移した queue_lint・enqueue に替える。head_and_body・sha を building.py に移し、autopilot.py は import して使う
- 新規: plugins/spec-autopilot/scripts/after.py
  - メモ: 依る spec の名前の読み取りと、後の spec と依る spec の対の記録（repo の外のファイル）
- 新規: plugins/spec-autopilot/scripts/building.py
  - メモ: 承認の対象のハッシュ（head_and_body・sha）と、承認した spec を自走中にする begin
- 変える: plugins/spec-autopilot/tests/test_import_layers.py（全体）
  - メモ: autopilot.py の import 先の数の期待を直し、R1〜R3 のテストを足す
- 呼び出し元: plugins/spec-autopilot/scripts/light.py:41
  - メモ: lineup.after_name と lineup.begin（57）を呼ぶ。lineup.py が移した名前を import するので、light.py は変えない
- 手本: plugins/spec-autopilot/scripts/light_rules.py:1-20（入口から出した、stages と deploy だけを import する下の層のモジュール。前の子で足した）
- 同じ入力: なし
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_advisor_approval.py plugins/spec-autopilot/tests/test_agent_gate.py plugins/spec-autopilot/tests/test_anomalies.py plugins/spec-autopilot/tests/test_autopilot.py plugins/spec-autopilot/tests/test_carry.py plugins/spec-autopilot/tests/test_consent.py plugins/spec-autopilot/tests/test_consent_adr.py plugins/spec-autopilot/tests/test_deploy_failure.py plugins/spec-autopilot/tests/test_goal.py plugins/spec-autopilot/tests/test_goal_child.py plugins/spec-autopilot/tests/test_goal_command.py plugins/spec-autopilot/tests/test_goal_done.py plugins/spec-autopilot/tests/test_import_layers.py plugins/spec-autopilot/tests/test_ladder.py plugins/spec-autopilot/tests/test_light.py plugins/spec-autopilot/tests/test_lineup.py plugins/spec-autopilot/tests/test_main_progress.py plugins/spec-autopilot/tests/test_merge_qa.py plugins/spec-autopilot/tests/test_overnight.py plugins/spec-autopilot/tests/test_prototype_gate.py plugins/spec-autopilot/tests/test_qa_evidence.py plugins/spec-autopilot/tests/test_rollback.py plugins/spec-autopilot/tests/test_rootcause.py plugins/spec-autopilot/tests/test_runlog.py plugins/spec-autopilot/tests/test_size.py plugins/spec-autopilot/tests/test_spec_command.py plugins/spec-autopilot/tests/test_stages.py plugins/spec-autopilot/tests/test_stop_bounds.py plugins/spec-autopilot/tests/test_watch.py -q -n auto
  - メモ: lineup・light・approve を回すテストと、autopilot を直接 import するテストのファイル（`grep -lE '\blineup\b|\blight\b|import autopilot|autopilot as ap|approve' plugins/spec-autopilot/tests/*.py`）。全量は PR の CI が回す（CLAUDE.md:5）

## 変えない挙動
- テストの全量: plugins/spec-autopilot/tests/
- まとめて承認と着手の順・依る spec の載せ替え: plugins/spec-autopilot/tests/test_lineup.py
- 軽量フローの承認: plugins/spec-autopilot/tests/test_light.py

## 前提
- 目的に届く: autopilot.py から lineup.py への import は無くなるが、overnight.py:325 が lineup.after_name を呼ぶので、輪のモジュールは 3 つのまま残る。overnight の子で 325 を after.py に向け直すと、lineup は輪から出る
- 運用: 指標は repo の外の測る道具（refactor-metrics の skill）で測る。評価役は、手元の道具で着手の commit と tip を比べる
- 普通のやり方: import の輪は、共通の部分を役ごとの下の層に出し、依存の向きを 1 つにそろえて切る。親の spec は、light・lineup・overnight を autopilot.py の上に立つ CLI の入口として扱い、承認の道で autopilot.py の lint・take_over を使う queue_lint・enqueue は autopilot.py に移すと決めた
  - メモ: 親の spec の作り方の子 2、この spec の ADR
- 過去: 5 本目は、light.py の判定を light_rules.py に出して autopilot.py が light を import しないようにした（PR 138）
  - メモ: docs/specs/2026-11-28-cycle-light/spec.md
- 前提: 今の輪は autopilot・lineup・overnight の 3 つで、autopilot.py の fan-out は 18・LCOM4 は 8、lineup.py の fan-out は 5・LCOM4 は 1
  - コマンド: `uv run --with lizard python <refactor-metrics の skill>/scripts/measure.py plugins/spec-autopilot/scripts --json` → 上の値（main の 33058e5 の上で測った）
- 前提: autopilot.py が lineup.py を使うのは、after_name（505・535・890）・queue_lint（889）・enqueue（911）・begin（912）で、import は 505・535 の `__import__("lineup")` と 887 の関数の中の import
  - コマンド: `grep -nE 'lineup' plugins/spec-autopilot/scripts/autopilot.py` → 505・535・887・889・890・891・911・912・985・1055・1256 の行（891・985・1055・1256 は文字列の中の語）
- 前提: after_name は stages の section・COMMENT_BLOCK だけを、begin は deploy・carry と stages の repo_root と autopilot.py の sha だけを使い、sha は head_and_body と consent の numberless と stages の section だけを使う
  - path: plugins/spec-autopilot/scripts/lineup.py:34（after_name。begin は 117-145）
  - path: plugins/spec-autopilot/scripts/autopilot.py:119（head_and_body。sha は 129-135）
- 前提: queue_lint・enqueue が使う lineup の補助は session_of・minutes・after_name・remember・NEXT で、remember は pairs_file・pairs を使い、lineup.py の released（196）と block（155）と demand（270・271）と hold（346）も pairs・NEXT を使う
  - コマンド: `grep -nE 'session_of|minutes\(|remember\(|pairs\(|pairs_file|NEXT' plugins/spec-autopilot/scripts/lineup.py` → 上の行
- 前提: テストは lineup.remember・lineup.pairs を読む（test_lineup.py:479・486）ので、lineup.py が after から import し直せば変えずに通る
  - path: plugins/spec-autopilot/tests/test_lineup.py:479（remember を別のプロセスで呼ぶ）
- 前提: lineup.py の fan-out は、begin の carry が building に移り、after・building が増えて 5 から 6 に上がる（deploy は cmd_hold、runlog は block が使い続ける）。指標の道具は、後の値が警告の目安（fan-out 10）を超え、かつ前より大きいときだけ悪化に数えるので、6 は悪化にならない
  - path: plugins/spec-autopilot/scripts/lineup.py:332（cmd_hold の deploy。block の runlog は 158）
  - コマンド: `grep -n THRESHOLDS <refactor-metrics の skill>/scripts/measure.py` → fan_out の目安は (10, 15)
- 前提: after.py の LCOM4 は 2（after_name と、pairs_file・pairs・remember の 2 つの塊）、building.py の LCOM4 は 1（begin が sha を呼び、sha が head_and_body を呼ぶ）、autopilot.py の fan-out は lineup が after・building に替わって 19
  - 未確認: 移した後に道具で測る値で、着手の前の repo の中では確かめられない

## 作り方
この spec の ADR のとおり、lineup.py の after_name・AFTER・NEXT・pairs_file・pairs・remember を after.py に、autopilot.py の head_and_body・sha と lineup.py の begin を building.py に、中身を変えずに移す（`ap.` の名前は stages・consent から import して直接使い、関数の中の `import deploy`・`__import__("carry")` は先頭の import にする）。lineup.py の queue_lint・enqueue・minutes・session_of は autopilot.py に移す（minutes は autopilot.py の done の中の同じ名前の変数と紛れないよう queue_minutes にする）。lineup.py と autopilot.py は移した名前を import して今の名前のまま使う。判定・文・順は変えない。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | tests/test_import_layers.py で autopilot.py が import する scripts のモジュールを読み、autopilot.py を `\blineup\b` で grep する | autopilot.py の import 先に lineup が無く、grep の当たりが文字列の中の語だけ |
| R2 | 手元で実物 | 着手の commit を前、tip を後にして、指標の前後の比べ方を回し、輪を読む | 輪が 3 モジュールの 1 つで、autopilot.py から lineup.py への import が無い |
| R3 | 手元で実物 | 移した先のモジュールの import を読み、指標の前後の比べ方で LCOM4 を読む | after.py・building.py が lineup・overnight・autopilot・light を import せず、LCOM4 がどれも 2 以下 |
| R4 | 手元で実物 | 回帰テストと足したテストを回し、着手の commit と tip で同じ spec に approve（--queue と依る spec のある spec）・lint・check・done と `lineup.py next`・`light.py approve` を一時の SPEC_AUTOPILOT_HOME で回して出力を突き合わせ、指標の前後の比べ方を回す。全量は PR の CI で回す | 回帰テストと足したテストが通り、出力が同じ（時刻・パスを除く）で、autopilot.py の LCOM4 と fan-out を除いて悪化 0、「移しただけ」と出ず、除いた値の前と後が証拠にあり、マージの前に CI の全量が通る |

- 目的の確かめ: R1

## 制約
- 予算: 60 分
- 大きさ: M
- playbook: なし（refactor の playbook は手元の plugin を更新するまで lint が読めない）
- 親 spec: 2026-11-28-metrics-refactor-goal
- 親の要件: R4、R5
- 想定する脅威: なし（hook と判定の結果を変えない。承認と着手の置き場だけを変えるので、test_lineup.py と test_light.py の回帰テストで守る）

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
