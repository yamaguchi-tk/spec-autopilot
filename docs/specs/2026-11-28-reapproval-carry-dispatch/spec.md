# 承認し直しで、spec の外が前の巡の handoff の tip と同じなら、dispatch と handoff の記録を持ち越す

- ADR: docs/adr/2026-11-28-reapproval-carry-dispatch.md

## 目的
人の発言:「まとめて承認」「spec（5 案）もOK」「夜なのでできるだけ確認せずに自走して欲しい」。親の spec（2026-11-27-flow-review-goal）の R1 を受け持つ。

観測: split-modules の run で、blocked の spec を承認し直すと前の巡の dispatch が数えられなくなり、実装がすでに HEAD に入っているので handoff が「commit が無い」で止まった。戻す手順（`git restore`）は auto mode に 4 件拒まれ、毎回人の手が要った。できあがったら、spec の文だけを直した承認し直しで、戻しも実装役の起動も無しに評価役へ進める。

## 要件
- R1: blocked の spec を承認し直したとき、前の巡の最後の dispatch が handoff で閉じていて、spec の置き場（docs/specs と docs/adr）の外のファイルがその handoff の tip と今の HEAD で同じなら、新しい dispatch を打たずに `overnight.py handoff` と `autopilot.py review` が通り、approve（`--queue` で承認したときは、着手の `lineup.py next`）は `dispatch を引き継いだ: ` で始まり、タスクの番号と次の一手（dispatch を打たずに `overnight.py handoff <dir> --task T<n>` から進む）を書いた 1 行を出す。照合に使う handoff は、最後の dispatch を閉じた handoff のうち最後のもの。どちらかが成り立たなければ（前の巡に dispatch が無い場合を含む）、今までどおり dispatch から始め、同じコマンドが `dispatch を引き継がなかった: ` で始まる理由の 1 行を出す（マージの持ち越しの `持ち越した`・`持ち越さなかった` の行と語を分ける）。

## 非目標
- レビュー・QA・park・失敗の記録を持ち越すこと（今までどおり新しい巡で数え直す）
- blocked 以外（done・queued・discovery）からの承認で持ち越すこと
- rebase で spec の外だけが変わり、実装役に直すものが無い場合の扱い（観測していない）
- 版数を上げること（この子の PR のマージの後に、版数だけの PR で patch を 1 つ上げる）

## 影響範囲
- 変える: plugins/spec-autopilot/scripts/carry.py:1-60（same_outside、why_not、plan）
- 変える: plugins/spec-autopilot/scripts/lineup.py:117-142（begin）
- 呼び出し元: plugins/spec-autopilot/scripts/autopilot.py:993
- 呼び出し元: plugins/spec-autopilot/scripts/lineup.py:235
- 呼び出し元: plugins/spec-autopilot/scripts/light.py:180
  - メモ: 軽量フローの approve は prev が discovery なので持ち越さない
- 呼び出し元: plugins/spec-autopilot/scripts/overnight.py:176-195
  - メモ: closed_handoff と review_gate が dispatches と handoffs を読む（呼ぶのではなく同じ記録を読む）。持ち越した handoff の tip が今の HEAD と違えば、handoff を打ち直して閉じ直す（after_close_errors が spec の置き場の中だけの変更を通す）
- 呼び出し元: plugins/spec-autopilot/hooks/agent_gate.py:103-108
  - メモ: 同じ dispatches と handoffs を読む。持ち越すと最後の dispatch は閉じているので、実装役の起動は拒まれる（持ち越したら実装役を起動しない、と合う）
- 変える: plugins/spec-autopilot/tests/test_carry.py:76-85（test_a_carried_round_counts_reviews_qa_and_dispatches_again）
- 変える: plugins/spec-autopilot/tests/test_prototype_gate.py:189-208（test_reapproval_after_a_building_round_moves_the_prototype_dispatch_and_handoff_to_history）
  - メモ: after=blocked の場合は、閉じた試作の dispatch と handoff が state に残る側に書き換える
- 手本: plugins/spec-autopilot/scripts/carry.py:11-19
- 同じ入力: dispatches、handoffs
  - メモ: overnight.py の closed_handoff・review_gate と agent_gate.py の実装役の門が同じ 2 つを読む
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_carry.py plugins/spec-autopilot/tests/test_lineup.py plugins/spec-autopilot/tests/test_overnight.py plugins/spec-autopilot/tests/test_light.py plugins/spec-autopilot/tests/test_prototype_gate.py -q -n auto

