# 新しく作る repo の M でも、実装役 1 本・代表のテストで書く

- ADR: docs/adr/2026-11-27-new-repo-m-one-implementer.md

## 目的
人の言葉:「10分で終わらないのは時間かかりすぎ」。どの時点を 10 分にしたいかを聞くと「触れるまで」。そのうえで「A+Bで進めて」「テストを絞ってもいい」。

観測した失敗は、0.1.16 でのハンズオンの試走（2026-11-27、Sonnet 5.5、新しい repo、ブラウザのテトリス）である。照合役の項目 11 が本体を約 290 行と見積もり、大きさが M に回った。M では試作が無く、実装役が T1（2 分 35 秒）と T2（4 分 32 秒）に分かれた。実装役が書いた約 82,000 字のうち、本体は約 16,000 字、テストは約 54,000 字、自前のブラウザ検査スクリプト（chrome-check.mjs）は約 12,000 字だった。触れる状態になったのは送信の約 13 分後だが、「遊べます」の行が出ず、人が触れてよいと分かったのは done の 23 分 48 秒後だった。

S の試作とテストの絞り方は、大きさ S にだけ効く。1 画面のゲームは本体が 300 行を超えて M に落ちるので、前の 2 本の直しはこの試走に効かなかった。

できあがったら、新しく作る repo の M では、実装役が 1 本で全要件を書き、テストは要件ごとに代表の数件になり、ブラウザの確かめは評価役に任せる。

2 本に分けた spec の 1 本目である。2 本目（handoff-playable-line）は、handoff が「遊べます」の行を促し、版数を上げ、マージの前に試走して触れるまでの時間を測る。

## 要件
- R1: autopilot-implementer が、大きさ S の spec か、新しく作る repo の大きさ M の spec を実装するとき、テストは要件ごとに代表の 1〜2 件にし、要件に書かれた境界の値・表の値はその数件の期待値に入れる。直しを頼まれたときの再現テスト、playbook のタスクが求めるテスト、同時の書き込みのテストは数に数えない。既存の repo の M 以上の spec のテストの書き方は変えない。
- R2: autopilot-implementer は、どの大きさでも、ヘッドレスのブラウザを動かす自前の検査スクリプトを書かない（ブラウザの確かめは評価役が行う）。spec の QA の方向性が repo に足すよう求める E2E のテストは、この数に入れずに書く。
- R3: 梯子の段の実装役（autopilot-implementer-opus・autopilot-implementer-opus-xhigh・autopilot-implementer-fable）も、R1・R2 と同じ書き方をする。
- R4: /autopilot の main は、新しく作る repo の M の spec でも、tasks.md に全要件を受け持つタスクを 1 つだけ書き（playbook のタスクがあれば、今のとおり先頭に残す）、実装役 1 本に全要件を書かせる。QA の方向性は、新しく作る repo の M でも、S と同じく E2E のテストを repo に足さず、ロジックの単体テストと評価役のブラウザの操作を証拠にする。

## 非目標
- 大きさ M でも承認の前に試作を作ること（autopilot.md の「承認の前にコードを書かない」の例外を広げる。2 本目の実測が 10 分を超えたら、数字を添えて人に戻す）
- handoff の出力と版数（2 本目で行う）
- 範囲の確認を草案の前に別の往復で出すこと
- 草案の前の WebSearch と照合の直しを削ること
- 既存の repo の M 以上の spec のテストの数と、タスクの分け方
- 照合役の項目 11 の目安（150 行）を変えること

## 影響範囲
- 変える: plugins/spec-autopilot/agents/autopilot-implementer.md（全体）
  - メモ: 12 行目の 2（TDD）の項
- 変える: plugins/spec-autopilot/agents/autopilot-implementer-opus.md（全体）
- 変える: plugins/spec-autopilot/agents/autopilot-implementer-opus-xhigh.md（全体）
- 変える: plugins/spec-autopilot/agents/autopilot-implementer-fable.md（全体）
  - メモ: 梯子の段の実装役の本文は、既定の実装役と同じに保つ
- 変える: plugins/spec-autopilot/commands/autopilot.md（全体）
  - メモ: 53 行目の大きさの表の M の行、66 行目の B の 1 の E2E の文、89〜91 行目の C の 1・2
