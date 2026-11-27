# 評価役の定義（梯子の段を含む 3 つ）は、自分で起こした処理を kill・pkill でなく TaskStop で止める

- ADR: docs/adr/2026-11-28-denial-stop-reviewers.md

## 目的
人の発言:「まとめて承認」「spec（5 案）もOK」「夜なのでできるだけ確認せずに自走して欲しい」。親の spec（2026-11-27-flow-review-goal）の R2 のうち、評価役の定義の分を受け持つ。

観測: split-modules の夜の run で、実装役・評価役は `pkill`・`kill` で 8 件拒まれた。できあがったら、評価役は自分で起こした処理を TaskStop で止められ、定義にそう書かれている。

## 要件
- R1: 評価役の定義（autopilot-reviewer・autopilot-reviewer-xhigh・autopilot-reviewer-fable の 3 つ）は、front matter の tools に TaskStop を持ち、本文で、自分で起こした処理を `kill`・`pkill` で止めず TaskStop で止めることを指示する。

## 非目標
- 実装役の定義を直すこと（2026-11-28-denial-stop-implementers が受け持つ）
- main の指示（Stop hook の続けさせる文と /autopilot の手順）を直すこと（2026-11-28-denial-handling が受け持つ）
- 版数を上げること（この子の PR のマージの後に、版数だけの PR で patch を 1 つ上げる）

## 影響範囲
- 変える: plugins/spec-autopilot/agents/autopilot-reviewer.md（全体）
- 変える: plugins/spec-autopilot/agents/autopilot-reviewer-xhigh.md（全体）
- 変える: plugins/spec-autopilot/agents/autopilot-reviewer-fable.md（全体）
- 呼び出し元: なし
- 手本: plugins/spec-autopilot/tests/test_advisors.py:13-27
- 同じ入力: なし
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_advisors.py plugins/spec-autopilot/tests/test_agent_gate.py plugins/spec-autopilot/tests/test_ladder.py -q -n auto

## 変えない挙動
- 相談役の定義の tools は Read・Grep・Glob のまま: plugins/spec-autopilot/tests/test_advisors.py::test_agent_front_matter

## 前提
- 目的に届く: 定義の文と tools を直すだけで、kill を打つことを機械では止めない。拒否の件数が減ったかは、この後の run の集計で確かめる
- 運用: 評価役は起動のたびに定義を読み、自分で起こした処理を TaskStop で止める
- 普通のやり方: なし（この plugin の agent の定義で、外の慣習が無い）
- 過去: 親の spec（2026-11-27-flow-review-goal）が、split-modules の run の transcript から kill・pkill の拒否を 8 件数えた
- 前提: 評価役の定義の tools には TaskStop が無い
  - path: plugins/spec-autopilot/agents/autopilot-reviewer.md:6
  - path: plugins/spec-autopilot/agents/autopilot-reviewer-fable.md:6
- 前提: 評価役の定義の 3 の段は、`&`・`$!`・`run_in_background` で処理を裏に回さないと書いている（裏に回った処理を止める手順は無い）
  - path: plugins/spec-autopilot/agents/autopilot-reviewer.md:23

## 作り方
この spec の ADR のとおり。3 つの定義の front matter の tools に `TaskStop` を足し、本文の 3 の段（裏に回さない、と書いた段）の終わりに「自分で起こした処理を止めるときは `kill`・`pkill` を打たず（権限の自動判定が拒む）、TaskStop で止める」を 1 文足す。テストは、3 つの定義の front matter の tools に TaskStop があるか（host が読む値）を見る。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | 3 つの定義の front matter と本文を読む | 3 つとも tools に TaskStop があり、本文に kill・pkill でなく TaskStop で止める指示がある |

## 制約
- 予算: 30 分
- 大きさ: M
- playbook: feature
- 親 spec: 2026-11-27-flow-review-goal
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
- 合意した要件を満たす方法が無いと分かったとき（park に積む。どの要件も進められないときだけ block）
- 承認した自走の範囲の外の操作が要るとき（実行せずに park に積む）
