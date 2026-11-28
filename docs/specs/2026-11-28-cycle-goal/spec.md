# goal.py を autopilot.py から外し、import の輪を 5 モジュールから 4 モジュールに縮める

- ADR: docs/adr/2026-11-28-cycle-goal.md

## 目的
人の発言:「結合度　凝集度　複雑さ 等々の必要なソフトウェアメトリクスを指標にして欲しい」「リファクタの spec」「承認する」「次の子へ進む」「次の子へ進む」「親の基準を緩める」「承認する」。親の spec（2026-11-28-metrics-refactor-goal）の R4・R5 のうち、4 本目を受け持つ。

観測: 3 本目（2026-11-28-fold-evidence-size-note）と main の後、輪は autopilot・goal・light・lineup・overnight の 5 つで残る。goal.py が autopilot.py から借りるのは、state.json の読み書き（load_state・save_state）、出力（report・refuse）、セッションの記録（release）と、stages.py にもう有る名前（COMMENT_BLOCK・REQ・repo_root・section）だけ。補助を下の層に出すと autopilot.py の LCOM4 と fan-out は上がるが、親の R5 のただし書きで R4 の子では悪化に数えない。

できあがったら、goal.py は autopilot.py を import せず、輪は autopilot・light・lineup・overnight の 4 つに縮む。

## 要件
- R1: plugins/spec-autopilot/scripts を測ったとき、goal.py は import の輪に入らず、輪は autopilot.py・light.py・lineup.py・overnight.py の 4 つの 1 つだけになる。
- R2: goal.py を読んだとき、autopilot を import する文（関数の中の import と `__import__` を含む）と `autopilot.<名前>`・`ap.<名前>` の参照を持たず、輪を `importlib`・変数で名前を渡す `__import__`・`sys.modules` に替えて道具に見えなくする形も無い（文字列の中の `autopilot` の語は数えない）。
- R3: 測ったとき、load_state・save_state・report・refuse・AFTER_DONE・session_file・recorded_specs・release を置く下の層のモジュールは、scripts のモジュールを stages.py のほかに import せず、どれも LCOM4 が 2 以下になる。
- R4: テストの全量が通り、CLI の goal・lint・check・status・done・block の出力と、done・block が runs.jsonl に書く行を、変える前と後で同じ spec に回した出力が同じで、指標の前後の比べ方（着手の commit を前にする）で、親の R5 のただし書きの autopilot.py の LCOM4 と fan-out を除いて悪化が無く、「移しただけ」と出ない。除いた 2 つの値は前と後を証拠に書く。テストは名前の向け先だけを変え、期待は変えない（tests/test_import_layers.py の輪と import 先の数の期待は、親の R5 のとおり新しい値に直す）。

## 非目標
- light・lineup・overnight・watch・hooks を autopilot.py から外すこと（後の子で扱う。それらは移した名前を autopilot.py を通して使い続ける）
- premises.py・rootcause.py が受ける `sys.modules[__name__]` を直すこと（後の子で扱う）
- record_spec・take_over など、goal.py が使わないセッションの補助を移すこと
- 複雑度・凝集度を目標にすること（親の R2・R3 の子で扱う）
- 挙動・CLI の出力・エラー文・runs.jsonl の行を変えること
- 版数を上げること

## 影響範囲
- 変える: plugins/spec-autopilot/scripts/autopilot.py（全体）
  - メモ: 115 の load_state・119 の save_state・291 の session_file・299 の recorded_specs・326 の release・834 の report・1143 の AFTER_DONE・1148 の refuse を下の層に移し、45 の stages の import の近くで、そこから import して使う
- 変える: plugins/spec-autopilot/scripts/goal.py（全体）
  - メモ: 21 の `import autopilot as ap` を、下の層のモジュールと stages の import に替え、`ap.` の 21 か所を向け直す
- 新規: plugins/spec-autopilot/scripts/state.py
  - メモ: load_state・save_state
- 新規: plugins/spec-autopilot/scripts/out.py
  - メモ: report・refuse・AFTER_DONE
- 新規: plugins/spec-autopilot/scripts/session.py
  - メモ: session_file・recorded_specs・release。SESSION_ID は stages.py から import する
