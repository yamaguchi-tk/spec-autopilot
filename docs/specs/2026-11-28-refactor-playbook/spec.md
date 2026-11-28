# /autopilot の playbook に refactor を足し、リファクタの spec が指標の前後で合否を書くようにする

- ADR: docs/adr/2026-11-28-refactor-playbook.md

## 目的
人の発言:「行数以外のソフトウェアメトリクスでは？」「結合度　凝集度　複雑さ 等々の必要なソフトウェアメトリクスを指標にして欲しい」「リファクタの spec」「承認する」。親の spec（2026-11-28-metrics-refactor-goal）の R1 を受け持つ。

観測: 前のリファクタ（2026-11-26-split-modules）は `- playbook: なし` で書かれ、合格基準は行数だけで、指標で測ると移しただけだった。今の playbook は feature・bug-fix・iac・external-service の 4 つで、リファクタに当たるものが無い。できあがったら、リファクタの spec は refactor を選び、変える前の指標の値と、前後の比べ方の合格基準を書く。

## 要件
- R1: spec の「## 制約」に `- playbook: refactor` を書いて `CLI lint` を回したとき、lint は playbook の行を ERROR にしない。
- R2: references/playbooks/refactor.md を読んだとき、既存の playbook と同じ 3 節（spec を書くとき・自走のタスク・評価役の観点）があり、spec を書くときの節は、変える前の指標の値を測ったコマンドと結果で「## 前提」に書かせ、QA の方向性の合格基準を「指標の前後の比べ方で悪化が無く、狙った指標が目標の値に届き、移しただけでない」の形にさせ、評価役の観点の節は「移しただけで複雑さが変わっていないか」を見させ、測る道具の名前とパスを書かない。

## 非目標
- 測る道具を repo に入れること（道具は repo の外に置く）
- 指標の悪化で `CLI check` が止まる仕組み（親の ADR の選択肢 3。観測してから別の spec で決める）
- 既存の 4 つの playbook を直すこと
- 版数を上げること（マージの後に版数だけの PR で上げる）

## 影響範囲
- 新規: plugins/spec-autopilot/references/playbooks/refactor.md
- 変える: plugins/spec-autopilot/commands/autopilot.md（全体）
  - メモ: 37-40 の playbook の索引の表に refactor の行を 1 行足す
- 変える: plugins/spec-autopilot/tests/test_playbooks.py（全体）
  - メモ: 15-16 の期待するファイルの一覧に refactor を足し、31 の「ファイルの無い名前」の例の refactor を別の名前に替え、refactor を受ける例を足す
- 呼び出し元: plugins/spec-autopilot/scripts/playbooks.py:22
  - メモ: lint は DIR の `*.md` の一覧で名前を閉じるので、コードは変えない
- 手本: plugins/spec-autopilot/references/playbooks/bug-fix.md:1-25
- 同じ入力: DIR
  - メモ: playbooks.py が references/playbooks/ のファイル名を読む。この spec はファイルを 1 つ足すだけ
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_playbooks.py plugins/spec-autopilot/tests/test_autopilot.py plugins/spec-autopilot/tests/test_stages.py -q -n auto

## 変えない挙動
- 知っている名前となしの理由を受ける: plugins/spec-autopilot/tests/test_playbooks.py::test_lint_accepts_known_names_or_none_with_a_reason
- playbook の行が無ければ止める: plugins/spec-autopilot/tests/test_playbooks.py::test_lint_requires_the_playbook_line

## 前提
- 目的に届く: リファクタの spec を書く人と main が refactor を選べ、指標の前後で合否を書く。手元の plugin を人が更新するまで、この repo の自走の lint は refactor を知らない（親の spec の前提のとおり）
- 運用: リファクタの spec を書くとき、/autopilot の A の 0 で refactor を選んで読む。道具は書く人が自分で持つ
- 普通のやり方: なし（この plugin に固有の playbook の書式で、外の慣習が無い）
- 過去: 2026-11-26-split-modules は playbook を `なし（挙動を変えないリファクタで、feature・bug-fix・iac・external-service のどれにも当たらない）` と書いた
  - メモ: docs/specs/2026-11-26-split-modules/spec.md の制約の節
- 前提: lint は references/playbooks/ の `*.md` のファイル名で playbook の名前を閉じ、コードに名前を並べていない
  - path: plugins/spec-autopilot/scripts/playbooks.py:5（DIR）、plugins/spec-autopilot/scripts/playbooks.py:22（glob）
- 前提: テストは期待するファイルの一覧を 4 つで持ち、ファイルの無い名前の例に refactor を使っている
  - path: plugins/spec-autopilot/tests/test_playbooks.py:15-16、plugins/spec-autopilot/tests/test_playbooks.py:31
- 前提: 既存の playbook は「spec を書くとき」「自走のタスク」「評価役の観点」の 3 節で書かれている
  - path: plugins/spec-autopilot/references/playbooks/bug-fix.md:5（ほかに 14・22）

## 作り方
この spec の ADR のとおり、refactor.md を bug-fix.md と同じ 3 節で足し、索引の表と test_playbooks.py を直す。playbook は、測るコマンドを「指標を測る道具のコマンド」と一般の語で書き、道具の名前とパスを書かない（公開の repo で、plugin を入れたほかの人は手元の道具を持たない）。自走のタスクは、変える前を測って記録する・直す・後を測って前と比べる、の 3 つにする。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | test_playbooks.py を回し、一時の repo で `- playbook: refactor` の spec に `CLI lint` を回す | テストが通り、lint が playbook の行を ERROR にしない |
| R2 | 手元で実物 | refactor.md の見出しを grep し、本文を読み、道具の名前（lizard・measure.py・refactor-metrics）とパスを grep する | 3 節があり、前提・合格基準・観点の文が要件のとおりで、道具の名前とパスが 0 件 |

## 制約
- 予算: 45 分
- 大きさ: M
- playbook: なし（refactor の playbook はこの spec が作るので、まだ選べない）
- 親 spec: 2026-11-28-metrics-refactor-goal
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
- 合意した要件を満たす方法が無いと分かったとき（park に積む。どの要件も進められないときだけ block）
- 承認した自走の範囲の外の操作が要るとき（実行せずに park に積む）
