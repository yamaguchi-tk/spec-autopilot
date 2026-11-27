# 夜の自走で観測した 5 つの詰まりを、目的の spec 1 本と子 5 本で直す

- ADR: docs/adr/2026-11-27-flow-review-goal.md

## 目的
人の発言:「まとめて承認」。直前のセッション（split-modules を回したもの）で示した 5 つの見直しの案を、示した順のまま、まとめて回すことへの返事である。

観測した事実（2026-11-20〜27 の auto mode の拒否の集計と、split-modules の run）:
- 承認し直すと、前の巡の dispatch が数えられなくなる。実装がすでに HEAD に入っていると handoff が通らない。戻す手順（`git restore`）は auto mode に 4 件拒まれ、毎回人の手が要った
- 拒否された後、同じ目的で `git revert`・`git checkout` を打った（形を変えて試さない、という CLAUDE.md の規則に反する）。実装役・評価役は `pkill`/`kill` で 8 件拒まれた。`approve` の拒否 6 件は、どれも他のコマンドとつないで打ったものだった
- 評価役が返った後に state を commit すると、証拠の頭の `- commit:` が記録した巡の tip と合わず、check が止まった。違いは state.json の 1 行だけだった
- 「大きさが L になった」の NOTE は `done` だけが出す。範囲がマージ以上の spec では、done はマージの後なので、分けるかを決める段（PR を作る前）より後に出た
- 子の done の state はマージの後に子のブランチへ commit され、main に入らない。親の `goal` は、子のブランチの commit を取り込むまで子を done と読めなかった

できあがったら、承認し直しと評価の記録の 2 か所で人の手が要らなくなり、拒否された後の扱いが手順に書かれ、L の分け方と目的の spec の閉じ方が手順の順に合う。拒否の件数が減ったかは、この spec の後の run の集計で確かめる（この spec の合格基準には入れない）。

## 要件
- R1: blocked の spec を承認し直したとき、前の巡の最後の dispatch が handoff で閉じていて、spec の置き場（docs/specs と docs/adr）の外のファイルがその handoff の tip と今の HEAD で同じなら、spec の外を戻さず、実装役を起動せずに、評価役の巡を `CLI review` で記録できる。どちらかが成り立たなければ、今までどおり dispatch から始め、そうした理由を 1 行出す。
- R2: 自走中に権限の自動判定に操作を拒まれたとき、main が読む指示（Stop hook の続けさせる文と /autopilot の手順）は、同じ目的を別のコマンドで試さず、その操作を park か block に入れることを指示する。あわせて、実装役と評価役（梯子の段を含む全部の定義）は自分で起こした処理を `kill`・`pkill` ではなく TaskStop で止めること、main は `approve` と `gh pr merge` を他のコマンドとつながずに単独で打つことを指示する。
- R3: 手元で実物の要件の証拠の頭の `- commit:` が、評価役の巡の tip と違っても、その 2 つの間の差分が spec の置き場の中だけなら、`CLI check` はその証拠をその巡のものとして数える。
- R4: 申告か数えた大きさが L のとき、`CLI check --stage pr` は「大きさが L になった」の NOTE を出す。
- R5: 目的の spec の子が done になった後、その done の state.json が今の作業ツリーに無くても、子の PR がマージ済みと gh で確かめられれば、`CLI goal` はその子を done と読み、親の要件が全部 done の子で受け持たれていれば親を done にする。PR がマージ済みと確かめられない子の done は読まない。

## 非目標
- 子の承認で spec を直したとき、相談役と検証役のどちらか一方で済ませること（承認の門を緩める向きなので退けた）
- auto mode の分類器そのものを変えること、拒否の件数を数える道具を足すこと
- 承認し直しの `approve` の拒否 6 件の原因を言い切ること（件数が少なく、R2 の「単独で打つ」で様子を見る）
- 手元の checkout の pull（人が頼んだときに docs/pull-checkout.md で行う）
- 承認し直しの前に rebase などで spec の外のコードだけが変わり、実装役に直すものが無い場合の扱い（観測していない。今までどおり dispatch から始め、handoff が commit の無いことで止めたら block で人に戻る）

## 影響範囲
- 変える: plugins/spec-autopilot/scripts/carry.py:1-60（same_outside、why_not、plan）
- 変える: plugins/spec-autopilot/scripts/lineup.py:117-142（begin）
- 変える: plugins/spec-autopilot/hooks/stop.py:50-54（CONTINUE）
- 変える: plugins/spec-autopilot/commands/autopilot.md（全体）
  - メモ: 93（handoff の戻しの手順）、101-102（C の 4・5 の L の NOTE）、112・138（L の NOTE と自走の段の文）
