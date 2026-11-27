# 承認し直しで、コードが同じならマージとデプロイの記録を持ち越す

- ADR: docs/adr/2026-11-27-reapproval-carry-merge.md

## 目的
人の発言:「夜間作業が止まったので　これも改善して」。

観測した失敗: 別の repo の spec が、マージとデプロイを済ませた後に要件の文の直しで 3 回承認し直し、11/27 12:42 に block した。理由は「承認し直しで、前の承認の巡・マージ・デプロイの記録が数えられなくなり（awaits は approved_at より後だけを読む）、smoke と QA を記録できない。done に届くには、レビューの巡・新しい PR のマージ・デプロイをやり直す必要がある」。runs.jsonl の 3 日分で、block の理由に「承認し直すと前の記録が消える」と書かれた spec は 2 本あった。要件の文だけを直してコードが同じなら、本番に出たものは変わっていないのに、マージとデプロイをやり直さないと done に届かない。

できあがったら、blocked の spec を承認し直したとき、最後のマージの後に spec の置き場の外のコードが変わっていなければ、マージとデプロイの記録を持ち越し、レビューと QA だけをやり直して done に届く。コードが変わっている、または同じか決められないときは、今までどおり数え直す。

## 要件
- R1: phase が blocked の spec を自走に戻すとき（人の承認・`--by-advisor`・`--queue` の後の着手のどれでも）、前の巡の最後のマージが戻しのマージでなく、そのマージの PR の head と今の HEAD の間で docs/specs と docs/adr の外のファイルが同じなら、マージの記録と、前の巡のマージ・デプロイ・CI の待ちの記録を持ち越し、新しい巡でもマージ済み・デプロイ済みとして数える。前の巡は今までどおり history にも写す。
- R2: R1 の条件を決められないとき（前の巡にマージが無い、最後が戻しのマージ、マージの記録に PR の head が無い、前の承認の時刻が無い〔着手の block の後〕、git で比べられない）か、spec の置き場の外のファイルが違うとき、今までどおり何も持ち越さない。
- R3: 持ち越したときも、レビューの巡・失敗の記録・QA の記録・実装役の dispatch と handoff・park は新しい巡で数え直し、マージ後の予算の時計は自走に戻した時刻から数え直す。
- R4: 持ち越した spec の `autopilot.py check` は、最後のマージの PR の head と今の HEAD の間の差分が docs/specs と docs/adr の中だけなら、「今の HEAD を含むマージ」があるとみなす。持ち越していない spec の判定は変えない。
- R5: 持ち越した後に docs/specs と docs/adr の外のファイルを commit した spec の `autopilot.py check` は、今までどおり新しいマージを求める。
- R6: 自走に戻した時（approve・`lineup.py next` の着手・`light.py approve` の後の承認し直し）の出力は、持ち越したとき「持ち越した: マージ <n> 件（PR <番号>、…）」を、前の巡にマージがあったのに持ち越さなかったとき理由を 1 行出す。
- R7: plugins/spec-autopilot/.claude-plugin/plugin.json の version を上げ、marketplace の description は plugin.json と同じに保つ。

## 非目標
- 変わった要件だけを数え直し、変わらない要件の pass とレビューを持ち越すこと（案 B）
- 承認の門（人の発言・`--by-advisor`）を変えること
- phase が done の spec の承認し直し（done の後の直し）で持ち越すこと
- lineup.py の着手の block（approved_at を空け、merges を history に移す）の後の持ち越し
- 持ち越したマージの PR に、直した spec の文を入れること（spec の置き場の直しは、マージの後の qa.md・state.json の commit と同じく、作業ブランチに残る）
- 前の巡で park に積んだデプロイ（起動がコマンドの spec）を持ち越すこと

## 影響範囲
- 変える: plugins/spec-autopilot/scripts/lineup.py:73-89（begin）
  - メモ: 戻り値の形（予算の分）は変えない。持ち越しの結果は begin が 1 行 print し、state に書く
- 変える: plugins/spec-autopilot/scripts/overnight.py:208-218（scope_errors）
  - メモ: 216 行目の「今の HEAD を含むマージ」の判定を、新しいモジュールの関数の呼び出しにする。overnight.py は 1495 行なので、行を増やさない
- 変える: plugins/spec-autopilot/scripts/overnight.py:652-657（awaits）
  - メモ: 起点を、持ち越しの起点があればそれにする。行を増やさない
- 新規: plugins/spec-autopilot/scripts/carry.py
  - メモ: 持ち越すかの判定と、持ち越した spec の「HEAD を含むマージ」の判定
- 変える: plugins/spec-autopilot/.claude-plugin/plugin.json（全体）
  - メモ: version の行だけ
- 呼び出し元: plugins/spec-autopilot/scripts/autopilot.py:985
  - メモ: approve が begin を呼ぶ
- 呼び出し元: plugins/spec-autopilot/scripts/lineup.py:163
  - メモ: lineup.py next の着手が begin を呼ぶ（prev は queued の元の phase）
