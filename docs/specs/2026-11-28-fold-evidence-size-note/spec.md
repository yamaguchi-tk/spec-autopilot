# evidence.py と size_note.py を autopilot.py に戻し、autopilot.py が import するモジュールを 16 から 14 に減らす

- ADR: docs/adr/2026-11-28-fold-evidence-size-note.md

## 目的
人の発言:「結合度　凝集度　複雑さ 等々の必要なソフトウェアメトリクスを指標にして欲しい」「リファクタの spec」「承認する」「次の子へ進む」。親の spec（2026-11-28-metrics-refactor-goal）の R4・R5 のうち、3 本目を受け持つ。

観測: 2 本目（2026-11-28-cycle-runlog）の後、輪は autopilot・goal・light・lineup・overnight の 5 つで残る。残りの 4 つが autopilot.py から借りるのは state.json の読み書き・セッションの記録・出力の補助で、輪を切るにはそれらを下の層の新しいモジュールに出すことになる。autopilot.py が import する scripts のモジュールは 16 で、新しいモジュールを 1 つ足すごとに増える。evidence.py（16 行）と size_note.py（23 行）は、autopilot.py の行の予算のために分けた小さい部品で、autopilot.py だけが使う。size_note.py は autopilot.py のモジュールごとを `sys.modules[__name__]` で受け、親の R4 が禁じる形になっている。

できあがったら、autopilot.py が import するモジュールは 14 になり、後の子が下の層のモジュールを足しても 16 を超えない余地が 2 つできる。size_note.py に渡していた `sys.modules[__name__]` の 2 か所は無くなる。

## 要件
- R1: plugins/spec-autopilot/scripts を測ったとき、autopilot.py の fan-out は 14 で、LCOM4 は 4 を超えず、指標の前後の比べ方（着手の commit を前にする）で悪化が無く、「移しただけ」と出ない。
- R2: plugins/spec-autopilot/scripts を読んだとき、evidence.py と size_note.py は無く、autopilot.py は `__import__("evidence")`・`__import__("size_note")` を持たず、`sys.modules[__name__]` を渡す呼び出しは premises と rootcause の 2 か所だけになる。
- R3: テストの全量が通り、`check --stage pr` と `done` の出力（大きさ L の NOTE を含む）と、qa.md の証拠の欄の区切り方の結果が、変える前と後で同じ spec に回して同じになる。テストは名前の向け先だけを変え、期待は変えない。

## 非目標
- goal・light・lineup・overnight を輪から出すこと（後の子で扱う）
- premises.py・rootcause.py が受ける `sys.modules[__name__]` を直すこと（後の子で扱う）
- playbooks.py などほかの小さい部品を戻すこと（凝集した部品で、autopilot.py の fan-out は 14 で足りる）
- 複雑度・凝集度を目標にすること（親の R2・R3 の子で扱う。悪化だけを止める）
- 挙動・CLI の出力・エラー文を変えること
- 版数を上げること

## 影響範囲
- 変える: plugins/spec-autopilot/scripts/autopilot.py（全体）
  - メモ: 749 の `__import__("evidence").items` と、954・973 の `__import__("size_note").notes(sys.modules[__name__], …)` を、autopilot.py の中の関数の呼び出しに替える
- 変える: plugins/spec-autopilot/scripts/evidence.py（全体）
  - メモ: items を autopilot.py に移し、ファイルを消す
- 変える: plugins/spec-autopilot/scripts/size_note.py（全体）
  - メモ: notes を autopilot.py に移し、ファイルを消す
- 呼び出し元: plugins/spec-autopilot/scripts/autopilot.py:749
  - メモ: evidence.py と size_note.py を使うのは autopilot.py だけ（ほかは 954・973）
- 手本: plugins/spec-autopilot/scripts/autopilot.py:795-802（report。autopilot.py の中のトップレベルの補助）
- 同じ入力: なし
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_advisor_approval.py plugins/spec-autopilot/tests/test_autopilot.py plugins/spec-autopilot/tests/test_goal_command.py plugins/spec-autopilot/tests/test_import_layers.py plugins/spec-autopilot/tests/test_overnight.py plugins/spec-autopilot/tests/test_qa_evidence.py plugins/spec-autopilot/tests/test_size.py plugins/spec-autopilot/tests/test_stages.py plugins/spec-autopilot/tests/test_stop_bounds.py -q -n auto
  - メモ: 大きさの NOTE・証拠の区切り・autopilot を直接 import するテストのファイル（`grep -lE 'size_note|SPLIT_PR|大きさが L|EVIDENCE_SEP|evidence_problem|import autopilot|autopilot as ap' plugins/spec-autopilot/tests/*.py`）と、import の層の test_import_layers。全量は PR の CI が回す（CLAUDE.md:5）

