# 梯子の巡を main の申告に頼らず数え、3 巡で必ず作り直しに入れる

- ADR: docs/adr/2026-11-27-ladder-counted-by-script.md

## 目的
人が「3巡も指摘されたら設計に戻って欲しいというフローがあると思うが　なんで5回も回っている？」「GDDでの反省や過去のセッションでの反省点がまったくいかされていない　どうするのが最善？　どうしたら守れる？」と問うた。

梯子は、巡の記録を main が打つ作りで、main が記録を飛ばすか、検査を回し直しただけの high none を記録すると、数えが 0 に戻って上がらない。その事例（docs/specs/2026-11-27-consent-adr-fix-ladder）では、2 巡目の評価役の結果を記録しないまま直しの実装役を起動し、R1 の high は 4 巡のうち 2 巡しか記録に残らなかった。これを、評価役の起動を hook が数え、記録の無いままの直しを止め、巡を累計で数える形にする。できあがると、同じ要件で high が 3 巡出た spec は、main が何を記録し忘れても `autopilot.py check` が作り直し（設計に戻る）を求め、作り直すまで完了の検査を通れない。

## 要件
- R1: phase が building の spec の評価役（subagent_type の最後の `:` の後が `autopilot-reviewer` で始まる）を起動するとき、agent_gate は、その spec が `autopilot.py review` の記録を受ける状態ならその起動をその spec の記録に残して通し、受けない状態なら起動を deny し、review が記録を断るときと同じ理由の文を出す。どの building の spec の評価役か分からない起動は、何も残さずに通す。記録に書けなかったときは、その spec のディレクトリと例外の型を stderr に出して通す。
- R2: 最後に記録した評価役の起動より後に `autopilot.py review` の記録が無い spec について、agent_gate は実装役の起動を deny し、理由に「評価役の結果を `autopilot.py review <dir> --high ...` で記録してから起動し直す」旨とその spec のディレクトリを書く。
- R3: `autopilot.py review` が巡を記録するとき、要件ごとの巡の数（streak）は、その要件に high か失敗のあった巡の累計にする。high も失敗も無い巡では数えを変えない。`autopilot.py rework` は今までどおりその要件の数えを 0 に戻す。
- R4: high R1 → high none（評価役を起動しない再実行）→ high R1 → high none → high R1 の順に記録したとき、R1 の巡の数は 2 巡目の high で 2（原因を調べる段）、3 巡目の high で 3（作り直しの段。`autopilot.py check` が作り直しを求める）になる。
- R5: 承認し直し（lineup.py の承認の処理）で、R1 で残した評価役の起動の記録は `reviews` と同じく前の巡の記録として history に移り、新しい巡では空になる。
- R6: references/dead-end.md の数え方の段落と見出し、commands/autopilot.md の C の 3 の記録の行は、巡を累計で数えること（high も失敗も無い巡で戻さないこと）と、評価役の結果を記録しないと次の dispatch と実装役の起動が止まることと、review を記録できない状態では評価役の起動が止まり handoff を打ち直してから起動することを書く。autopilot.py の梯子の文（「N 巡続いた」）は「N 巡」の累計の言い方にする。
- R7: マージの記録がある building の spec（デプロイ後の QA の段）で、評価役の起動が R1 で deny されたとき、`overnight.py handoff` を打ち直した後の評価役の起動は通る。

## 非目標
- 予算の 2 倍で放す時間の引き金（hooks/stop.py）は変えない。予算を超えた spec がその後に何巡使ったかを、この変更の後の state.json で数えてから別の spec で決める
- 巡を spec 全体の累計で数えること（作り直しの入口が要件ごとのため）
- 評価役の 1 巡目に境界の入力を挙げさせる先手の仕組み（この変更で巡の数が残ってから、別の spec で比べる）
- runs.jsonl に予算と巡の数の欄を足すこと（Issue #33）
- plugins/spec-autopilot/README.md:29 の「high も失敗も無い巡で 0 に戻ります」の直し（変えるファイルが 6 つで大きさ L になるため、この spec のマージの直後に、repo の CLAUDE.md の振り分け 2 の文書の直しとして別の PR にする）
- hooks/hooks.json の description（実装役の門の文は、この変更の後も誤りにならないので変えない）
- main が high を none と偽って記録すること（想定するのは記録の抜けで、偽りは想定しない）

## 影響範囲
- 変える: plugins/spec-autopilot/hooks/agent_gate.py:83-118（全体）
  - メモ: problem と decide
- 変える: plugins/spec-autopilot/scripts/autopilot.py:764-1283（全体）
  - メモ: cmd_review の巡の数え（1259-1272）と、梯子の文（ladder_errors・status・ladder_message・cmd_rework の「N 巡続いた」）
