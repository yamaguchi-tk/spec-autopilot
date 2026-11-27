# main が価値観で案を選び、人に問う範囲を事実・1 操作ごとの許可・目的の変更に絞る

- ADR: docs/adr/2026-11-28-values-driven-main.md

## 目的
人の発言:「人に問う必要がある内容はかなり少ないと思う」「人の代わりのFableだったりでいけるのでは」「そもそも価値観を入れているが選ばない選択肢が出てきたりする」「価値観に合わない選択肢はいみがない」「main自体も価値観に合わせて動いて欲しい」。

観測: 2026-11-28 の夜、目的の spec の子を 3 本マージした後、03:19 に R3 の子（親の要件を狭める点）を人に問うて turn を終え、08:14 に人が返すまで約 5 時間止まった。出した選択肢のうち「狭めて承認する」は価値観に合わず、人の答えは「直して出し直す」で、相談役でも同じ答えに届いた見込み（runs.jsonl と元のセッションの transcript で確かめた）。

できあがったら、main は価値観に合う案だけを作って選び、人に問うのは事実・1 操作ごとの許可・目的の変更だけになる。夜の間に価値観から答えが出る問いで止まらない。

## 要件
- R1: main が案（作り方・直し方・人に戻るときの選択肢）を作るとき、`commands/autopilot.md` と SessionStart の相談役の規則は、先に価値観（repo と利用者の CLAUDE.md の設計原則、spec・ADR の人の決定、目的・非目標）を読ませ、価値観に反する案を選択肢に並べさせず、退けた理由を 1 行だけ残させ、案の数をそろえるために案を作らせない。
- R2: 価値観で残る案が 1 つのとき、`commands/autopilot.md` と SessionStart の相談役の規則は、問わずにその案で進ませ、理由を残させる。
- R3: main が人に問うのは、(a) 答えを人しか持たない事実、(b) 利用者の規則が 1 操作ごとに求める操作の許可、(c) 目的を変える決定（要件を落とす・狭める・非目標を広げる）だけであると、`commands/autopilot.md` と SessionStart の相談役の規則は書く。それ以外の迷いは、main が価値観で選んだ案と相談役の推奨が同じで、検証役が反証なしとしたら問わずに進み、違うか反証ありなら、自走中は当たる要件だけを止めて他を続け、自走していないときは食い違いを添えて人に問う。
- R4: SessionStart の相談役の規則、`agents/fable-advisor.md`、`plugins/spec-autopilot/README.md` は、相談役を、main の代わりに選ぶ役ではなく、main が価値観で選んだ案が人の選びと同じかを確かめる役として書く。

## 非目標
- 相談役の 2 段（fable-advisor → advice-checker → 反証ありの直し 1 回）の段の数と、承認し直しの `--by-advisor` の判定を変えること
- hook で人への問いを機械的に止めること
- advice-checker・opus-advisor の定義を変えること
- 版数を上げること（マージの後に版数だけの PR で上げる）
- ADR の `- 退けた:`（直し方の段）の行の形と rootcause.py の判定を変えること（価値観で退けた案は別の行 `- 価値観で退けた:` に書き、rootcause.py は読まない）

## 影響範囲
- 変える: plugins/spec-autopilot/commands/autopilot.md（全体）
  - メモ: A の 4（61 行）、A の 2（問いの範囲）、B の 3 の相談役（75 行。相談役は main の案を見ずに推奨を出し、main が自分の案と比べる形に直す）、C の冒頭（85 行）、「人に戻るとき」（150 行）。見出しは変えない。目的の spec の子の承認（57 行）と承認し直し（152-158 行）の 2 段の手順は変えない
- 変える: plugins/spec-autopilot/hooks/session_start.py:27-43（ADVISE）
- 変える: plugins/spec-autopilot/agents/fable-advisor.md（全体）
  - メモ: 本文の 24 行と 38 行の役の文。frontmatter の description の「ユーザーならどの案を選ぶかの代わり」も同じに直す
- 変える: plugins/spec-autopilot/README.md（全体）
  - メモ: 43 行の相談役の役の文
- 変える: plugins/spec-autopilot/tests/test_autopilot.py（全体）
  - メモ: ADVISE が問う範囲の 3 つと、main が選んだ案を確かめる役を出すテストを足す
- 呼び出し元: plugins/spec-autopilot/hooks/session_start.py:81-87
- 手本: plugins/spec-autopilot/tests/test_autopilot.py:1660-1690
- 別の実装: plugins/spec-autopilot/scripts/rootcause.py:11
  - メモ: ADR の `- 退けた:` を段の名前で読む。価値観で退けた案は `- 価値観で退けた:` の行にして、この判定に当てない
- 同じ入力: なし
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_autopilot.py plugins/spec-autopilot/tests/test_advisor_approval.py plugins/spec-autopilot/tests/test_rootcause.py plugins/spec-autopilot/tests/test_consent_adr.py plugins/spec-autopilot/tests/test_goal_command.py plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py -q -n auto