- 変える: plugins/spec-autopilot/tests/test_import_layers.py（全体）
  - メモ: 輪の期待を 4 つに、autopilot.py の import 先の数の期待を 18 に直し、R2・R3 のテストを足す
- 呼び出し元: plugins/spec-autopilot/scripts/lineup.py:53
  - メモ: ap.recorded_specs・ap.load_state を使う。lineup.py は変えない（ほかに light.py・overnight.py・watch.py・hooks の agent_gate.py・session_start.py・stop.py が autopilot.<名前> で使い続ける）
- 手本: plugins/spec-autopilot/scripts/runlog.py:1-20（stages だけを import する小さいモジュール）
- 同じ入力: なし
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_advisor_approval.py plugins/spec-autopilot/tests/test_agent_gate.py plugins/spec-autopilot/tests/test_autopilot.py plugins/spec-autopilot/tests/test_carry.py plugins/spec-autopilot/tests/test_consent.py plugins/spec-autopilot/tests/test_consent_adr.py plugins/spec-autopilot/tests/test_deploy_failure.py plugins/spec-autopilot/tests/test_goal.py plugins/spec-autopilot/tests/test_goal_child.py plugins/spec-autopilot/tests/test_goal_command.py plugins/spec-autopilot/tests/test_goal_done.py plugins/spec-autopilot/tests/test_goal_merged.py plugins/spec-autopilot/tests/test_import_layers.py plugins/spec-autopilot/tests/test_init_models.py plugins/spec-autopilot/tests/test_input_kinds.py plugins/spec-autopilot/tests/test_ladder.py plugins/spec-autopilot/tests/test_ladder_setup.py plugins/spec-autopilot/tests/test_light.py plugins/spec-autopilot/tests/test_lineup.py plugins/spec-autopilot/tests/test_merge_qa.py plugins/spec-autopilot/tests/test_overnight.py plugins/spec-autopilot/tests/test_prototype_gate.py plugins/spec-autopilot/tests/test_qa_evidence.py plugins/spec-autopilot/tests/test_rollback.py plugins/spec-autopilot/tests/test_rootcause.py plugins/spec-autopilot/tests/test_size.py plugins/spec-autopilot/tests/test_stages.py plugins/spec-autopilot/tests/test_stop_bounds.py -q -n auto
  - メモ: 移す名前・goal・autopilot を直接 import するテストのファイル（`grep -lE 'load_state|save_state|refuse|release|session_file|recorded_specs|AFTER_DONE|\bgoal\b|import autopilot|autopilot as ap' plugins/spec-autopilot/tests/*.py`）。全量は PR の CI が回す（CLAUDE.md:5）

## 変えない挙動
- テストの全量: plugins/spec-autopilot/tests/
- 目的の spec の goal の判定: plugins/spec-autopilot/tests/test_goal_command.py
- セッションの記録: plugins/spec-autopilot/tests/test_autopilot.py
- runs.jsonl の記録: plugins/spec-autopilot/tests/test_runlog.py

## 前提
- 目的に届く: 輪は 5 から 4 モジュールに縮むが、0 にはならない。残りの light・lineup・overnight と、premises・rootcause の `sys.modules[__name__]` と hooks は、後の子で向け直す。この子の間は、移した名前をほかのモジュールが autopilot.py を通して使い続ける（親の作り方の子 2 のとおり、出し直しの 0 件は R4 の最後の子で判定する）
- 運用: 指標は repo の外の測る道具（refactor-metrics の skill）で測る。評価役は、手元の道具で着手の commit と tip を比べる
- 普通のやり方: import の輪は、共通の部分を役ごとの下の層に出し、依存の向きを 1 つにそろえて切る
  - メモ: 親の spec の普通のやり方の項と、この spec の ADR
- 過去: 前の 3 本は、新しいモジュールを足すと autopilot.py の fan-out が上がるので、stages.py に寄せるか部品を畳んだ。補助を stages.py に寄せると stages.py の LCOM4（2）が上がって悪化になり、1 つのモジュールにまとめると LCOM4 が 4 以上になるので、親の R5 にただし書きを足して役ごとの 3 つに出す
  - メモ: docs/adr/2026-11-28-fold-evidence-size-note.md と親の spec の R5
