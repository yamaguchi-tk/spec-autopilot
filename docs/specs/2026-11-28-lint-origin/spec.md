# 承認の門の起点を、承認の中身のハッシュを lint が初めて見た時刻にする

- ADR: docs/adr/2026-11-28-fewer-reapprovals.md

## 目的
目的の spec（docs/specs/2026-11-28-fewer-reapprovals）の R1〜R4 を受け持つ。人の発言:「複数ステップにまたがる実装の際に、毎回確認が入る」。

観測した失敗: 人の「OK」の後に、先頭の `- ADR:` 行の連番だけを直して approve がもう一度 OK を求めた（「ADR の番号のほかは、承認いただいた R8 の中身から変えていません」）。approve は spec.md の最後の変更の時刻より後の人の発言だけを数える。できあがったら、人が見た中身と同じ spec では OK を求め直さない。

## 要件
- R1: 人の発言の前に `autopilot.py lint` を通した spec.md を、人の発言の後に先頭の `- ADR:` 行の連番の桁だけ直したとき、`autopilot.py approve` は人の発言を求め直さずに通る。
- R2: 人の発言の後に、spec.md の先頭の `- ADR:` 行の連番の外を 1 文字でも変えたとき（作り方の節を含む）、`autopilot.py approve` は今までどおり人の発言を求める。spec.md を人の発言の前に `autopilot.py lint` で通していないときも、今までどおり spec.md の最後の変更の時刻を起点にする。block・done の時刻を起点にする扱いは変えない。ただし、人に示す前の lint を飛ばして示した中身に人が返事をした後、lint を通した中身へ連番ごと戻したときは除く（非目標）。
- R3: `--by-advisor` の承認し直しと、目的の spec の子の承認（`--queue --by-advisor`）でも、相談役の記録を数える起点を R1・R2 と同じにする。
- R4: /autopilot の手順は、spec を人に示す前と、照合役の ng や人の直しの指示で直して示し直す前に、毎回 `autopilot.py lint` を通すと読め、承認の返事の項（人に示す前に lint が通した中身なら連番だけの直しで求め直さない）と食い違わない。

## 非目標
- 人に示す前の lint を飛ばして示した中身に人が返事をした後、lint を通した中身へ連番ごと戻した承認を止めること（承認の門は中身の履歴を持たないので見分けられない。R4 の手順で、示す中身は必ず lint の記録に残る。この spec の ADR の残る限界）
- 人の発言のときの spec の中身を hook で残すこと（観測した失敗が無い）
- hooks/user_prompt.py の docstring にある approve の起点の説明（「spec.md の変更」）を直すこと（判定に関わらない説明の文。影響範囲を増やさず、別に直す）
- 昼の承認し直しを相談役 2 本で通すこと
- `lineup.py` の着手の block（承認の後に spec.md が変わった）の判定を変えること
- 承認の後の check が見る spec のハッシュ（作り方の節を外すもの）を変えること

## 影響範囲
- 変える: plugins/spec-autopilot/scripts/autopilot.py:961-998（cmd_lint、cmd_approve）
  - メモ: autopilot.py は 1391 行。増える分は新しいモジュールに置き、1500 行を超えない
- 変える: plugins/spec-autopilot/scripts/advisor_approval.py（全体）
  - メモ: since_of と、docstring・エラー文の「spec.md の最後の変更」の言い回し（6・29-30・122 行目）
- 変える: plugins/spec-autopilot/scripts/goal.py:117（child_errors）
  - メモ: 子の承認の起点。since_of を通らない
- 変える: plugins/spec-autopilot/commands/autopilot.md（全体）
  - メモ: 57・77・78・155 行目の「spec.md の最後の変更」を起点とする説明を、新しい起点に合わせる。74〜76 行目（B の 3・4）に、示す前と示し直す前に毎回 lint を通すと書く
- 変える: plugins/spec-autopilot/tests/test_goal_child.py:153-160（test_child_records_made_before_the_last_spec_change_do_not_count）
  - メモ: エラー文の「spec.md の最後の変更」を言い換えるなら合わせる
- 新規: plugins/spec-autopilot/scripts/consent.py
- 新規: plugins/spec-autopilot/tests/test_consent.py
- 呼び出し元: plugins/spec-autopilot/scripts/autopilot.py:984
  - メモ: approve が since_of を呼ぶ
- 呼び出し元: plugins/spec-autopilot/scripts/goal.py:118
  - メモ: child_errors が reply_errors に起点を渡す
- 別の実装: plugins/spec-autopilot/scripts/autopilot.py:153-165
  - メモ: sha。作り方の節を外す。承認の中身のハッシュは作り方の節を含める
- 手本: plugins/spec-autopilot/tests/test_autopilot.py:1078（test_approve_requires_user_prompt_after_spec_change）
- 同じ入力: spec.md、approved_at、blocked、done_at、state.json
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_autopilot.py plugins/spec-autopilot/tests/test_goal_command.py plugins/spec-autopilot/tests/test_advisor_approval.py plugins/spec-autopilot/tests/test_goal.py plugins/spec-autopilot/tests/test_goal_child.py plugins/spec-autopilot/tests/test_lineup.py plugins/spec-autopilot/tests/test_light.py -q -n auto