- 変える: plugins/spec-autopilot/agents/autopilot-implementer.md（全体）
- 変える: plugins/spec-autopilot/agents/autopilot-implementer-opus.md（全体）
- 変える: plugins/spec-autopilot/agents/autopilot-implementer-opus-xhigh.md（全体）
- 変える: plugins/spec-autopilot/agents/autopilot-implementer-fable.md（全体）
- 変える: plugins/spec-autopilot/agents/autopilot-reviewer.md（全体）
- 変える: plugins/spec-autopilot/agents/autopilot-reviewer-xhigh.md（全体）
- 変える: plugins/spec-autopilot/agents/autopilot-reviewer-fable.md（全体）
- 変える: plugins/spec-autopilot/scripts/stages.py:104-116（same_commit、checked_in_review）
- 変える: plugins/spec-autopilot/scripts/autopilot.py:690-756（check）
- 変える: plugins/spec-autopilot/scripts/autopilot.py:1021-1047（cmd_done）
- 変える: plugins/spec-autopilot/scripts/goal.py:121-144（cover）
- 変える: plugins/spec-autopilot/references/after-pr.md:16-26（全体）
  - メモ: 16（gh pr merge）、21・26（done と state の commit）
- 呼び出し元: plugins/spec-autopilot/scripts/autopilot.py:993
- 呼び出し元: plugins/spec-autopilot/scripts/light.py:180
- 呼び出し元: plugins/spec-autopilot/scripts/lineup.py:235
- 呼び出し元: plugins/spec-autopilot/scripts/overnight.py:182-195
  - メモ: review_gate。closed_handoff（176-179）で最後の dispatch が閉じているかを見る。handoff（515-540）は dispatches・handoffs を読むだけ
- 呼び出し元: plugins/spec-autopilot/scripts/deploy.py:301-312
- 呼び出し元: plugins/spec-autopilot/scripts/autopilot.py:1016-1018
- 呼び出し元: plugins/spec-autopilot/scripts/goal.py:147-185
- 手本: plugins/spec-autopilot/scripts/carry.py:11-19
- 同じ入力: dispatches、handoffs、reviews、merges、goal
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_carry.py plugins/spec-autopilot/tests/test_lineup.py plugins/spec-autopilot/tests/test_overnight.py plugins/spec-autopilot/tests/test_stages.py plugins/spec-autopilot/tests/test_size.py plugins/spec-autopilot/tests/test_autopilot.py plugins/spec-autopilot/tests/test_goal.py plugins/spec-autopilot/tests/test_merge_qa.py plugins/spec-autopilot/tests/test_light.py plugins/spec-autopilot/tests/test_stop_bounds.py -q -n auto

## 変えない挙動
- 承認し直しでのマージとデプロイの記録の持ち越し（R1 は、前の巡の最後の dispatch が閉じていて spec の外が同じ場合だけ、test_carry.py の test_a_carried_round_counts_reviews_qa_and_dispatches_again の dispatch・handoff の 2 つの期待を書き換える。reviews・qa_runs・park などを数え直す期待は変えない）: plugins/spec-autopilot/tests/test_carry.py
- 承認の人の発言の門: plugins/spec-autopilot/tests/test_autopilot.py::test_approve_after_block_needs_new_user_prompt
- 目的の spec の承認と子の受け持ちの表: plugins/spec-autopilot/tests/test_goal.py
- マージ・デプロイ・QA の段の判定: plugins/spec-autopilot/tests/test_merge_qa.py

## 前提
- 目的に届く: 5 つとも、観測した詰まりをその場所で直す。R2 は文で指示するだけで、拒否された後に別の形を試すことを機械では止めない。`approve` の拒否の原因は分からないままで、R2 の後に件数が減るかで確かめる
- 運用: 直した後も /autopilot の手順は変わらず、承認し直し・評価の記録・PR の前の check・goal が人の手なしで通る。拒否されたら park か block に入れ、朝の報告で人が見る
- 普通のやり方: 拒否や失敗を、形を変えて試し直さず、既存の待ちの行列（park）に積んで人に渡すのは、この plugin が範囲の外の操作で既にしている扱いと同じ（hooks/stop.py の CONTINUE）
- 過去: 承認し直しの持ち越しは reapproval-carry-merge で入り、その spec の R3 が「実装役の dispatch と handoff は新しい巡で数え直す」と決めた。数え直すと、実装が HEAD にある巡では handoff が commit の無いことで止まり、戻す手順（`git restore`）が auto mode に拒まれる。R1 はこの決定を、最後の dispatch が閉じていて spec の外が同じ場合に限って覆す（理由はこの spec の ADR）
- 前提: approve（begin）は、前の phase が discovery でなければ、dispatches と handoffs を history に移して state から消す（承認の前の試作の dispatch だけを残す）
  - path: plugins/spec-autopilot/scripts/lineup.py:125-133
- 前提: handoff は dispatch の記録が無ければ拒み、開いている dispatch では base から commit が増えたかを数える
  - path: plugins/spec-autopilot/scripts/overnight.py:520-535
- 前提: check は手元で実物の証拠の `- commit:` を、巡の sha と文字列で比べる（git の中身では比べない）
  - path: plugins/spec-autopilot/scripts/stages.py:104-116