- 前提: 今の輪は autopilot・goal・light・lineup・overnight の 5 つで、autopilot.py の fan-out は 15・LCOM4 は 4、goal.py の fan-out は 4・LCOM4 は 2、stages.py の LCOM4 は 2
  - コマンド: `uv run --with lizard python <refactor-metrics の skill>/scripts/measure.py plugins/spec-autopilot/scripts --json` → 上の値（main の e665307 を取り込んだ 0ae5330 で測った）
- 前提: goal.py が autopilot から使う名前は load_state・save_state・report・refuse・release・COMMENT_BLOCK・REQ・repo_root・section の 9 つで、後ろの 4 つと SESSION_ID は stages.py にある
  - コマンド: `grep -o "ap\.[A-Za-z_]*" plugins/spec-autopilot/scripts/goal.py | sort -u` → 上の 9 つ
  - path: plugins/spec-autopilot/scripts/autopilot.py:46（stages から import する名前の並び）
- 前提: release は session_file と recorded_specs を呼び、session_file は SESSION_ID を使う。load_state と save_state、report と refuse・AFTER_DONE は、互いに呼び合わないか 1 つだけでつながる
  - path: plugins/spec-autopilot/scripts/autopilot.py:326（release。session_file は 291、recorded_specs は 299、refuse は 1148）
- 前提: 3 つに分けて移すと、輪は autopilot・light・lineup・overnight の 4 つになり、新しいモジュールの LCOM4 は state.py 2・out.py 2・session.py 1、goal.py の fan-out は 7・LCOM4 は 2、autopilot.py の fan-out は 18・LCOM4 は 8
  - 未確認: main の 0ae5330 の写しで移して道具で測った値で、repo の中では確かめられない

## 作り方
この spec の ADR のとおり、load_state・save_state を state.py に、report・refuse・AFTER_DONE を out.py に、session_file・recorded_specs・release を session.py に、中身を変えずに移す（session.py は SESSION_ID を stages.py から import する）。autopilot.py は 3 つから名前を import して、今の名前のまま使う（ほかのモジュールが autopilot.<名前> で使うのは、この子では向け直さない）。goal.py は autopilot を import せず、state・out・session・stages を import し、`ap.` の参照をそれぞれのモジュールの名前に替える。判定・文・順は変えない。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | 着手の commit を前、tip を後にして、指標の前後の比べ方を回し、輪を読む | 輪が 4 モジュールの 1 つで、goal が入らない |
| R2 | 手元で実物 | goal.py を `import autopilot`・`autopilot\.[A-Za-z_]`・`ap\.[A-Za-z_]`・`importlib`・`sys.modules` と、変数を渡す `__import__` で grep する | grep が 0 件（文字列の中の語と、名前を文字列で渡す `__import__("runlog")` は除く） |
| R3 | 手元で実物 | 移した先のモジュールの import を読み、指標の前後の比べ方で、それぞれの LCOM4 を読む | stages.py のほかに scripts を import せず、どれも LCOM4 が 2 以下 |
| R4 | 手元で実物 | 回帰テストと足したテストを回し、着手の commit と tip で同じ spec に CLI の goal・lint・check・status・done・block を一時の SPEC_AUTOPILOT_HOME で回して出力と runs.jsonl の行を突き合わせ、指標の前後の比べ方を回す。全量は PR の CI で回す | 回帰テストと足したテストが通り、出力と行が同じ（時刻・パスを除く）で、autopilot.py の LCOM4 と fan-out を除いて悪化 0、「移しただけ」と出ず、除いた値の前と後が証拠にあり、マージの前に CI の全量が通る |

## 制約
- 予算: 45 分
- 大きさ: M
- playbook: なし（refactor の playbook は手元の plugin を更新するまで lint が読めない）
- 親 spec: 2026-11-28-metrics-refactor-goal
- 親の要件: R4、R5
- 想定する脅威: なし（hook と判定の結果を変えない。関数の置き場と import 先だけを変えるので、回帰テストで守る）

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