## 変えない挙動
- 承認し直しでのマージとデプロイの記録の持ち越し: plugins/spec-autopilot/tests/test_carry.py::test_reapproval_after_a_words_only_fix_carries_the_merge_and_the_deploy
- コードが違うか決められないときは持ち越さない: plugins/spec-autopilot/tests/test_carry.py::test_reapproval_carries_nothing_when_the_code_differs_or_cannot_be_decided
- done からの承認し直しでは試作の dispatch と handoff を history に移す: plugins/spec-autopilot/tests/test_prototype_gate.py::test_reapproval_after_a_building_round_moves_the_prototype_dispatch_and_handoff_to_history
- handoff が新しい dispatch の後に commit を求める: plugins/spec-autopilot/tests/test_overnight.py::test_handoff_after_a_new_dispatch_requires_a_new_commit

## 前提
- 目的に届く: spec の文だけを直した承認し直しは、戻しも実装役も無しに評価役へ進める。コードを変えた承認し直しは今までどおり dispatch から始まり、そこでの詰まりは残る
- 運用: 承認し直した後、main は approve か `lineup.py next` の出力の `dispatch を引き継いだ: ` の行を見て、dispatch を打たずに handoff と評価役に進む。/autopilot の手順の文は子 2 で直す
- 普通のやり方: なし（この plugin に固有の記録の持ち越しで、外の慣習が無い）
- 過去: reapproval-carry-merge の spec の R3 が「dispatch と handoff は新しい巡で数え直す」と決めた。この spec はそれを、最後の dispatch が閉じていて spec の外が同じ場合に限って覆す（理由はこの spec の ADR）
- 前提: approve（begin）は、前の phase が discovery でなければ、dispatches と handoffs を history に移して state から消す。残すのは承認の前の試作の dispatch だけ
  - path: plugins/spec-autopilot/scripts/lineup.py:125-133
- 前提: review_gate は、最後の dispatch を今の HEAD で閉じた handoff を求める
  - path: plugins/spec-autopilot/scripts/overnight.py:176-188
- 前提: handoff は、最後の dispatch が閉じていて HEAD が動いたとき、spec のファイルの外の変更だけを拒む
  - path: plugins/spec-autopilot/scripts/overnight.py:459-490
- 前提: 今のテストは、blocked からの承認し直しの後に dispatches と handoffs が空であることを求めている
  - path: plugins/spec-autopilot/tests/test_carry.py:76-85
  - path: plugins/spec-autopilot/tests/test_prototype_gate.py:207（after=blocked の場合）
- 前提: マージを持ち越さない場合と、マージの無い spec の承認し直しでは、出力に `持ち越した`・`持ち越` が無いことをテストが求めている
  - path: plugins/spec-autopilot/tests/test_carry.py:149
  - path: plugins/spec-autopilot/tests/test_carry.py:158
- 前提: 実装役の起動は、最後の dispatch が handoff で閉じていると拒まれる
  - path: plugins/spec-autopilot/hooks/agent_gate.py:103-108

## 作り方
この spec の ADR のとおり。carry.py に、前の巡の最後の dispatch を閉じた handoff があり、その tip と今の HEAD で spec の置き場の外が同じか（`same_outside` と同じ照合）を見る関数を足す。lineup.py の begin は、前の phase が blocked でそれが成り立つときに dispatches と handoffs を history に移したうえで state にも残し、`dispatch を引き継いだ: `・`dispatch を引き継がなかった: ` の行を出す（マージの持ち越しの語 `持ち越` を使わないので、test_carry.py:149・158 はそのまま通る）。test_carry.py の `test_a_carried_round_counts_reviews_qa_and_dispatches_again` は、dispatches と handoffs の 2 つの期待だけを、持ち越す側に書き換える。test_prototype_gate.py の after=blocked の場合は、dispatches と handoffs が state に残り history にも入る側に書き換える（after=done は今のまま）。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | 一時の git repo で spec を building → dispatch → 実装の commit → handoff → blocked にし、spec の文だけを直して承認し直し、handoff と review を CLI で回す。spec の外を 1 行変えた場合と、最後の dispatch を閉じずに blocked にした場合も回す。文だけの場合は `--queue` で承認し直して `lineup.py next` でも回す | 文だけの場合は dispatch なしで handoff と review が終了コード 0 で通り、approve（`--queue` の場合は `lineup.py next`）が `dispatch を引き継いだ: ` の行を出す。ほかの 2 つは同じコマンドが `dispatch を引き継がなかった: ` の理由を出し、dispatch なしの handoff が今までどおり拒まれる |

## 制約
- 予算: 60 分
- 大きさ: M
- playbook: feature
- 親 spec: 2026-11-27-flow-review-goal
- 親の要件: R1

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