- 前提: L の NOTE（SPLIT_PR）を出すのは cmd_done だけで、check は大きさを数えない
  - path: plugins/spec-autopilot/scripts/autopilot.py:556
  - path: plugins/spec-autopilot/scripts/autopilot.py:1036-1047
- 前提: goal は、親と同じ置き場の子の state.json を今の作業ツリーから直に読む
  - path: plugins/spec-autopilot/scripts/goal.py:121-144
- 前提: 範囲がマージ以上の spec は、マージしてから done にし、done の state をその後に commit する
  - path: plugins/spec-autopilot/references/after-pr.md:21（範囲がマージまでのとき、マージの後に done）、plugins/spec-autopilot/references/after-pr.md:26（done の後に state を commit）
- 前提: 実装役と評価役の定義には、kill・pkill・TaskStop の記述が無い
  - コマンド: `grep -cE "\bkill|pkill|TaskStop" plugins/spec-autopilot/agents/*.md` → どのファイルも 0

## 作り方
この spec の ADR のとおり、目的の spec として 1 回承認し、要件ごとに子を 1 本ずつ、R1 → R2 → R3 → R4 → R5 の順に回す。子は main から順にブランチを切り、前の子のマージの後に着手する。子の承認は相談役と検証役の経路（`approve --queue --by-advisor`）で通す。

- 子 1（R1）: carry.py に、前の巡の最後の dispatch と、それを閉じた handoff の記録を持ち越す判定を足し、lineup.py の begin がそれを state に戻す（review_gate は閉じた handoff を見るので、記録を戻せば通る）。照合は carry.py の `same_outside` と同じ形で、比べる先はその handoff の tip にする。begin を呼ぶ 3 か所（approve・lineup next・軽量フローの approve）のうち、持ち越すのは前の phase が blocked のときだけ
- 子 2（R2）: stop.py の CONTINUE に拒否の扱いの文を足し、commands/autopilot.md の C の節と、実装役・評価役の定義（梯子の段の定義を含む）に 1〜2 行ずつ足す
- 子 3（R3）: stages.py の checked_in_review で、sha が一致しないときに、証拠の commit と巡の sha の間の差分が spec の置き場の中だけかを carry.py と同じ pathspec で見る
- 子 4（R4）: cmd_done の大きさの判定を関数に切り出し、check の stage が pr のときも呼ぶ。autopilot.py は 1391 行なので、増えるなら同じ子の中で別のファイルに移す
- 子 5（R5）: goal の読み方は子の spec で決める。候補は、PR がマージ済みの子の state を子のブランチから読む形と、done の state の commit をマージの前に回す形の 2 つ。どちらでも、PR がマージ済みと確かめられない子の done は読まない（未マージのブランチに書いた done を信じて親を閉じない）
- 各子は、利用者に届く挙動を変えるので、plugin.json の版数の patch を 1 つ上げる

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | 一時の git repo で spec を building → dispatch → handoff → blocked にし、spec の外を変えずに承認し直して review を記録する。spec の外を 1 行変えた場合と、最後の dispatch を閉じずに blocked にした場合も回す | 変えない場合は dispatch・実装役・戻しなしで review が記録でき、ほかの 2 つの場合は dispatch から始める理由の行が出る |
| R2 | 手元で実物 | Stop hook を自走中の spec で起動して reason を読み、commands/autopilot.md と実装役・評価役の定義（梯子の段を含む）を grep する | reason と手順に拒否の後に park か block に入れる指示があり、定義の全部に TaskStop の指示があり、手順に approve と gh pr merge を単独で打つ指示がある |
| R3 | 手元で実物 | 一時の git repo で、評価の巡を記録した後に spec の置き場の中だけを commit し、証拠の頭をその commit にして `CLI check` を回す。spec の外を変えた commit でも回す | 置き場の中だけなら check がその要件を通し、外を変えたなら今までどおり落とす |
| R4 | 手元で実物 | 一時の git repo で、申告 M で差分が L に育った spec に `CLI check --stage pr` を回す。申告 M で M のままの spec でも回す | L の spec では NOTE が出て、M の spec では出ない |
| R5 | 手元で実物 | 一時の git repo と gh の代役で、親と子 2 本を作り、子の done の state を子のブランチにだけ commit して、main の作業ツリーで `CLI goal` を回す。片方の子の PR を未マージにした場合も回す | 両方マージ済みなら親が done になり、未マージの子があれば親は done にならず、その子を挙げる |

## 制約
- 予算: 360 分
- 大きさ: L
- playbook: bug-fix

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
- 合意した要件のどれかを満たす方法が無いと分かったとき（その子だけを park に積み、ほかの子を進める。どの子も進められないときだけ block）
- 承認した自走の範囲の外の操作が要るとき（実行せずに park に積む）
- 子の承認が相談役か検証役で通らないとき（その子を discovery のまま残し、次の子へ進む）
