# spec を分けるときは目的の spec を既定にすると書き、版数を上げる

- ADR: docs/adr/2026-11-28-fewer-reapprovals.md

## 目的
目的の spec（docs/specs/2026-11-28-fewer-reapprovals）の R7〜R8 を受け持つ。人の発言（11/25）:「spec が複数に分かれてそれぞれ毎に承認する形式も無駄」。

観測した失敗: spec を分けるとき、commands/autopilot.md は分けた spec を「まとめて承認（B の 5）」へ導き、目的の spec（`--goal`）をいつ選ぶかの基準が無い。11/26 に目的の spec が入った後も、使われたのは 3〜4 回だった。できあがったら、spec を分けるときの人の承認が既定で 1 回になる。

## 要件
- R1: L の依頼で spec を分けるとき、/autopilot の手順は目的の spec（`--goal`、人の承認 1 回）を既定にし、まとめて承認（B の 5）は人が子の spec を全部見てから承認したいと言ったときだけ選ぶと読め、まとめて承認の項と食い違わない。
- R2: plugins/spec-autopilot/.claude-plugin/plugin.json の version を上げ、`.claude-plugin/marketplace.json` の description は plugin.json と同じに保つ。

## 非目標
- 目的の spec の CLI の挙動を変えること
- 昼の承認し直しを相談役 2 本で通すこと

## 影響範囲
- 変える: plugins/spec-autopilot/commands/autopilot.md（全体）
  - メモ: 56〜57 行目（大きさの L と目的の spec）、77〜78 行目（承認の返事とまとめて承認）
- 変える: plugins/spec-autopilot/.claude-plugin/plugin.json（全体）
  - メモ: version の行だけ
- 変える: plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py（全体）
  - メモ: 版数のテストの前の版の値だけ
- 別の実装: plugins/spec-autopilot/tests/test_goal_command.py:18-36
  - メモ: 目的の spec の項の見出しの行を 1 行だけ探し、その行の CLI の呼び出しを argparse で通す。見出しの語を変えない
- 呼び出し元: なし
- 同じ入力: version、description
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py plugins/spec-autopilot/tests/test_goal_command.py -q -n auto

## 変えない挙動
- marketplace の description は plugin.json と同じ: plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py
- 目的の spec の手順の CLI の呼び出しは argparse で通る: plugins/spec-autopilot/tests/test_goal_command.py

## 前提
- 目的に届く: 届くのは、spec を分けるときの既定の承認を 1 回にするところまで。人が子を全部見たいときは今までどおりまとめて承認を使う
- 運用: main は A の 3 で L の依頼を受けたら、目的の spec を草案にして人に示す。新しい版は、plugin を使う手元の checkout を人が pull したときに効く
- 普通のやり方: repo の CLAUDE.md の版数の決まり（版数は機能の PR のマージの後に、版数だけを上げる PR で上げる）。この spec は機能の PR ではなく、人が親の R8 で版数を上げると承認した子なので、文書の直しと版数を同じ PR にする
- 過去: 11/26 に目的の spec（`--goal`）が入ったが、A の 3 の文は分けた spec をまとめて承認へ導いたまま
- 前提: 目的の spec（`--goal`）は人の承認 1 回で、子を相談役 2 本で承認して夜の間に回す
  - path: plugins/spec-autopilot/commands/autopilot.md:57
- 前提: 版数は plugin.json の version にあり、テストが marketplace.json の description と突き合わせる
  - path: plugins/spec-autopilot/.claude-plugin/plugin.json:3

## 作り方
A の 3 の L の項の「分けた spec は、まとめて承認して（B の 5）」の文を、目的の spec を既定にし、まとめて承認は人が子を全部見てから承認したいと言ったときだけにする文に直す。B の 5 のまとめて承認の項にも、選ぶときの条件を 1 文で合わせる。置き場は commands/autopilot.md の A の 3 の L の項と B の 5 のまとめて承認の項で、plugins/spec-autopilot/README.md に同じ選び方の記述があれば合わせる。版数はパッチを 1 つ上げる（CLAUDE.md の版数の決まりとの違いは、前提の普通のやり方の行に書いた）。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | commands/autopilot.md の差分を読み、A の 3 の目的の spec とまとめて承認の記述を突き合わせる | 選ぶ基準が書かれ、既定が目的の spec で、B の 5 の記述と食い違わない |
| R2 | 手元で実物 | `python3 -m pytest plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py -q` | 版数が前の版を超え、marketplace の description が plugin.json と同じでテストが通る |

## 制約
- 予算: 90 分
- 大きさ: M
- playbook: feature
- 親 spec: 2026-11-28-fewer-reapprovals
- 親の要件: R7、R8
- 依る spec: 2026-11-28-lint-origin
- 想定する脅威: なし（文書と版数だけ）

## モデル

## 自走の範囲
- 範囲: マージまで
- QA の環境: 手元の一時 repo（git init した作業ディレクトリ）
- QA の書き込み先: 手元の一時 repo と spec のディレクトリの evidence だけ
- デプロイの起動:
- デプロイの確かめ:
- ロールバック: revert の PR をマージし、デプロイの完了を確かめる
- 通知: デスクトップ
- AWS の profile: なし

## 止まる条件
- 合意した要件のどれかを満たす方法が無いと分かったとき（その要件だけを park に積み、ほかを進める。どの要件も進められないときだけ block）
- 承認した自走の範囲の外の操作が要るとき（実行せずに park に積む）
