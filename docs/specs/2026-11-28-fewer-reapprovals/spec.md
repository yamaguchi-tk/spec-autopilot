# 承認し直しと分けた spec ごとの承認で、人に確認を求める回数を減らす

- ADR: docs/adr/2026-11-28-fewer-reapprovals.md

## 目的
人の発言:「複数ステップにまたがる実装の際に、毎回確認が入る　セッションを分析して他の改善点を洗い出して欲しい」「夜回したいので　自走をできるだけして欲しい」。11/25 にも「spec が複数に分かれてそれぞれ毎に承認する形式も無駄」と言っている。

観測した失敗: 11/22〜11/28 に /autopilot を使った main のセッション 74 本で、承認の後に人が返事をした 583 回のうち、直前の問いが承認し直しだったのが 47 回、初回の承認が 38 回だった（キーワードでの粗い分類）。承認し直しの原因として次の 2 つを transcript で確かめた。

- 人の「OK」の後に、先頭の `- ADR:` 行の連番だけを直して approve がもう一度 OK を求めた（「ADR の番号のほかは、承認いただいた R8 の中身から変えていません」）。approve は spec.md の最後の変更の時刻より後の人の発言だけを数える
- 承認し直しの後に前の巡の dispatch が数えられず handoff が通らないので、前の巡の実装を `git restore --source` で戻して作り直そうとし、auto mode に 9 回拒まれた（runs.jsonl の block の理由にも 3 件）

できあがったら、中身を変えない直しで OK を求め直さず、コードが同じ承認し直しで実装を戻さずに評価へ進み、spec を分けるときは人の承認 1 回で夜の間に子を回す。

## 要件
- R1: phase が blocked の spec を自走に戻したとき（人の承認・`--by-advisor`・`--queue` の後の着手のどれでも）、前の巡で実装役の作業を handoff で閉じていて、その後に docs/specs と docs/adr の外のファイルが変わっていなければ、`overnight.py handoff` は実装役を起動し直さず、前の巡の実装を戻さずに通る。
- R2: R1 の条件に当たらないとき（前の巡に実装役への受け渡しが無い、最後の受け渡しが閉じていない、外のファイルが変わった、git で比べられない）、`overnight.py handoff` は今までどおり新しい受け渡しを求める。自走に戻した時の出力は、R1 に当たったとき「持ち越した: dispatch <番号>（<タスク>）」の 1 行を、前の巡に受け渡しがあったのに当たらなかったとき理由の 1 行を出す。
- R3: R1 に当たったときも、レビューの巡・失敗の記録・QA の記録は新しい巡で数え直す。新しい巡で評価役（autopilot-reviewer の系統）を起動した記録が無いうちは、`autopilot.py review` は記録を断る。
- R4: 人の発言の前に `autopilot.py lint` を通した spec.md を、人の発言の後に先頭の `- ADR:` 行の連番の桁だけ直したとき、`autopilot.py approve` は人の発言を求め直さずに通る（approve の中で回る lint の検査は、この判定の起点にしない）。
- R5: 人の発言の後に、spec.md の先頭の `- ADR:` 行の連番の外を 1 文字でも変えたとき（作り方の節を含む）、`autopilot.py approve` は今までどおり人の発言を求める。spec.md を人の発言の前に `autopilot.py lint` で通していないときも、今までどおり spec.md の最後の変更の時刻を起点にする。block・done の時刻を起点にする扱いは変えない。
- R6: `--by-advisor` の承認し直しと、目的の spec の子の承認（`--queue --by-advisor`）でも、相談役の記録を数える起点を R4・R5 と同じにする。
- R7: plugins/spec-autopilot/commands/autopilot.md の A の 3 に、spec を分けるときに目的の spec（`--goal`）とまとめて承認（B の 5）のどちらを選ぶかの基準を書く。既定は目的の spec（人の承認 1 回）で、まとめて承認は人が子の spec を全部見てから承認したいと言ったときだけにする。plugins/spec-autopilot/README.md に同じ選び方の記述があれば合わせる。
- R8: plugins/spec-autopilot/.claude-plugin/plugin.json の version を上げ、`.claude-plugin/marketplace.json` の description は plugin.json と同じに保つ。