- 呼び出し元: plugins/spec-autopilot/scripts/light.py:180
  - メモ: 軽量フローの approve が begin を呼ぶ（prev は discovery なので持ち越さない）。戻り値を予算として出すので、戻り値の形を変えない
- 別の実装: plugins/spec-autopilot/scripts/lineup.py:92-105
  - メモ: 着手の block。approved_at を空け、merges を history に移す。変えない
- 別の実装: plugins/spec-autopilot/scripts/autopilot.py:1046-1067
  - メモ: cmd_block。merges と approved_at を最上位に残す。変えない
- 別の実装: plugins/spec-autopilot/scripts/overnight.py:652-676
  - メモ: deploy_floor も awaits を読む
- 手本: plugins/spec-autopilot/tests/test_overnight.py:675（test_reapproving_after_a_post_merge_block_starts_a_fresh_round）
- 手本: plugins/spec-autopilot/tests/test_overnight.py:254（test_check_requires_a_merge_that_contains_head）
- 同じ入力: merges、merged_at、paused_at_merge、approved_at、history、awaits.jsonl
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_overnight.py plugins/spec-autopilot/tests/test_lineup.py plugins/spec-autopilot/tests/test_autopilot.py plugins/spec-autopilot/tests/test_light.py plugins/spec-autopilot/tests/test_prototype_gate.py plugins/spec-autopilot/tests/test_advisor_approval.py plugins/spec-autopilot/tests/test_rollback.py plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py -q -n auto

## 変えない挙動
- 承認し直しは、新しいレビューを求める: plugins/spec-autopilot/tests/test_autopilot.py::test_reapproval_requires_a_new_review
- 承認し直しの前の park は、新しい巡を逃がさない: plugins/spec-autopilot/tests/test_overnight.py::test_a_park_from_before_the_reapproval_does_not_exempt_the_new_round
- マージの記録が無ければ、範囲がマージを含む spec の check は通らない: plugins/spec-autopilot/tests/test_overnight.py::test_check_requires_a_merge_that_contains_head
- 承認し直しの前の S の試作の dispatch・handoff は history に移す: plugins/spec-autopilot/tests/test_prototype_gate.py::test_reapproval_after_a_building_round_moves_the_prototype_dispatch_and_handoff_to_history
  - メモ: test_overnight.py::test_reapproving_after_a_post_merge_block_starts_a_fresh_round は、この spec で挙動を変える（マージの後に spec の外のファイルが同じなら持ち越す）。テストは、コードを変えてから承認し直す形と、持ち越す形の 2 本に分ける

## 前提
- 目的に届く: 届くのは、要件の文だけを直した承認し直しで、マージとデプロイをやり直さずに done に届くところまで。直しでコードも変わるなら、今までどおり新しい PR・マージ・デプロイが要る。レビューと QA は毎回やり直す
- 運用: main は今までどおり block → spec の直し → approve を回す。持ち越すかは自走に戻した時の出力に出て、main はそれに従ってレビューと QA に進む
- 普通のやり方: なし（承認し直しの後にマージの記録を持ち越す仕組みに、決まった作り方は無い。コードの同一性を git の差分で決めるのは、この repo の only_tests_and_docs と同じ道具）
- 過去: docs/specs/2026-11-26-advisor-reapproval で承認し直しを夜の間に通せるようにした。前の巡を history に移す動きは、test_overnight.py:675 が「新しい巡は承認から数え直す」と決めている
- 前提: begin は承認し直しのとき、前の巡の記録（ROUND_KEYS を含む）を history に写し、最上位から消して、approved_at を今にする
  - path: plugins/spec-autopilot/scripts/lineup.py:73-89
  - path: plugins/spec-autopilot/scripts/overnight.py:55-56
- 前提: blocked の spec の最上位に残る記録は block の出どころで違い、cmd_block は merges と approved_at を残し、着手の block は approved_at を空けて merges を history に移す
  - path: plugins/spec-autopilot/scripts/autopilot.py:1058-1062
  - path: plugins/spec-autopilot/scripts/lineup.py:92-100
- 前提: awaits は approved_at より後に終わった待ちの記録だけを返す
  - path: plugins/spec-autopilot/scripts/overnight.py:652-657
- 前提: 範囲がマージを含む spec の check は、今の HEAD が最後のマージの head の祖先であることを求める
  - path: plugins/spec-autopilot/scripts/overnight.py:208-218
  - path: plugins/spec-autopilot/scripts/overnight.py:192-197
- 前提: マージの記録は pr・sha・head・at を持ち、戻しのマージは rollback の印を持つ
  - path: plugins/spec-autopilot/scripts/overnight.py:1140-1165
- 前提: マージ後の予算の時計は、merged_at が空のときに最初のマージで固まり、merged_at が空なら予算は承認から数える
  - path: plugins/spec-autopilot/scripts/overnight.py:1163-1164
  - path: plugins/spec-autopilot/scripts/overnight.py:726-733
