# コードが同じ承認し直しで、前の巡の実装役への受け渡しを持ち越す

- ADR: docs/adr/2026-11-28-fewer-reapprovals.md

## 目的
目的の spec（docs/specs/2026-11-28-fewer-reapprovals）の R1〜R3 を受け持つ。人の発言:「複数ステップにまたがる実装の際に、毎回確認が入る」「夜回したいので　自走をできるだけして欲しい」。

観測した失敗: 承認し直しの後に前の巡の dispatch が数えられず handoff が通らないので、前の巡の実装を `git restore --source` で戻して作り直そうとし、auto mode に 9 回拒まれた（runs.jsonl の block の理由にも 3 件）。できあがったら、コードが同じ承認し直しでは実装を戻さずに評価へ進む。

## 要件
- R1: phase が blocked の spec を自走に戻したとき（人の承認・`--by-advisor`・`--queue` の後の着手のどれでも）、前の巡で実装役への最後の受け渡しを `overnight.py handoff` で閉じていて、閉じた時点から docs/specs と docs/adr の外のファイルが変わっていなければ、`overnight.py handoff` は新しい `overnight.py dispatch` も実装役の起動も、前の巡の実装を戻すことも求めずに通る。
- R2: R1 の条件に当たらないとき（前の巡に受け渡しが無い、最後の受け渡しが閉じていない、外のファイルが変わった、git で比べられない、前の phase が blocked でない）、`overnight.py handoff` は今までどおり新しい `overnight.py dispatch` を求める。自走に戻した時の出力には、マージの持ち越しの行とは別の 1 行として、R1 に当たったとき「持ち越した: dispatch <番号>（<タスク>）」を、前の巡に受け渡しがあったのに当たらなかったとき「持ち越さなかった dispatch: 」で始まる理由を出す。前の巡に受け渡しが無ければ、受け渡しの行は出さない。
- R3: R1 に当たったときも、レビュー・失敗・QA の記録と評価役の起動の記録は新しい巡で空から数え直す。受け渡しを持ち越した巡では、新しい巡で評価役（autopilot-reviewer の系統）を起動した記録が 1 件も無いうちは、`autopilot.py review` は記録を断る。

## 非目標
- dispatch を持ち越さない巡（新しく dispatch した巡）で、review が評価役の起動の記録を求めること（hook を通さない既存のテストと手順を変える）
- 要件の文を直した承認し直しで、変わらない要件の pass やレビューを持ち越すこと
- 承認の門の起点を変えること（兄弟の spec の 2026-11-28-lint-origin が受け持つ）

## 影響範囲
- 変える: plugins/spec-autopilot/scripts/carry.py:40-48（plan）
  - メモ: dispatch と handoff を持ち越すかの判定を別の関数で足す。plan の戻り値の形は変えない（test_carry.py:188 はそのまま）。ファイルは 60 行
- 変える: plugins/spec-autopilot/scripts/lineup.py:117-141（begin）
  - メモ: 持ち越した dispatch と handoff を最上位に戻す。戻り値（予算の分）は変えない
- 変える: plugins/spec-autopilot/scripts/autopilot.py:1249-1266（cmd_review）
  - メモ: 持ち越した巡だけ review_launches を見る。autopilot.py は 1391 行で、1500 行を超えない
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
- 別の実装: plugins/spec-autopilot/hooks/agent_gate.py:130-135
  - メモ: 評価役の起動で review_launches に時刻を足す
- 手本: plugins/spec-autopilot/tests/test_carry.py:63（test_reapproval_after_a_words_only_fix_carries_the_merge_and_the_deploy）
- 同じ入力: dispatches、handoffs、history、review_launches、approved_at、blocked
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_carry.py plugins/spec-autopilot/tests/test_lineup.py plugins/spec-autopilot/tests/test_overnight.py plugins/spec-autopilot/tests/test_autopilot.py plugins/spec-autopilot/tests/test_prototype_gate.py plugins/spec-autopilot/tests/test_agent_gate.py plugins/spec-autopilot/tests/test_light.py plugins/spec-autopilot/tests/test_rollback.py -q -n auto

## 変えない挙動
- コードが違えばマージを持ち越さない: plugins/spec-autopilot/tests/test_carry.py::test_reapproval_carries_nothing_when_the_code_differs_or_cannot_be_decided
  - メモ: マージを持ち越さない挙動は変えない。出力の assert だけを下のメモのとおり直す
