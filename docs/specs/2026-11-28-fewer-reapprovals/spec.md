# 中身を変えない直しと分けた spec の承認で、人に確認を求める回数を減らす

- ADR: docs/adr/2026-11-28-fewer-reapprovals.md

## 目的
人の発言:「複数ステップにまたがる実装の際に、毎回確認が入る　セッションを分析して他の改善点を洗い出して欲しい」「夜回したいので　自走をできるだけして欲しい」。11/25 にも「spec が複数に分かれてそれぞれ毎に承認する形式も無駄」と言っている。

観測した失敗: 11/22〜11/28 に /autopilot を使った main のセッション 74 本で、承認の後に人が返事をした 583 回のうち、直前の問いが承認し直しだったのが 47 回、初回の承認が 38 回だった（キーワードでの粗い分類）。承認し直しの原因として次の 2 つを transcript で確かめた。

- 人の「OK」の後に、先頭の `- ADR:` 行の連番だけを直して approve がもう一度 OK を求めた（「ADR の番号のほかは、承認いただいた R8 の中身から変えていません」）。approve は spec.md の最後の変更の時刻より後の人の発言だけを数える
- 承認し直しの後に前の巡の dispatch が数えられず handoff が通らないので、前の巡の実装を `git restore --source` で戻して作り直そうとし、auto mode に 9 回拒まれた（runs.jsonl の block の理由にも 3 件）

2 つ目（コードが同じ承認し直しで実装を戻す）は、この spec の承認の後に main へ入った PR #105（docs/specs/2026-11-28-reapproval-carry-dispatch）が直した。できあがったら、中身を変えない直しで OK を求め直さず、spec を分けるときは人の承認 1 回で夜の間に子を回す。

## 要件
- R1: 人の発言の前に `autopilot.py lint` を通した spec.md を、人の発言の後に先頭の `- ADR:` 行の連番の桁だけ直したとき、`autopilot.py approve` は人の発言を求め直さずに通る。
- R2: 人の発言の後に、spec.md の先頭の `- ADR:` 行の連番の外を 1 文字でも変えたとき（作り方の節を含む）、`autopilot.py approve` は今までどおり人の発言を求める。spec.md を人の発言の前に `autopilot.py lint` で通していないときも、今までどおり spec.md の最後の変更の時刻を起点にする。block・done の時刻を起点にする扱いは変えない。ただし、人に示す前の lint を飛ばして示した中身に人が返事をした後、lint を通した中身へ連番ごと戻したときは除く（非目標）。
- R3: `--by-advisor` の承認し直しと、目的の spec の子の承認（`--queue --by-advisor`）でも、相談役の記録を数える起点を R1・R2 と同じにする。
- R4: /autopilot の手順は、spec を人に示す前と、照合役の ng や人の直しの指示で直して示し直す前に、毎回 `autopilot.py lint` を通すと読め、承認の返事の項と食い違わない。
- R5: plugins/spec-autopilot/commands/autopilot.md の A の 3 に、spec を分けるときに目的の spec（`--goal`）とまとめて承認（B の 5）のどちらを選ぶかの基準を書く。既定は目的の spec（人の承認 1 回）で、まとめて承認は人が子の spec を全部見てから承認したいと言ったときだけにする。plugins/spec-autopilot/README.md に同じ選び方の記述があれば合わせる。

## 非目標
- 昼の承認し直しを相談役 2 本で通すこと（commands/autopilot.md の「夜の間の承認し直し」の対象を広げる。人に決めてもらう）
- spec の外の PR（版数・docs・後続の直し）を自走でマージすること（repo の CLAUDE.md の決定）
- 依る spec の block で後ろの spec が全部止まる設計を変えること（上の直しの後に測り直す）
- spec-autopilot の外の hook が `archive_session` の入力を書き換え、auto mode が判定できない件（この repo では直せない）
- `lineup.py` の着手の block（承認の後に spec.md が変わった）の判定を変えること