- 変える: plugins/spec-autopilot/scripts/overnight.py:55-56（ROUND_KEYS）
- 変える: plugins/spec-autopilot/scripts/ladder.py:108（全体）
  - メモ: unrecorded_review を足す
- 変える: plugins/spec-autopilot/references/dead-end.md:5-18（全体）
- 変える: plugins/spec-autopilot/commands/autopilot.md:95（全体）
- 呼び出し元: plugins/spec-autopilot/hooks/hooks.json:6
- 呼び出し元: plugins/spec-autopilot/scripts/lineup.py:79-89
- 手本: plugins/spec-autopilot/tests/test_agent_gate.py:58
- 変える: plugins/spec-autopilot/tests/test_autopilot.py:1359-1370（test_round_without_high_or_fail_resets_the_count）
- 変える: plugins/spec-autopilot/tests/test_autopilot.py:1551（全体）
- 同じ入力: reviews、streak、fails、dispatches、handoffs
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_agent_gate.py plugins/spec-autopilot/tests/test_ladder.py plugins/spec-autopilot/tests/test_autopilot.py plugins/spec-autopilot/tests/test_lineup.py plugins/spec-autopilot/tests/test_overnight.py plugins/spec-autopilot/tests/test_prototype_gate.py -q -n auto

## 変えない挙動
- 実装役の起動は、開いた dispatch があるときだけ通る: plugins/spec-autopilot/tests/test_agent_gate.py::test_gate_denies_after_the_dispatch_was_closed_by_a_handoff
- rework は新しい ADR を求め、その要件の数えを 0 に戻す: plugins/spec-autopilot/tests/test_autopilot.py::test_rework_needs_new_existing_adr_and_resets_count
- 梯子の段は、上げた段を渡すまで 1 巡に 1 段だけ上がる: plugins/spec-autopilot/tests/test_ladder.py::test_one_round_raises_one_rung_even_with_several_signals

## 前提
- 目的に届く: R1〜R4 で、評価役を起動したのに記録しない抜けと、再実行の high none で数えが戻る抜けは止まる。評価役を起動せずに直しへ進む抜け（評価役の起動の前の handoff の後に実装役を起動する）は、dispatch と handoff の門が今までどおり見るだけで、この spec では止めない
- 運用: main が /autopilot の C の 3 で評価役を起動し、結果を `autopilot.py review` で記録する。記録を忘れたら、次の実装役の起動で hook の deny を読んで記録する
- 普通のやり方: 同じ repo の、起動を state.json の記録と突き合わせて止める既存の門に揃える（agent_gate.py の problem が実装役の起動を dispatch・handoff と突き合わせ、overnight.py の cmd_dispatch が state の記録で dispatch を断る）。方針の出典は docs/adr/2026-11-15-switch-harness-to-spec-autopilot.md の「文の指示でなく機械の検査で固める」
- 過去: docs/adr/2026-11-25-input-kinds-table.md は、同じ要件で high が 4 巡続いた事例と、表を high の後にしか求めない後手の直しを記録している（読んで確かめた）
- 前提: 評価役と実装役の起動は、どちらも agent_gate を通る
  - path: plugins/spec-autopilot/hooks/hooks.json:6（matcher が Agent|Task）
  - path: plugins/spec-autopilot/hooks/agent_gate.py:107（実装役でない起動は何も記録せずに通す）
- 前提: 今は high も失敗も無い巡で数えが 0 に戻り、その巡の記録は main の `autopilot.py review` だけが作る
  - path: plugins/spec-autopilot/scripts/autopilot.py:1259-1272
  - コマンド: `python3 -c "import json;s=json.load(open('docs/specs/2026-11-27-consent-adr-fix-ladder/state.json'));print(s['streak']['R1'],[r['high'] for r in s['reviews']],len(s['fails']['R1']))"` → `0 [['R1', 'R8'], [], ['R1'], [], []] 2`
- 前提: 評価役の prompt には spec のディレクトリが入る
  - path: plugins/spec-autopilot/commands/autopilot.md:92（渡すのは spec のディレクトリと差分の base・tip）
- 前提: 事例では、評価役の結果を記録しないまま直しの実装役を起動しており、R2 があればそこで止まり、記録すれば R1 の累計は 3 巡目の high で 3 になる
  - コマンド: `state.json の reviews・lenses・dispatches・handoffs を時刻で並べる python3 の 1 行` → 承認から 3103 秒に review [R1,R8]、3598 秒に handoff、5444 秒に評価役の lens（found 2）、5445 秒に review の記録の無いまま R1 の dispatch、7337 秒に review [R1]