## 非目標
- 昼の承認し直しを相談役 2 本で通すこと（commands/autopilot.md の「夜の間の承認し直し」の対象を広げる。人に決めてもらう）
- spec の外の PR（版数・docs・後続の直し）を自走でマージすること（repo の CLAUDE.md の決定）
- 依る spec の block で後ろの spec が全部止まる設計を変えること（上の直しの後に測り直す）
- spec-autopilot の外の hook が `archive_session` の入力を書き換え、auto mode が判定できない件（この repo では直せない）
- `lineup.py` の着手の block（承認の後に spec.md が変わった）の判定を変えること
- 要件の文を直した承認し直しで、変わらない要件の pass やレビューを持ち越すこと

## 影響範囲
- 変える: plugins/spec-autopilot/scripts/carry.py:40-48（plan）
  - メモ: dispatch と handoff を持ち越すかの判定を足す。ファイルは 60 行
- 変える: plugins/spec-autopilot/scripts/lineup.py:117-141（begin）
  - メモ: 持ち越した dispatch と handoff を最上位に戻す。戻り値の形（予算の分）は変えない
- 変える: plugins/spec-autopilot/scripts/autopilot.py:961-998（cmd_lint、cmd_approve）
  - メモ: autopilot.py は 1391 行。行を増やす分は新しいモジュールに出し、1500 行を超えない
- 変える: plugins/spec-autopilot/commands/autopilot.md（全体）
  - メモ: 56〜57 行目（大きさの L と目的の spec）、77〜78 行目（承認の返事とまとめて承認）、155 行目（相談役の記録を数える起点の文）
- 変える: plugins/spec-autopilot/scripts/advisor_approval.py（全体）
  - メモ: since_of と、docstring・エラー文の「spec.md の最後の変更」の言い回し（6・29-30・122 行目）
- 変える: plugins/spec-autopilot/.claude-plugin/plugin.json（全体）
  - メモ: version の行だけ
- 変える: plugins/spec-autopilot/scripts/goal.py:117（child_errors）
  - メモ: 子の承認の起点。since_of を通らない
- 変える: plugins/spec-autopilot/scripts/autopilot.py:1249-1266（cmd_review）
  - メモ: R3 の評価役の起動の記録を見る。起動の記録は hooks/agent_gate.py が残す
- 呼び出し元: plugins/spec-autopilot/scripts/autopilot.py:993
  - メモ: approve が begin を呼ぶ
- 呼び出し元: plugins/spec-autopilot/scripts/lineup.py:235
  - メモ: lineup.py next の着手が begin を呼ぶ（queued の承認し直し）
- 呼び出し元: plugins/spec-autopilot/scripts/light.py:180
  - メモ: 軽量フローの approve が begin を呼ぶ（prev は discovery なので持ち越さない）
- 呼び出し元: plugins/spec-autopilot/scripts/overnight.py:507-548
  - メモ: cmd_handoff が最後の dispatch と、それを閉じた handoff を読む
- 別の実装: plugins/spec-autopilot/scripts/overnight.py:176-180
  - メモ: closed_handoff。review の門が最後の dispatch を閉じた handoff を読む
- 手本: plugins/spec-autopilot/tests/test_carry.py:63（test_reapproval_after_a_words_only_fix_carries_the_merge_and_the_deploy）
- 手本: plugins/spec-autopilot/tests/test_autopilot.py:1078（test_approve_requires_user_prompt_after_spec_change）
- 同じ入力: dispatches、handoffs、history、approved_at、blocked、done_at、spec.md
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_carry.py plugins/spec-autopilot/tests/test_lineup.py plugins/spec-autopilot/tests/test_overnight.py plugins/spec-autopilot/tests/test_autopilot.py plugins/spec-autopilot/tests/test_advisor_approval.py plugins/spec-autopilot/tests/test_goal.py plugins/spec-autopilot/tests/test_prototype_gate.py plugins/spec-autopilot/tests/test_agent_gate.py plugins/spec-autopilot/tests/test_light.py plugins/spec-autopilot/tests/test_goal_child.py plugins/spec-autopilot/tests/test_rollback.py plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py -q -n auto