- 呼び出し元: plugins/spec-autopilot/references/small-prototype.md:7
  - メモ: S の試作は small-prototype.md が実装役を起動する。M は autopilot.md の C の 2 が起動する
- 手本: plugins/spec-autopilot/agents/autopilot-implementer.md:12（2 の項の、計測を括弧に添える書き方）
- 同じ入力: なし
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_ladder.py plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py plugins/spec-autopilot/tests/test_goal_command.py plugins/spec-autopilot/tests/test_advisor_approval.py plugins/spec-autopilot/tests/test_light.py -q -n auto
  - メモ: 実装役の本文は test_ladder.py が段ごとの一致を確かめる。autopilot.md は test_spec_autopilot_wiring.py・test_goal_command.py・test_advisor_approval.py・test_light.py が読む。文書の語の有無を見るテストは repo の規則で書かない

## 変えない挙動
- 梯子の段ごとに agent があり、本文が同じ: plugins/spec-autopilot/tests/test_ladder.py::test_every_rung_has_an_agent_with_the_declared_model_and_the_same_body

## 前提
- 目的に届く: 縮むのは実装の約 7 分の側だけで、草案の約 4 分と人の OK は変わらない。触れる時点を知らせる行と実測は 2 本目で行うので、この spec だけでは 10 分に届いたかは分からない
- 運用: /autopilot の main が C の 1・2 で tasks.md を書き、実装役を起動する。変更が効くのは、マージの後に、人が plugin の checkout を pull してから（repo の CLAUDE.md の規則）
- 普通のやり方: なし（agent の出力の量で待ちを縮める、決まった作り方は無い）
- 過去: docs/specs/2026-11-27-s-prototype-tests（S だけテストを絞り、M 以上を非目標にした。この spec の ADR でその退け方を新しく作る repo の M に限って改める）
- 前提: 実装役のテストの絞り方は、大きさ S にだけ効く
  - path: plugins/spec-autopilot/agents/autopilot-implementer.md:12
- 前提: M はタスクごとに実装役を起動する
  - path: plugins/spec-autopilot/commands/autopilot.md:53、plugins/spec-autopilot/commands/autopilot.md:90
- 前提: init は新しく作る repo かを、spec のディレクトリの state.json の existing に記録する（実装役は spec のディレクトリを渡され、Read で読める）
  - path: plugins/spec-autopilot/scripts/autopilot.py:893-897、plugins/spec-autopilot/agents/autopilot-implementer.md:9
- 前提: playbook のタスクは tasks.md の先頭に写し、消さずに残す（bug-fix は T1〜T3 を持つ）
  - path: plugins/spec-autopilot/commands/autopilot.md:89、plugins/spec-autopilot/references/playbooks/bug-fix.md:16-20
- 前提: 梯子の段の実装役の本文は、既定の実装役と同じでなければならない
  - path: plugins/spec-autopilot/tests/test_ladder.py:199-211

## 作り方
この spec の ADR のとおり、実装役の 2 の項のテストの絞り方の条件を「S か、新しく作る repo（spec のディレクトリの state.json の `existing` が false）の M」に広げ、自前のブラウザ検査スクリプトを書かない文を足し、梯子の段の 3 ファイルに同じ文を写す。commands/autopilot.md の大きさの表（M の行）・B の 1（QA の方向性の E2E）・C の 1・2（計画と実装）に、新しく作る repo の M の扱いを書く。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | 変えた autopilot-implementer.md の 2 の項を base と比べて読む | 絞る条件が「S か、state.json の existing が false の M」になり、既存の repo の M 以上の書き方が今のまま |
| R2 | 手元で実物 | 変えた autopilot-implementer.md を読む | 自前のヘッドレスのブラウザの検査スクリプトを書かないと書かれ、spec が求める E2E は書くと書かれている |
| R3 | 手元で実物 | 回帰テストの test_ladder.py を回し、4 ファイルの本文を読み比べる | テストが通り、4 ファイルの本文が同じ |
| R4 | 手元で実物 | 変えた autopilot.md の :53・:66・C の 1・2 を base と比べて読む | 新しく作る repo の M で、タスク 1 つ・実装役 1 本・E2E を足さないことが書かれ、既存の repo の M の書き方が今のまま |

## 制約
- 予算: 30 分
- 大きさ: M
- playbook: feature
- 脅威: なし（agent と command の文だけを変え、hook と判定のコードは変えない）

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