- 前提: begin を呼ぶ 3 か所は、戻り値を予算の分として出す
  - path: plugins/spec-autopilot/scripts/autopilot.py:985-988
  - path: plugins/spec-autopilot/scripts/lineup.py:163-165
  - path: plugins/spec-autopilot/scripts/light.py:180-184
- 前提: 観測した spec は、承認し直しで前の記録が数えられなくなって block した
  - コマンド: `grep -F '"kind": "block"' ~/.claude/spec-autopilot/runs.jsonl` → 11/27 12:42 の block の理由に「承認し直しで、前の承認の巡・マージ・デプロイの記録が数えられなくなり」とある（別の repo なので名前は書かない）

## 作り方
この spec の ADR のとおり、案 A（コードが同じときだけ、マージとデプロイの事実を持ち越す）にする。

- 新しいモジュール `carry.py` に、(1) 持ち越すかの判定（R1・R2）と、(2) 持ち越した spec の「HEAD を含むマージ」の判定（R4）を置く。(1) は、最上位の `merges` の最後が `rollback` でなく `head` を持ち、最上位の `approved_at` があり、`git diff --quiet <head> HEAD -- . ':(exclude)docs/specs' ':(exclude)docs/adr'` が 0 で終わるときだけ持ち越す（1 なら差分あり、ほかの終了コードと例外は決められないとして持ち越さない。照合は git の pathspec に任せ、自前で path を比べない）。(2) は、持ち越しの起点がある spec だけ、`git diff --name-only <head> HEAD` が docs/specs と docs/adr の中だけかを見る
- begin は prev が blocked のときだけ (1) を呼ぶ。持ち越すなら、history には今までどおり写したうえで、`merges` を最上位に残し、`merged_at` を新しい approved_at、`paused_at_merge` を 0 にし、`awaits_since`（持ち越しの起点）を前の `awaits_since`、無ければ前の `approved_at` にする。持ち越さないなら `awaits_since` を消す。reviews・fails・streak・reworks と、merges・merged_at・paused_at_merge 以外の ROUND_KEYS（qa_runs・dispatches・handoffs・parked・lenses など）は今までどおり消す
- begin は持ち越しの結果を 1 行 print し、戻り値（予算の分）は変えない（approve・着手・軽量フローの 3 か所の出力に同じ行が出る。autopilot.py は 1526 行なので触らない）
- awaits は `awaits_since` があればそれを、無ければ approved_at を起点にする。持ち越しで読む前の巡の待ちの記録（CI・デプロイ・レビューの待ち）は、持ち越したマージと同じ事実なので全部読む
- scope_errors の 216 行目は、`awaits_since` がある spec だけ (2) を使う

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 代役 | 一時の repo で範囲が「マージ・デプロイ・QA まで」の spec を自走に入れ、tests/test_overnight.py の gh の代役（PR と run の応答）で `overnight.py merged` とデプロイの待ちを記録し、`autopilot.py block` → spec.md の要件の文だけを直して commit → approve する。`--queue` で承認して `lineup.py next` で着手する形も打つ | state の最上位に merges が残り、デプロイの成功の記録を awaits が返し、history の最後にも前の巡の merges がある |
| R2 | 代役 | R1 の手前で、(a) spec の外のファイルを 1 行変えて commit、(b) 最後のマージを戻しのマージにする、(c) merges の head を消す、(d) 着手の block（approved_at が空）の後、の 4 つの入力で自走に戻す | どれも最上位に merges が無く、awaits は新しい approved_at より後だけを返す |
| R3 | 代役 | R1 の後の state を読む | reviews・qa_runs・dispatches・handoffs・parked・lenses が空で、merged_at が新しい approved_at と同じ |
| R4 | 代役 | R1 の後にレビューの巡（high none）を入れて `autopilot.py check` を打つ。あわせて、持ち越していない spec で spec.md だけを commit した HEAD の check も打つ | 持ち越した spec は「今の HEAD を含むマージ」のエラーが出ない。持ち越していない spec は今までどおりエラーが出る |
| R5 | 代役 | R1 の後に spec の外のファイルを commit して check を打つ | 「今の HEAD を含むマージ」のエラーが出る |
| R6 | 代役 | R1 と R2 の approve・`lineup.py next` の出力を読む | R1 は「持ち越した: マージ 1 件（PR <番号>）」が出て、R2 の (a)〜(c) は持ち越さない理由が 1 行出る |
| R7 | 手元で実物 | plugin.json の version を読み、`python3 -m pytest plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py -q` を回す | version が上がり、テストが通る |
- 代役の理由: R1（一時の repo には実物の PR とデプロイの run が無い。gh の応答は tests の代役で立てる）
- 代役の理由: R2（R1 と同じ）
- 代役の理由: R3（R1 と同じ）
- 代役の理由: R4（R1 と同じ）
- 代役の理由: R5（R1 と同じ）
- 代役の理由: R6（R1 と同じ）

## 制約
- 予算: 90 分
- 大きさ: M
- playbook: feature
- 脅威: 事故だけ（コードが変わったのに前のデプロイを本番の証拠として数えること）。agent が git の履歴を偽造する形は想定しない

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