- 承認し直しの後は新しいレビューを求める: plugins/spec-autopilot/tests/test_autopilot.py::test_reapproval_requires_a_new_review
- 軽量フローの承認は、今までどおり動く: plugins/spec-autopilot/tests/test_light.py
  - メモ: 次の 4 本は、この spec で挙動を変える（R1・R2）。test_carry.py::test_reapproval_carries_nothing_when_the_code_differs_or_cannot_be_decided と test_carry.py::test_a_spec_without_a_merge_prints_nothing_about_carrying は、マージの持ち越しの出力だけを見る assert（「持ち越した: マージ」が無い）に直し、コードが同じなら dispatch の行が出ることを足す。test_carry.py::test_a_carried_round_counts_reviews_qa_and_dispatches_again は、dispatch と handoff の扱いだけを変え、レビュー・失敗・QA を数え直すところは残す。test_prototype_gate.py::test_reapproval_after_a_building_round_moves_the_prototype_dispatch_and_handoff_to_history は、after が blocked でコードが同じ場合に持ち越す形に変え、done の場合は今のまま history に移す

## 前提
- 目的に届く: 届くのは、コードが同じ承認し直しで実装を戻す回避を無くすところまで。承認の OK の求め直しは兄弟の spec が受け持つ
- 運用: main は今までどおり approve か lineup.py next で自走に戻す。持ち越したかは、戻した時の出力の 1 行に出る
- 普通のやり方: なし（この plugin の中の記録の持ち越しで、外に決まった作り方は無い）
- 過去: docs/specs/2026-11-27-reapproval-carry-merge で、コードが同じならマージとデプロイの記録を持ち越すようにし、dispatch と handoff は新しい巡で数え直すと決めた（test_carry.py:76）
- 前提: 承認し直しの begin は、前の巡の dispatches と handoffs を history に写して最上位から消す（承認の前の S の試作の dispatch だけを残す）
  - path: plugins/spec-autopilot/scripts/lineup.py:125-133
- 前提: review の門は、最後の dispatch を閉じた handoff の tip が今の HEAD であることを求め、dispatch が無ければ通らない
  - path: plugins/spec-autopilot/scripts/overnight.py:176-190
- 前提: handoff は、最後の dispatch が閉じていて HEAD が動いたとき、閉じた後の変更が spec の置き場だけなら通す
  - path: plugins/spec-autopilot/scripts/overnight.py:536-537
- 前提: review は review の門だけを見て、評価役を起動したかは見ない
  - path: plugins/spec-autopilot/scripts/autopilot.py:1258-1261
- 前提: 評価役の起動の記録 review_launches は巡ごとの記録で、begin が history に移す
  - path: plugins/spec-autopilot/scripts/deploy.py:20-21

## 作り方
carry.py に、前の巡の最後の dispatch とそれを閉じた handoff を持ち越すかの判定を別の関数で足す（carry.same_outside と同じ git の pathspec で、handoff の tip と今の HEAD を比べる。決められないときは持ち越さない）。begin はその dispatch と handoff を history に移さずに最上位に残し、持ち越した印を state.json に残す。当たらなければ今までどおり history に移す。review は印がある巡だけ、hooks/agent_gate.py が残す review_launches（begin が巡ごとに空にする）を見る。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | 一時 repo で spec を承認・dispatch・実装の commit・handoff・block・spec の文だけの直し・承認し直しの順に CLI を回し、`overnight.py handoff` を打つ | 承認し直しの出力に「持ち越した: dispatch」の行があり、handoff が実装役を起動せずに OK を返す |
| R2 | 手元で実物 | R1 と同じ手順で、block の後に spec の置き場の外のファイルを変えて commit してから承認し直す | 「持ち越さなかった dispatch: 」の理由の行が出て、handoff が dispatch の記録が無いと断る |
| R3 | 手元で実物 | R1 の手順の後、評価役を起動せずに `autopilot.py review --high none` を打ち、次に review_launches に記録を残してから打ち直す | 1 回目は断り、2 回目は通る。state.json の reviews・fails・qa_runs が新しい巡で空から数えられている |

## 制約
- 予算: 90 分
- 大きさ: M
- playbook: feature
- 親 spec: 2026-11-28-fewer-reapprovals
- 親の要件: R1、R2、R3
- 想定する脅威: 事故（コードの違う承認し直しで前の巡の handoff を流用すること、評価役を起動せずに review を記録すること）。state.json の偽造は守らない

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