- 人に示す前の lint を飛ばして示した中身に人が返事をした後、lint を通した中身へ連番ごと戻した承認を止めること（承認の門は中身の履歴を持たないので見分けられない。この spec の ADR の残る限界）
- 人の発言のときの spec の中身を hook で残すこと（観測した失敗が無い）
- コードが同じ承認し直しで、前の巡の dispatch と handoff を持ち越すこと（PR #105 が main に入れた）
- dispatch を持ち越した巡で、評価役を起動するまで review を断ること（観測した失敗が無い。測るなら、state.json の history で、dispatch を引き継いだ巡のうち評価役の起動の記録が無いまま review した巡を数え、1 件でもあれば別の spec にする）
- 版数を上げること（repo の CLAUDE.md の決まりどおり、マージの後に版数だけの PR で上げる）

## 影響範囲
- 変える: plugins/spec-autopilot/scripts/autopilot.py:961-998（cmd_lint、cmd_approve）
  - メモ: autopilot.py は 1391 行。行を増やす分は新しいモジュールに出し、1500 行を超えない
- 変える: plugins/spec-autopilot/commands/autopilot.md（全体）
  - メモ: 56〜57 行目（大きさの L と目的の spec）、26 行目（作った verify skill の PR をまとめて承認の先頭に置く文。目的の spec のときは子の先頭に置くと合わせる）、74〜76 行目（示す前の lint）、77〜78 行目（承認の返事とまとめて承認）、155 行目（相談役の記録を数える起点の文）
- 変える: plugins/spec-autopilot/scripts/advisor_approval.py（全体）
  - メモ: since_of と、docstring・エラー文の「spec.md の最後の変更」の言い回し（6・29-30・122 行目）
- 変える: plugins/spec-autopilot/scripts/goal.py:117（child_errors）
  - メモ: 子の承認の起点。since_of を通らない
- 新規: plugins/spec-autopilot/scripts/consent.py
- 新規: plugins/spec-autopilot/tests/test_consent.py
- 手本: plugins/spec-autopilot/tests/test_autopilot.py:1078（test_approve_requires_user_prompt_after_spec_change）
- 呼び出し元: plugins/spec-autopilot/scripts/autopilot.py:984
  - メモ: approve が since_of を呼ぶ
- 同じ入力: approved_at、blocked、done_at、spec.md、state.json
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_consent.py plugins/spec-autopilot/tests/test_consent_adr.py plugins/spec-autopilot/tests/test_autopilot.py plugins/spec-autopilot/tests/test_advisor_approval.py plugins/spec-autopilot/tests/test_goal.py plugins/spec-autopilot/tests/test_goal_child.py plugins/spec-autopilot/tests/test_goal_command.py plugins/spec-autopilot/tests/test_lineup.py plugins/spec-autopilot/tests/test_light.py -q -n auto

## 変えない挙動
- spec を変えた後の承認は、その後の人の発言を求める: plugins/spec-autopilot/tests/test_autopilot.py::test_approve_requires_user_prompt_after_spec_change
- block の後の承認は、block の後の人の発言を求める: plugins/spec-autopilot/tests/test_autopilot.py::test_approve_after_block_needs_new_user_prompt
- 目的の spec の承認は、lint で記録していない中身なら spec の最後の変更の後の人の発言を求める（人の発言が無ければ止まる）: plugins/spec-autopilot/tests/test_goal.py::test_approve_goal_needs_a_human_prompt_after_the_last_spec_change
- 軽量フローの承認は、今までどおり動く: plugins/spec-autopilot/tests/test_light.py

## 前提
- 目的に届く: 届くのは、中身を変えない直しでの OK の求め直しを無くすところと、spec を分けるときの承認を 1 回にするところまで（実装の戻しは PR #105 が直した）。要件の文を変えた承認し直しは、昼は今までどおり人の OK が要る。spec の外の PR のマージの許可（33 回）は減らない
- 運用: main は lint → 人に示す → approve を回し、直して示し直す前にも lint を通す。新しい版は、plugin を使う手元の checkout を人が pull したときに効く
- 普通のやり方: なし（承認の門の起点を中身のハッシュで決める仕組みに、決まった作り方は無い。中身を比べるのは、この repo の lineup.py の着手の門と同じ道具）
- 過去: docs/specs/2026-11-28-reapproval-carry-dispatch（PR #105）が、コードが同じ承認し直しで閉じた dispatch と handoff を持ち越すようにした。子 2 の評価で、lint の記録だけでは、lint を通さずに示した中身へ連番ごと戻した承認を見分けられないと分かった（docs/specs/2026-11-28-lint-origin/evidence/R2-block.md）
- 前提: 着手の時点の main では、approve は中で lint の検査を回すが、cmd_lint も approve も state.json に lint の記録を書かない
  - path: plugins/spec-autopilot/scripts/autopilot.py:961-963
  - path: plugins/spec-autopilot/scripts/autopilot.py:970
