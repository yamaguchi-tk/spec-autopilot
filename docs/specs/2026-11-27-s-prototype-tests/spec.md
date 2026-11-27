# 大きさ S の試作のテストを要件ごとに代表の数件にする

- ADR: docs/adr/2026-11-27-s-prototype-tests.md

## 目的
人の言葉:「10分で終わらないのは時間かかりすぎ」「autopilot自体の改善か、試走のプロンプトの改善をして」。

観測した失敗は、ハンズオンの試走（2026-11-27、main と実装役は Sonnet 5.5、新しい repo）である。依頼文を「シンプル」「基本の操作だけでよい」に絞った版で、本体 342 行に対してテストが 789 行あり、送信から試作が示されるまで 10 分 41 秒かかった。絞らない版では、本体 837 行に対してテストが 1,238 行で、実装役の最初の応答（テストを書く）が 47,326 output tokens、実装が 19,991 tokens だった。

できあがったら、S の試作のテストは要件ごとに代表の数件になり、試作の出力の量が減る。

2 本に分けた spec の 2 本目である。1 本目（s-prototype-size）は、S の草案を本体 200 行に収め、収まらない草案を照合役が止める。

## 要件
- R1: autopilot-implementer が大きさ S の spec を実装するとき、実装役はテストを要件ごとに代表の 1〜2 件にし、要件に書かれた境界の値・表の値はその数件の期待値に入れる。直しを頼まれたときの再現テスト、playbook のタスクが求めるテスト（bug-fix の落ちる再現のテストなど）、同時の書き込みのテストは代表の数に数えず、今のまま書く。大きさが S でない spec のテストの書き方は変えない。
- R2: 梯子の段の実装役（autopilot-implementer-opus・autopilot-implementer-opus-xhigh・autopilot-implementer-fable）も、R1 と同じテストの書き方をする。
- R3: plugins/spec-autopilot/.claude-plugin/plugin.json の version を 0.1.15 から 0.1.16 に上げ、版数のテストが 0.1.15 を超えたことを確かめ、.claude-plugin/marketplace.json の description は plugin.json と同じに保つ。

## 非目標
- M 以上の spec のテストの数を絞ること
- 試作の実装役が目安を超えたら途中で止める門
- 起動から試作までの 10 分の実測を、この spec の QA で行うこと（入れ子の Claude Code の対話と権限の確認が要る。マージの後に、ハンズオンの手順書の試走で測る）

## 影響範囲
- 変える: plugins/spec-autopilot/agents/autopilot-implementer.md（全体）
  - メモ: 12 行目の 2（TDD）の項
- 変える: plugins/spec-autopilot/agents/autopilot-implementer-opus.md（全体）
- 変える: plugins/spec-autopilot/agents/autopilot-implementer-opus-xhigh.md（全体）
- 変える: plugins/spec-autopilot/agents/autopilot-implementer-fable.md（全体）
  - メモ: 梯子の段の実装役の本文は、既定の実装役と同じに保つ（tests/test_ladder.py が本文の一致を確かめる）
- 変える: plugins/spec-autopilot/.claude-plugin/plugin.json（全体）
  - メモ: version の行だけ
- 変える: plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py:68-70（test_version_is_raised_past_0_1_14）
  - メモ: 版数のテストを、0.1.15 を超えたことを見るものに置き換える（repo の CLAUDE.md の版数の規則）
- 呼び出し元: plugins/spec-autopilot/commands/autopilot.md:90
  - メモ: C の 2 が実装役を起動する。S の試作は references/small-prototype.md が起動する
- 手本: plugins/spec-autopilot/agents/autopilot-implementer.md:12（2 の項の、計測を括弧に添える書き方）
- 同じ入力: なし
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_ladder.py plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py -q
  - メモ: 実装役の本文は test_ladder.py が段ごとの一致を、版数は test_spec_autopilot_wiring.py が確かめる。文書の語の有無を見るテストは repo の規則で書かない

## 変えない挙動
- 梯子の段ごとに agent があり、本文が同じ: plugins/spec-autopilot/tests/test_ladder.py::test_every_rung_has_an_agent_with_the_declared_model_and_the_same_body
- marketplace の description が plugin.json と同じ: plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py::test_marketplace_entry_matches_manifest

## 前提
- 目的に届く: 届くのは試作のテストの量まで。待ちが 10 分に収まるかは、1 本目の spec の草案の直しと合わせて、マージの後の試走でしか分からない
- 運用: /autopilot の main が試作と C の 2 で実装役を起動する（今の手順のまま）。変更が効くのは、マージの後に、人が plugin の checkout を pull してから（repo の CLAUDE.md の規則。pull は自走の範囲に入れない）
- 普通のやり方: なし（試作のテストの数の、決まった作り方は無い）
- 過去: docs/specs/2026-11-26-version-0-1-14（版数を上げ、版数のテストを置き換えた前例）
- 前提: 実装役は全要件のテストを先にまとめて書き、テストの数の上限は無い
  - path: plugins/spec-autopilot/agents/autopilot-implementer.md:12
- 前提: 梯子の段の実装役の本文は、既定の実装役と同じでなければならない
  - path: plugins/spec-autopilot/tests/test_ladder.py:199-211
- 前提: 版数のテストは 0.1.14 を超えたかだけを見る
  - path: plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py:68-70

## 作り方
この spec の ADR のとおり、実装役の 2 の項に、大きさ S のときのテストの数を 1 文足し、梯子の段の 3 ファイルに同じ文を写す。版数を 0.1.16 に上げ、版数のテストを 0.1.15 を超えたことを見るものに置き換える。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | 変えた autopilot-implementer.md の 2 の項を読む | 大きさ S のときだけテストを要件ごとに代表の 1〜2 件にし、境界の値・表の値を期待値に入れ、再現テスト・playbook のテスト・同時の書き込みのテストを数に数えないと書かれ、S でないときの書き方が今のまま |
| R2 | 手元で実物 | 回帰テストの test_ladder.py を回し、4 ファイルの 2 の項を読み比べる | テストが通り、4 ファイルの 2 の項が同じ |
| R3 | 手元で実物 | plugin.json の version を読み、回帰テストのコマンドを回す | version が 0.1.16 で、版数のテストが 0.1.15 を超えたことを見て、テストが通る |

## 制約
- 予算: 30 分
- 大きさ: M
- playbook: feature
- 依る spec: 2026-11-27-s-prototype-size
- 脅威: なし（agent の文と版数の変更で、hook と判定のコードは変えない）

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
