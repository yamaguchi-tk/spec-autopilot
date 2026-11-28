# 相談役は承認の門と名指し・IaC の初回だけに回し、ほかは main の案を検証役に直接当てる

- ADR: docs/adr/2026-11-28-fewer-advisor-calls.md

## 目的
人の発言:「毎回相談役に確認するのもコストアップと時間効率の悪化の要因になっていそう」「相談役が不要なのであれば外したい」「必要なケースを洗い出したい」。

観測: 2026-11-14〜11-28 の transcript で相談 569 件・約 3,162 分。1 段目の推奨が main の案を変えた証拠は 0 件。効いたのは、検証役が repo の事実（path:行）との食い違いを見つけた件と、子の承認の `承認: 否` だけ（判定できた 192 件中 101 件）。検証役が path:行 を引かなかった 3 件は全部反証なし。2026-11-28 未明の目的の spec の子の承認では、子ごとに相談役と検証役を順に回し、子 5 では計 5 本・約 7 分、可・反証なしで終わった。commands/autopilot.md にも、承認前の相談の決着に 38 分かかった事例が載っている。

できあがったら、相談役は効いていた場面（承認の門）と人の名指し・IaC の初回だけで回り、ほかの迷いでは検証役を多くて 1 本、repo の事実に当てる主張があるときだけ回す。

## 要件
- R1: SessionStart の相談役の規則と commands/autopilot.md は、1 段目の相談役（fable-advisor、名指しのときは opus-advisor）を回す場面を、目的の spec の子の承認、block の後の承認し直し、人が相談役を名指ししたとき、IaC の初回の apply を含む spec の 4 つだけと書く。
- R2: 価値観で残る案が 2 つ以上のとき・人に戻るときの選択肢・レビュー指摘の直し方では、SessionStart の相談役の規則と commands/autopilot.md は、main が価値観で選んだ案を、根拠に repo の事実（path:行・コード・引いた決定）があるときだけ検証役に 1 本で確かめさせ反証を探させ、無ければ回さずに進ませる。反証ありなら、自走中は当たる要件を park に積み、自走していないときは反証を添えて人に問わせる。
- R3: 価値観で案が 1 つに絞れたとき、SessionStart の相談役の規則と commands/autopilot.md は、相談役も検証役も回さずに進ませる。
- R4: agents/advice-checker.md と plugins/spec-autopilot/README.md は、検証役が、1 段目の相談役の推奨だけでなく main の案も確かめると書く。
- R5: 目的の spec の子の承認（`approve --queue --by-advisor`）と承認し直し（`approve --by-advisor`）の判定は、今のまま相談役と検証役の 2 本の記録を求める。

## 非目標
- 承認の門（advisor_approval.py・goal.py の child_errors）の判定を変えること
- fable-advisor・opus-advisor の定義を消すこと
- GDD の plugin の相談の規定を変えること（repo の規則の別の相談の規定を優先する今の文は残す）
- 版数を上げること（マージの後に版数だけの PR で上げる）

## 影響範囲
- 変える: plugins/spec-autopilot/hooks/session_start.py:27-52（ADVISE）
- 変える: plugins/spec-autopilot/commands/autopilot.md（全体）
  - メモ: A の 2（44 行）、B の 3 の相談役（75 行）、C の冒頭（85 行）、人に戻るとき（150-152 行）。子の承認（57 行）と承認し直し（154-160 行）の 2 段の手順は変えない
- 変える: plugins/spec-autopilot/agents/advice-checker.md（全体）
- 変える: plugins/spec-autopilot/README.md（全体）
- 変える: plugins/spec-autopilot/tests/test_autopilot.py（全体）
- 呼び出し元: plugins/spec-autopilot/hooks/session_start.py:90-96
- 手本: plugins/spec-autopilot/tests/test_autopilot.py:1685-1707
- 同じ入力: なし
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_autopilot.py plugins/spec-autopilot/tests/test_advisor_approval.py plugins/spec-autopilot/tests/test_goal_child.py plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py plugins/spec-autopilot/tests/test_advisors.py plugins/spec-autopilot/tests/test_goal_command.py plugins/spec-autopilot/tests/test_lineup.py plugins/spec-autopilot/tests/test_watch.py -q -n auto