- 前提: 着手の時点の main では、目的の spec の子の承認は、spec.md の最後の変更と先に承認した子の時刻の遅い方を起点にする
  - path: plugins/spec-autopilot/scripts/goal.py:117-118
- 前提: 着手の時点の main では、approve は spec.md の最後の変更の時刻を起点にし、block・done の時刻がそれより後ならそれを起点にする
  - path: plugins/spec-autopilot/scripts/autopilot.py:984
  - path: plugins/spec-autopilot/scripts/advisor_approval.py:28-40
- 前提: spec のハッシュ（sha）は作り方の節を外し、先頭の `- ADR:` 行の連番の桁を外して計算する
  - path: plugins/spec-autopilot/scripts/autopilot.py:153-165
- 前提: 目的の spec（`--goal`）は人の承認 1 回で、子を相談役 2 本で承認して夜の間に回す
  - path: plugins/spec-autopilot/commands/autopilot.md:57

## 作り方
目的の spec として 1 回承認を受け、2 本の子に分けて回す。子は 1 本ずつ PR にしてマージし、次の子は前の子の先端に載せる。

- 子 2（R1〜R4）: `autopilot.py lint` の CLI が通ったときだけ、承認の中身のハッシュ（spec.md の全体から先頭の `- ADR:` 行の連番の桁だけを外したもの。作り方の節を含める）・本文全体のハッシュ・そのハッシュを初めて見た時刻・lint の時点の spec.md の mtime を state.json に残す。approve の中の lint の検査は記録しない（この判定の起点にしない）。approve・`--by-advisor`・子の承認の起点は、今のハッシュの記録があり、lint の後に spec.md が変わっていないか連番の桁だけが変わったときはその時刻、ほかは spec.md の最後の変更の時刻にする。autopilot.py が 1500 行を超えないよう、増える分は新しいモジュールに置く。commands/autopilot.md の B の 3・4 に、示す前と示し直す前に毎回 lint を通すと書く
- 子 3（R5）: 文書だけ。版数は、マージの後に版数だけの PR で上げる

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | 一時 repo で `autopilot.py lint` → 人の発言の記録 → 先頭の `- ADR:` 行の連番だけを直す → `autopilot.py approve` | approve が通る |
| R2 | 手元で実物 | R1 と同じ手順で、連番の代わりに要件の文か作り方の節を 1 文字変える。別に、lint を回さずに人の発言 → 連番だけ直す → approve | どれも approve が人の発言を求めて断る |
| R3 | 手元で実物 | R1・R2 と同じ 2 通りを、block の後の `approve --by-advisor` と、目的の spec の子の `approve --queue --by-advisor` で回す（相談役 2 本の記録は一時 repo の transcript に作る） | 連番だけの直しは通り、中身の直しは断る |
| R4 | 手元で実物 | commands/autopilot.md の差分を読み、B の 3・4 と B の 5 を突き合わせ、一時 repo で lint(A) → B に直す → lint(B) → 人の発言 → 連番だけ直す、と、連番ごと A に戻す、の 2 通りで approve を回す | 示す前と示し直す前に毎回 lint を通すと読め、1 本目は通り、2 本目は断る |
| R5 | 手元で実物 | commands/autopilot.md の差分を読み、A の 3 の目的の spec とまとめて承認の記述を突き合わせる | 選ぶ基準が書かれ、既定が目的の spec で、B の 5 の記述と食い違わない |

## 制約
- 予算: 120 分
- 大きさ: L
- playbook: feature
- 子の大きさ: どれも M（承認の前に試作を作らないため）
- 子の自走の範囲: 親と同じ
- 子の順: 子 2（R1〜R4）→ 子 3（R5）
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