## 変えない挙動
- spec を変えた後の承認は、その後の人の発言を求める: plugins/spec-autopilot/tests/test_autopilot.py::test_approve_requires_user_prompt_after_spec_change
- block の後の承認は、block の後の人の発言を求める: plugins/spec-autopilot/tests/test_autopilot.py::test_approve_after_block_needs_new_user_prompt
- 目的の spec の承認は、spec の最後の変更の後の人の発言を求める: plugins/spec-autopilot/tests/test_goal.py::test_approve_goal_needs_a_human_prompt_after_the_last_spec_change
- コードが違えばマージを持ち越さない: plugins/spec-autopilot/tests/test_carry.py::test_reapproval_carries_nothing_when_the_code_differs_or_cannot_be_decided
- 軽量フローの承認は、今までどおり動く: plugins/spec-autopilot/tests/test_light.py
  - メモ: 次の 2 本は、この spec で挙動を変える（R1）。test_carry.py::test_a_carried_round_counts_reviews_qa_and_dispatches_again は、dispatch と handoff の扱いだけを変え、レビュー・失敗・QA を数え直すところは残す。test_prototype_gate.py::test_reapproval_after_a_building_round_moves_the_prototype_dispatch_and_handoff_to_history は、after が blocked でコードが同じ場合に持ち越す形に変え、done の場合は今のまま history に移す

## 前提
- 目的に届く: 届くのは、中身を変えない直しでの OK の求め直しと、コードが同じ承認し直しでの実装の戻しを無くすところと、spec を分けるときの承認を 1 回にするところまで。要件の文を変えた承認し直しは、昼は今までどおり人の OK が要る。spec の外の PR のマージの許可（33 回）は減らない
- 運用: main は今までどおり lint → 人に示す → approve を回す。持ち越すかは自走に戻した時の出力に出る。新しい版は、plugin を使う手元の checkout を人が pull したときに効く
- 普通のやり方: なし（承認の門の起点を中身のハッシュで決める仕組みに、決まった作り方は無い。中身を比べるのは、この repo の lineup.py の着手の門と同じ道具）
- 過去: docs/specs/2026-11-27-reapproval-carry-merge で、承認し直しでコードが同じならマージとデプロイの記録を持ち越すようにした。そのとき dispatch と handoff は新しい巡で数え直すと決めた（test_carry.py:76）
- 前提: 承認し直しの begin は、前の巡の dispatches と handoffs を history に写して最上位から消す（承認の前の S の試作の dispatch だけを残す）
  - path: plugins/spec-autopilot/scripts/lineup.py:125-133
- 前提: review の門は、最後の dispatch を閉じた handoff の tip が今の HEAD であることを求め、dispatch が無ければ通らない
  - path: plugins/spec-autopilot/scripts/overnight.py:176-180
  - path: plugins/spec-autopilot/scripts/overnight.py:182-190
- 前提: handoff は、最後の dispatch が閉じていて HEAD が動いたとき、閉じた後の変更が spec の置き場だけなら通す
  - path: plugins/spec-autopilot/scripts/overnight.py:536-537
- 前提: approve は中で lint の検査を回すが、cmd_lint も approve も state.json に lint の記録を書かない
  - path: plugins/spec-autopilot/scripts/autopilot.py:961-963
  - path: plugins/spec-autopilot/scripts/autopilot.py:970
- 前提: review は review の門（閉じた handoff と commit していないコード）だけを見て、評価役を起動したかは見ない
  - path: plugins/spec-autopilot/scripts/autopilot.py:1258-1261
- 前提: 目的の spec の子の承認は、spec.md の最後の変更と先に承認した子の時刻の遅い方を起点にする
  - path: plugins/spec-autopilot/scripts/goal.py:117-118
- 前提: approve は spec.md の最後の変更の時刻を起点にし、block・done の時刻がそれより後ならそれを起点にする
  - path: plugins/spec-autopilot/scripts/autopilot.py:984
  - path: plugins/spec-autopilot/scripts/advisor_approval.py:28-40
- 前提: spec のハッシュ（sha）は作り方の節を外し、先頭の `- ADR:` 行の連番の桁を外して計算する
  - path: plugins/spec-autopilot/scripts/autopilot.py:153-165