## 変えない挙動
- 子の承認は相談役 2 本の記録が要る: plugins/spec-autopilot/tests/test_goal_child.py::test_child_is_refused_when_an_advisor_condition_is_missing
- 承認し直しの門: plugins/spec-autopilot/tests/test_advisor_approval.py
- SessionStart は spec の無い repo でも相談役の規則を出す: plugins/spec-autopilot/tests/test_autopilot.py::test_session_start_gives_the_advisor_rule_outside_any_spec

## 前提
- 目的に届く: 規則と手順の文で main の起動を決めるので、main が文に従わない場合は防げない。1 段目が効かなかったというのは記録から効いた証拠が取れなかったという意味で、比べられたのは 3 件だけ
- 運用: main が SessionStart の規則と /autopilot の手順を読んで従う。承認の門は今のままスクリプトが検査する
- 普通のやり方: なし（この plugin に固有の、人の代わりの相談役の手順で、外の慣習が無い）
- 過去: PR #110 で、main が価値観で案を選び、相談役を確かめる役にした。残る案が複数なら毎回 2 段で回す文が残った（git log -- plugins/spec-autopilot/hooks/session_start.py で確かめた）
- 前提: ADVISE は、価値観で残る案が複数なら毎回 fable-advisor → advice-checker の 2 段で回させている
  - path: plugins/spec-autopilot/hooks/session_start.py:33-40
- 前提: 子の承認は goal.child_errors が advisor_approval.reply_errors で 2 本の記録を求める
  - path: plugins/spec-autopilot/scripts/goal.py:118-119
- 前提: advice-checker は 1 段目の推奨の欄を受け取る役として書かれている
  - path: plugins/spec-autopilot/agents/advice-checker.md:18-25
- 前提: B の 3 は IaC の初回の apply と名指しのときだけ相談役を回す
  - path: plugins/spec-autopilot/commands/autopilot.md:75

## 作り方
この spec の ADR のとおり。ADVISE を「価値観で 1 つ → 回さない／複数・選択肢・直し方 → main の案の根拠に repo の事実があれば advice-checker 1 本／承認の門・名指し・IaC の初回 → 今の 2 段」に書き直す。autopilot.md の A の 2・C の冒頭・人に戻るときを同じに直す。advice-checker.md の受け取る材料と README の表を直す。ADVISE のテスト（1685-1707 行）を新しい文に直す。R2 の検証は、main の案の `推奨:`・`理由:`・`引いた決定:` の欄を advice-checker に渡す形にする（advice-checker.md の受け取る材料もこの欄と書く）。ADVISE には、承認の門・名指し・IaC の初回で使う「1 段目→2 段目→反証ありの直し 1 回」の文を残し、autopilot.md の 154・158 行が名指しする「2 段の相談」「2 段目」の指し先を保つ。ADVISE には 3 つの agent の名前を残す（test_autopilot.py:1665）。fable-advisor・opus-advisor の description は「規則か手順が名指ししたときに起動する」と書いていて、場面を決めるのは規則の側なので、今回は直さない（大きさを M に収めるため。場面の例の文の直しは別の PR）。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | SessionStart の hook を一時の repo で回して出力を読み、autopilot.md と突き合わせる | 1 段目を回す場面が 4 つだけと書かれ、両者が食い違わない |
| R2 | 手元で実物 | 同じ出力と autopilot.md を読み、価値観で 2 案残るレビュー指摘の直し方の場面に当てる | main の案を advice-checker に 1 本だけ渡し、repo の事実が無ければ回さない。反証ありの扱いが自走中は park・自走していないときは人に問う |
| R3 | 手元で実物 | 同じ出力と autopilot.md を読む | 案が 1 つなら相談役も検証役も回さない文がある |
| R4 | 手元で実物 | agents/advice-checker.md と README.md を読む | 検証役が main の案も確かめると書かれ、新しい案を出さない役は変わらない |
| R5 | 手元で実物 | test_goal_child.py と test_advisor_approval.py を回す | 全部通る。advisor_approval.py・goal.py に差分が無い |

## 制約
- 予算: 60 分
- 大きさ: M
- playbook: feature
- 想定する脅威: main が承認の門でない場面を門でないと読み替え、repo の事実を根拠に持つ案でも検証役を回さずに進むこと

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