## 変えない挙動
- テストの全量: plugins/spec-autopilot/tests/
- 大きさ L の NOTE: plugins/spec-autopilot/tests/test_size.py
- 証拠の欄の読み方: plugins/spec-autopilot/tests/test_qa_evidence.py

## 前提
- 目的に届く: この子は輪を縮めない。後の子が state.json の読み書きなどを下の層に出すときに、autopilot.py の import 先が 16 を超えない余地を作る。輪を 0 にするのは後の子
- 運用: 指標は repo の外の測る道具（refactor-metrics の skill）で測る。評価役は、手元の道具で着手の commit と tip を比べる
- 普通のやり方: 1 か所からしか使わない小さい部品は、使う側に置く（モジュールの境は、使う側が複数あるか、役が独立しているところで切る）
  - メモ: この spec の ADR
- 過去: evidence.py は ba3a0e3、size_note.py は 2b6595d で、autopilot.py の行の予算のために分けた。autopilot.py は今 1,322 行で、2 つを戻しても 1,400 行に届かない
  - メモ: `git log --oneline -1 ba3a0e3`・`git log --oneline -1 2b6595d`・`wc -l plugins/spec-autopilot/scripts/autopilot.py`（1322）
- 前提: autopilot.py が import する scripts のモジュールは 16 で、evidence と size_note はその中にある
  - コマンド: `for m in $(ls plugins/spec-autopilot/scripts/*.py | xargs -n1 basename | sed 's/\.py$//'); do grep -qE "^\s*(import|from) $m\b|__import__\(\"$m\"\)|^\s*import .*\b$m\b" plugins/spec-autopilot/scripts/autopilot.py && echo $m; done` → 16 行（evidence と size_note を含む）
- 前提: evidence.py と size_note.py は、scripts・hooks・tests のどこからも autopilot.py のほかに import されていない
  - コマンド: `grep -rnE 'import (evidence|size_note)|__import__\("(evidence|size_note)"\)' plugins/spec-autopilot` → autopilot.py の 749・954・973 の 3 行だけ
- 前提: size_note.py の notes は、autopilot.py のモジュールを引数に受け、stated_size・COMMENT_BLOCK・section・is_new_repo・counted_size・SPLIT_PR をそこから読む
  - path: plugins/spec-autopilot/scripts/size_note.py:7（ほかに 12・16・18・22）
- 前提: evidence.py の items は、区切りの正規表現を引数 sep で受け、autopilot.py は EVIDENCE_SEP を渡す
  - path: plugins/spec-autopilot/scripts/evidence.py:4（呼ぶ側は autopilot.py:749、EVIDENCE_SEP は autopilot.py:106）

## 作り方
この spec の ADR のとおり、evidence.py の items と size_note.py の notes を、autopilot.py のトップレベルの関数として移す（名前は autopilot.py の中で重ならないものにする）。notes は autopilot.py のモジュールを引数に受けず、同じモジュールの名前を直接使う。items は区切りの正規表現を引数に受けず、EVIDENCE_SEP を直接使う。中身の判定・文・順は変えない。2 つのファイルは消し、呼ぶ側の `__import__` を関数の呼び出しに替える。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | 着手の commit を前、tip を後にして、指標の前後の比べ方を回し、autopilot.py の fan-out と LCOM4 を読む | fan-out が 14、LCOM4 が 4 以下、悪化 0、「移しただけ」と出ない |
| R2 | 手元で実物 | scripts の一覧を読み、autopilot.py を `__import__\("(evidence|size_note)"\)` と `sys.modules\[__name__\]` で grep する | 2 つのファイルが無く、`__import__` が 0 件、`sys.modules[__name__]` が premises と rootcause の 2 行だけ |
| R3 | 手元で実物 | 回帰テストと足したテストを回し、着手の commit と tip の写しで、大きさが L の spec と M の spec に `check --stage pr` と `done` を一時の SPEC_AUTOPILOT_HOME で回し、証拠の欄の例を区切らせて突き合わせる。全量は PR の CI で回す | 回帰テストと足したテストが通り、出力（時刻を除く）と区切りの結果が同じで、マージの前に CI の全量が通る |

## 制約
- 予算: 45 分
- 大きさ: M
- playbook: なし（refactor の playbook は手元の plugin を更新するまで lint が読めない）
- 親 spec: 2026-11-28-metrics-refactor-goal
- 親の要件: R4、R5
- 想定する脅威: なし（hook と判定の結果を変えない。関数の置き場だけを変えるので、回帰テストで守る）

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