- 前提: 目的の spec（`--goal`）は人の承認 1 回で、子を相談役 2 本で承認して夜の間に回す
  - path: plugins/spec-autopilot/commands/autopilot.md:57

## 作り方
目的の spec として 1 回承認を受け、夜の間に 3 本の子に分けて回す。子は 1 本ずつ PR にしてマージし、次の子は最新の main から切る。

- 子 1（R1〜R3）: carry.py の判定に、前の巡の最後の dispatch と、それを閉じた handoff の tip と今の HEAD の間の spec の置き場の外の差分（carry.same_outside と同じ git の pathspec）を足し、begin が dispatches と handoffs を最上位に戻す。決められないときは持ち越さない。carry.plan の戻り値の形を変えるなら test_carry.py:188 も合わせる。review は、新しい巡の評価役の起動の記録（hooks/agent_gate.py が残すもの）が無ければ断る
- 子 2（R4〜R6）: `autopilot.py lint` の CLI が通ったときだけ、承認の中身のハッシュ（spec.md の全体から先頭の `- ADR:` 行の連番の桁だけを外したもの。作り方の節を含める）と、そのハッシュを初めて見た時刻を state.json に残す（同じハッシュでは時刻を書き換えない）。approve の中の lint の検査は記録しない。approve・`--by-advisor`・子の承認の起点は、今のハッシュの記録があればその時刻、無ければ spec.md の最後の変更の時刻にする。autopilot.py が 1500 行を超えないよう、増える分は新しいモジュールに置く
- 子 3（R7〜R8）: 文書と版数

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | 一時 repo で spec を承認・dispatch・実装の commit・handoff・block・spec の文だけの直し・承認し直しの順に CLI を回し、`overnight.py handoff` を打つ | 承認し直しの出力に「持ち越した: dispatch」の行があり、handoff が実装役を起動せずに OK を返す |
| R2 | 手元で実物 | R1 と同じ手順で、block の後に spec の置き場の外のファイルを変えて commit してから承認し直す | 持ち越さなかった理由の行が出て、handoff が dispatch の記録が無いと断る |
| R3 | 手元で実物 | R1 の手順の後、評価役を起動せずに `autopilot.py review --high none` を打ち、次に評価役の起動の記録を残してから打ち直す | 1 回目は断り、2 回目は通る。state.json の reviews・fails・qa_runs が新しい巡で空から数えられている |
| R4 | 手元で実物 | 一時 repo で `autopilot.py lint` → 人の発言の記録 → 先頭の `- ADR:` 行の連番だけを直す → `autopilot.py approve` | approve が通る |
| R5 | 手元で実物 | R4 と同じ手順で、連番の代わりに要件の文か作り方の節を 1 文字変える。別に、lint を回さずに人の発言 → 連番だけ直す → approve | どれも approve が人の発言を求めて断る |
| R6 | 手元で実物 | R4・R5 と同じ 2 通りを、block の後の `approve --by-advisor` と、目的の spec の子の `approve --queue --by-advisor` で回す（相談役 2 本の記録は一時 repo の transcript に作る） | 連番だけの直しは通り、中身の直しは断る |
| R7 | 手元で実物 | commands/autopilot.md の差分を読み、A の 3 の目的の spec とまとめて承認の記述を突き合わせる | 選ぶ基準が書かれ、既定が目的の spec で、B の 5 の記述と食い違わない |
| R8 | 手元で実物 | `python3 -m pytest plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py -q` | 版数が前の版を超え、marketplace の description が plugin.json と同じでテストが通る |

## 制約
- 予算: 270 分
- 大きさ: L
- playbook: feature
- 子の大きさ: どれも M（承認の前に試作を作らないため）
- 子の自走の範囲: 親と同じ
- 子の順: 子 1（R1〜R3）→ 子 2（R4〜R6）→ 子 3（R7〜R8）
- 想定する脅威: 事故（main が人の返事も評価役の確かめも無いまま、中身の違う spec で承認を通すこと、コードの違う承認し直しで前の巡の handoff を流用すること）。state.json や transcript の偽造は守らない

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