- 前提: handoff の後に spec のファイルだけを commit すると、review_gate は通らない（tip と HEAD の完全一致を見る）が、handoff の打ち直しは通り、新しい tip で閉じ直す
  - path: plugins/spec-autopilot/scripts/overnight.py:630-634（closed_handoff）
  - path: plugins/spec-autopilot/scripts/overnight.py:1040（handoff は SPEC_FILES の変更を数えない）
- 前提: 承認し直しは、ROUND_KEYS の記録を history に移して消し、reviews を空にする
  - path: plugins/spec-autopilot/scripts/lineup.py:79-89

## 作り方
この spec の ADR のとおり（直し方の段は「設計を変える」）。agent_gate の decide で、評価役の起動なら prompt に書かれた spec のディレクトリ（spec_dirs）のうち building のもの全部の state.json の `review_launches` に起動の時刻を 1 件足して通し、実装役の起動なら problem で「最後の評価役の起動の時刻 > 最後の review の時刻」を deny の理由にする。state.json の読み書きは autopilot.py の load_state・save_state を使う。`review_launches` を overnight.py の ROUND_KEYS に足し、承認し直しで history に移す。cmd_review の巡の数えから、high も失敗も無い巡で 0 に戻す分岐を消す（autopilot.py の行数は増やさない）。開いた dispatch の後では review を記録できない（review_gate が閉じた handoff を求める）ので、記録の抜けは overnight.py dispatch でも断り、判定は ladder.py の unrecorded_review 1 つを agent_gate と dispatch で使う。「review の記録を受ける状態」の判定は overnight.review_gate 1 つを正本にし、hook に条件を写さない。prompt に building の spec が複数あるときは、1 つでも受ける状態なら通し、受ける状態の spec にだけ記録する。評価役の起動では、agent_gate が overnight.review_gate をそのまま呼び、通る spec にだけ review_launches を足して通し、どの spec も通らなければ deny して review_gate の文を理由に出す（評価役の deny の文は実装役のものと分ける）。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | 評価役の payload を agent_gate に stdin で渡し、state.json と出力を読む。handoff で閉じた spec、dispatch の無い spec、開いた dispatch の spec、handoff の後に spec のファイルだけを commit した spec、受ける spec と受けない spec を並べた prompt、building の spec が無い payload、書けない spec を渡す | 閉じた spec は 1 件増えて通る。dispatch の無い・開いた dispatch・spec の commit の後の spec は deny で、理由に review_gate の文がある。並べた prompt は通り、受ける spec にだけ記録する。building の spec が無い payload は state.json が変わらず通る。書けない spec は通り、stderr にディレクトリと例外の型がある |
| R2 | 手元で実物 | 評価役の起動を記録した後、review を記録せずに、開いた dispatch のある spec で実装役の payload を agent_gate に渡す。続けて review を記録して渡し直す | 1 回目は deny で、理由に `autopilot.py review` と spec のディレクトリがある。2 回目は通る |
| R3 | 手元で実物 | review を high R1 → high none → high R1 で記録し、state.json の streak を読む | R1 が 2 で、none の巡で 0 に戻らない。rework の後は 0 |
| R4 | 手元で実物 | R4 の順で review を記録し、各記録の出力と `autopilot.py check` の出力を読む | 2 巡目の high で原因を調べる段の文、3 巡目の high で check が作り直しを求める |
| R5 | 手元で実物 | review_launches のある building の spec を承認し直し、state.json を読む | review_launches が history の前の巡にあり、新しい巡には無い |
| R6 | 手元で実物 | dead-end.md と autopilot.md の該当の行を読む | 累計で数えることと、記録しないと実装役の起動が止まることが書いてある |
| R7 | 手元で実物 | マージの記録（overnight.py merged）がある building の spec で、checkout をマージの commit に置き、評価役の payload、`overnight.py handoff`、評価役の payload の順に渡す | 1 回目が deny なら、handoff の後の 2 回目は通る（1 回目が通れば、それも合格） |

## 制約
- 予算: 150 分
- 大きさ: L
- playbook: bug-fix
- 想定する脅威: main が評価役の結果の記録を忘れる・飛ばす事故（偽りの記録と、評価役の prompt に関係の無い building の spec を書いて巻き込むことは想定しない。巻き込んだ spec は review を記録するまで実装役の起動が止まり、止まる側に倒れる）

## モデル

## 自走の範囲
- 範囲: マージまで
- QA の環境:
- QA の書き込み先:
- デプロイの起動: なし（マージした commit で QA）
- デプロイの確かめ:
- ロールバック: revert の PR をマージし、デプロイの完了を確かめる
- 通知: デスクトップ
- AWS の profile: なし

## 止まる条件
- 合意した要件のどれかを満たす方法が無いと分かったとき（その要件だけを park に積み、ほかを進める。どの要件も進められないときだけ block）
- 承認した自走の範囲の外の操作が要るとき（実行せずに park に積む）