## 変えない挙動
- spec を変えた後の承認は、その後の人の発言を求める: plugins/spec-autopilot/tests/test_autopilot.py::test_approve_requires_user_prompt_after_spec_change
- block の後の承認は、block の後の人の発言を求める: plugins/spec-autopilot/tests/test_autopilot.py::test_approve_after_block_needs_new_user_prompt
- 目的の spec の承認は、lint で記録していない中身なら spec の最後の変更の後の人の発言を求める（人の発言が無ければ止まる）: plugins/spec-autopilot/tests/test_goal.py::test_approve_goal_needs_a_human_prompt_after_the_last_spec_change
- 軽量フローの承認は、今までどおり動く: plugins/spec-autopilot/tests/test_light.py

## 前提
- 目的に届く: 届くのは、中身を変えない直しでの OK の求め直しを無くすところまで。要件の文を変えた承認し直しは、昼は今までどおり人の OK が要る
- 運用: main は今までどおり lint → 人に示す → approve を回す。lint を回さずに示した spec は今までどおり mtime を起点にする
- 普通のやり方: なし（承認の門の起点を中身のハッシュで決める仕組みに、決まった作り方は無い）
- 過去: docs/specs/2026-11-28-fewer-reapprovals の分析で、ADR の連番だけの直しで OK を求め直した場面を transcript で確かめた
- 前提: approve は中で lint の検査を回すが、cmd_lint も approve も state.json に lint の記録を書かない
  - path: plugins/spec-autopilot/scripts/autopilot.py:961-963
  - path: plugins/spec-autopilot/scripts/autopilot.py:970
- 前提: approve は spec.md の最後の変更の時刻を起点にし、block・done の時刻がそれより後ならそれを起点にする
  - path: plugins/spec-autopilot/scripts/autopilot.py:984
  - path: plugins/spec-autopilot/scripts/advisor_approval.py:28-40
- 前提: 目的の spec の子の承認は、spec.md の最後の変更と先に承認した子の時刻の遅い方を起点にする
  - path: plugins/spec-autopilot/scripts/goal.py:117-118
- 前提: spec のハッシュ（sha）は作り方の節を外し、先頭の `- ADR:` 行の連番の桁を外して計算する
  - path: plugins/spec-autopilot/scripts/autopilot.py:153-165

## 作り方
新しいモジュール consent.py に、承認の中身のハッシュ（spec.md の全体から先頭の `- ADR:` 行の連番の桁だけを外したもの。作り方の節を含める）と、記録と起点を求める関数を置く。`autopilot.py lint` の CLI が通ったときだけ、{ハッシュ, そのハッシュを初めて見た時刻} を state.json に残す（同じハッシュでは時刻を書き換えない）。approve の中の lint の検査は記録しない（この判定の起点にしない）。記録には lint の時点の spec.md の mtime と、連番を含む本文全体のハッシュも残し、lint の後に spec.md が変わったときは、本文全体が lint の時点から連番の桁だけ違うときに限って記録の時刻を起点にする。approve・`--by-advisor`・子の承認の起点は、今のハッシュの記録があればその時刻、無ければ spec.md の最後の変更の時刻にし、block・done の扱いは since_of のまま重ねる。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | 一時 repo で `autopilot.py lint` → 人の発言の記録 → 先頭の `- ADR:` 行の連番だけを直す → `autopilot.py approve` | approve が通る |
| R2 | 手元で実物 | R1 と同じ手順で、連番の代わりに要件の文か作り方の節を 1 文字変える。別に、lint を回さずに人の発言 → 連番だけ直す → approve | どれも approve が人の発言を求めて断る |
| R3 | 手元で実物 | R1・R2 と同じ 2 通りを、block の後の `approve --by-advisor` と、目的の spec の子の `approve --queue --by-advisor` で回す（相談役 2 本の記録は一時 repo の transcript に作る） | 連番だけの直しは通り、中身の直しは断る |
| R4 | 手元で実物 | commands/autopilot.md の差分を読み、B の 3・4（照合役の ng の直し・人の直しの指示の後の示し直し）と B の 5（承認の返事）を突き合わせる。あわせて一時 repo で lint(A) → B に直す → lint(B) → 人の発言 → 連番だけ直す → approve と、lint(A) → B に直す → lint(B) → 人の発言 → 連番ごと A に戻す → approve を回す | 示す前と示し直す前に毎回 lint を通すと読め、B の 5 と食い違わない。1 本目の approve は通り、2 本目は人の発言を求めて断る |

## 制約
- 予算: 90 分
- 大きさ: M
- playbook: feature
- 親 spec: 2026-11-28-fewer-reapprovals
- 親の要件: R1、R2、R3、R4
- 想定する脅威: 事故（main が人の返事も相談役の検証も無いまま、中身の違う spec で承認を通すこと）。state.json や transcript の偽造は守らない

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