## 変えない挙動
- SessionStart は spec の無い repo でも相談役の規則を出す: plugins/spec-autopilot/tests/test_autopilot.py::test_session_start_gives_the_advisor_rule_outside_any_spec
- 相談役の規則は名指しする 3 つの agent が plugin にある: plugins/spec-autopilot/tests/test_autopilot.py::test_session_start_gives_only_the_advisor_rule_without_active_specs
- fable-advisor の `承認: 可` の書式をコードが読む: plugins/spec-autopilot/tests/test_advisor_approval.py

## 前提
- 目的に届く: 手順と規則の文で main の振る舞いを決めるので、main が文に従わない場合は防げない（hook で問いを止めるのは非目標）。夜の 5 時間の停止は、問いが (c) に当たらず相談役の推奨と同じなら起きない
- 運用: main が /autopilot の手順と SessionStart の規則を読んで従う。食い違いで park に積んだ要件は朝の報告に出る
- 普通のやり方: なし（この plugin に固有の、人の代わりの相談役の手順で、外の慣習が無い）
- 過去: 相談役の 2 段（fable-advisor → advice-checker）は、人に返事を求める前に推奨を検証するために入った。相談役の価値観の節（依頼を縮めない・人の介在を最小にする）はすでにあり、main 側には価値観を読む手順が無い（git log -- plugins/spec-autopilot/hooks/session_start.py で確かめた）
- 前提: A の 4 は案を 2〜3 個挙げることを求めている
  - path: plugins/spec-autopilot/commands/autopilot.md:61
- 前提: ADVISE は SessionStart のたびに全セッションに出る
  - path: plugins/spec-autopilot/hooks/session_start.py:81-87
- 前提: rootcause.py は `- 退けた:` を直し方の段の名前で始まる行だけ読み、ほかの見出しの行は読まない
  - path: plugins/spec-autopilot/scripts/rootcause.py:11
- 前提: park は要件ごとに積み、積んでいない要件は進む（自走中に当たる要件だけを止める手段）
  - path: plugins/spec-autopilot/scripts/overnight.py:690
- 前提: 自走中かどうかは、spec の phase が building でこのセッションが引き受けたかで見分ける（SessionStart が状態の行で知らせる）
  - path: plugins/spec-autopilot/hooks/session_start.py:21-22
- 前提: ADVISE の末尾は repo の規則の別の相談の規定を優先させる。問う範囲の 3 つもこの優先の下に置く（repo が別に定めたらそちらに従う）
  - path: plugins/spec-autopilot/hooks/session_start.py:43
- 前提: fable-advisor は、ユーザーならどの案を選ぶかの代わりを役にしている
  - path: plugins/spec-autopilot/agents/fable-advisor.md:38

## 作り方
この spec の ADR のとおり。価値観で退けた案は ADR の `- 価値観で退けた: <案>（<当たる価値観>）` の行かタスクのメモに 1 行残す。(c) は、要件の数・範囲・合格の条件・非目標のどれかが承認時より狭まるか広がるかで見分ける。自走中の食い違いは park に積む。相談役には材料の場所だけを先に渡して推奨を出させ、main は自分の案をその後に並べて比べる（main の案を見て寄らないように）。autopilot.md の A の 4・A の 2・C の冒頭・人に戻るときを直し、ADVISE の文を「main が価値観で選ぶ → 相談役が同じかを確かめる → 同じで反証なしなら進む」に直し、問う範囲を 3 つと書く。fable-advisor.md の役の文を直す。ADVISE のテストを足す。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | 評価役が commands/autopilot.md の A の 4 と「人に戻るとき」を読み、2026-11-28 の夜の問い（狭めて承認する・直して出し直す）に当てる | 価値観を先に読む手順、反する案を並べず退けた行に残す手順、数合わせをしない文がある。夜の場面で「狭めて承認する」は選択肢に並ばない |
| R2 | 手元で実物 | 評価役が commands/autopilot.md を読む | 残る案が 1 つなら問わずに進み、理由を ADR かメモに残す文がある |
| R3 | 手元で実物 | SessionStart の hook を一時の repo で回して出力を読み、autopilot.md と突き合わせる | ADVISE と autopilot.md が問う範囲を (a)(b)(c) の 3 つと書き、それ以外は相談役と同じで反証なしなら進み、違えば自走中は park・自走していないときは人に問うと書く。両者が食い違わない |
| R4 | 手元で実物 | SessionStart の hook の出力と agents/fable-advisor.md を読む | 相談役を main の選んだ案を確かめる役として書き、main の案を見る前に推奨を決めさせる。既存のテストが全部通る |

## 制約
- 予算: 60 分
- 大きさ: M
- playbook: feature
- 想定する脅威: main が (c) に当たる決定（要件を狭める）を (a)(b)(c) の外と読み、相談役と同じだとして人に問わずに進むこと

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
