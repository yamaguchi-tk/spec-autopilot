# block の後に、相談役の承認し直しへ進む導線を足す

- ADR: docs/adr/2026-11-27-night-reapproval-route.md

## 目的
人の発言:「夜間作業が止まったので　これも改善して」。前に決めたこと（docs/specs/2026-11-26-advisor-reapproval の目的）:「承認の単位とPRの単位を切り離す　で途中の承認はFableでよい」「Fableの直しの裏取りしたら間違っていたことも複数あるので裏取りはして欲しい」。

観測した失敗: 11/26 22 時〜11/27 9 時に、別の repo の spec が 00:59 に R2 の文を直す必要で block し、人が 11:21 に承認し直すまで約 10 時間止まった。夜の承認し直し（`approve --by-advisor`）はその checkout に入っていたが、runs.jsonl の 3 日分で使われたのは 0 回だった。そのセッションは、人に聞く前の相談として fable-advisor（00:54）と advice-checker（00:56）を回し、その後に `block`（00:59）を打って、人に聞いて turn を終えた。承認の門は spec.md の最後の変更と block の後に起動した相談役だけを数えるので、この相談は数えられなかった。block の出力（`blocked: R<n>。人に 1 通で示す`）と status の行（「返事を受けたら…」）は、人の返事を待つ道だけを示す。

できあがったら、block の後は、まず spec を直して相談役 2 段の承認し直しを試し、通らなかったときだけ人に 1 通で示して行列の次に進む。人がいる昼でも同じ順にする（途中の承認は Fable でよいという人の決定に合わせ、「夜の間か」を決める判定を持たない）。

## 要件
- R1: `autopilot.py block` が block を記録したとき、出力は、人に示す前に `/autopilot` の「人に戻るとき」の承認し直し（spec を直してから fable-advisor → advice-checker → `approve --by-advisor`）を試すことと、相談役は spec を直した後に起動したものだけが数えられることと、通らなければ `lineup.py next` で次に進んで人に 1 通で示すことを書く。
- R2: phase が blocked の spec の `autopilot.py status` は、R1 と同じ順（承認し直しを試す → 通らなければ人の返事を待つ）を 1 行で示す。
- R6: `--by-advisor` が受けない blocked の spec（advisor_approval.py の human_errors が断る。最後の承認のときの `## 自走の範囲` の節の記録が無い spec〔軽量フローの `light.py approve` で承認した spec、この版より前に承認した spec〕など）では、R1 の block の出力と R2 の status の行は承認し直しを示さず、今までどおり人に 1 通で示して返事を待つと書く。
- R3: commands/autopilot.md の C の冒頭の「変える必要があるなら『人に戻るとき』に進む」の文は、check のエラー文の使い分けにそろい、1 つの要件だけなら `overnight.py park` で積んでほかを進め、どの要件も進められないときだけ `CLI block` で記録して「人に戻るとき」に進むと書く（Issue #22）。
- R4: commands/autopilot.md の「人に戻るとき」は、block の後に、時刻や人がいるかによらず、まず承認し直しの手順（今の 1〜5）を回し、通らないとき（`承認: 否`・反証あり・確かめられない 1 以上・`## 自走の範囲` を変える直し・直す文が無い）だけ人に 1 通で示して `lineup.py next` に進むと書く。その相談を、SessionStart の相談役の規則の「返事待ちで turn を終える前の 2 段の相談」（1 つの確認に 1 回）に数え、人に示すときに重ねて回さないと書く。再開の項（「blocked なら人の返事を待つ」）も同じ順に直す。agents/fable-advisor.md の `承認:` の欄の「夜の間に」「朝まで」の限定を、block の後の承認し直しの相談（時刻によらない）に直す。
- R5: plugins/spec-autopilot/.claude-plugin/plugin.json の version を上げ、marketplace の description は plugin.json と同じに保つ。

## 非目標
- 承認の門（`approve --by-advisor` の判定、advisor_approval.py）を変えること。緩めも締めもしない
- 「夜の間か」を機械で決めること（最後の人の発言からの時間など）
- 承認し直しで前の巡の記録を持ち越すこと（別の spec: 2026-11-27-reapproval-carry-merge）
- Stop hook で、block の後に承認し直しを試したかを強制すること（承認し直しの使用が 0 回のままなら、別に出す）
- lineup.py の着手の block（`blocked: <spec>（理由）`）の出力を変えること

## 影響範囲
- 変える: plugins/spec-autopilot/scripts/autopilot.py:1046-1067（cmd_block）
  - メモ: 1065 行目の print の文だけ。行は増やさない（ファイルは 1526 行で目安の 1500 行を超えているので、増やさない）
- 変える: plugins/spec-autopilot/scripts/autopilot.py:1112-1146（status）
  - メモ: 1138 行目の blocked の行の文だけ
- 変える: plugins/spec-autopilot/commands/autopilot.md（全体）
  - メモ: 85 行目の C の冒頭の 1 文、128 行目の再開の項、144-160 行目の「人に戻るとき」だけ
- 変える: plugins/spec-autopilot/agents/fable-advisor.md（全体）
  - メモ: 85 行目の `承認:` の欄の文だけ
- 変える: plugins/spec-autopilot/.claude-plugin/plugin.json（全体）
  - メモ: version の行だけ
- 呼び出し元: plugins/spec-autopilot/hooks/session_start.py:5
  - メモ: status の行を SessionStart の文脈に入れる
- 別の実装: plugins/spec-autopilot/scripts/lineup.py:92-105
  - メモ: 着手の block の出力。変えない
- 別の実装: plugins/spec-autopilot/scripts/advisor_approval.py:47-55
  - メモ: human_errors。`--by-advisor` を受けるかの判定。R6 で出力を分けるのに呼ぶだけで、変えない
- 手本: plugins/spec-autopilot/tests/test_autopilot.py:1671（test_status_shows_phase_budget_and_what_is_left）
- 手本: plugins/spec-autopilot/tests/test_autopilot.py:877（test_block_requires_known_requirement_and_evidence）
- 同じ入力: blocked
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_autopilot.py plugins/spec-autopilot/tests/test_advisor_approval.py plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py -q -n auto

## 変えない挙動
- block の後の承認は、--by-advisor を付けなければ人の新しい発言を求める: plugins/spec-autopilot/tests/test_autopilot.py::test_approve_after_block_needs_new_user_prompt
- --by-advisor は、block より前に起動した相談役の記録を数えない: plugins/spec-autopilot/tests/test_advisor_approval.py::test_approve_by_advisor_ignores_records_older_than_the_block
- block は、知らない要件と空の証拠を受けない: plugins/spec-autopilot/tests/test_autopilot.py::test_block_requires_known_requirement_and_evidence

## 前提
- 目的に届く: 届くのは、block の後に main が承認し直しの道を見落とさないところまで。相談役が否と言うか、検証で反証が出た承認し直しは、今までどおり人の返事まで止まる。main が出力と本文を読んでも道を選ばない事故は、機械では止めない（非目標の Stop hook）
- 運用: main が block を打った直後に出力と「人に戻るとき」に従う。人は朝の報告で、相談役で承認した巡（approved_by）を読み直す
- 普通のやり方: なし（agent の承認を別の agent に検証させる流れに、決まった作り方は無い。この repo の相談役の 2 段の規則に合わせる）
- 過去: docs/specs/2026-11-26-advisor-reapproval で `--by-advisor` を入れた。docs/specs/2026-11-25-fix-order-park で check のエラー文を park と block の使い分けにした。Issue #22 は command の本文だけがその使い分けに残っていないと挙げた（gh issue view 22 で確かめた）
- 前提: block の出力は、人に 1 通で示すことだけを言う
  - path: plugins/spec-autopilot/scripts/autopilot.py:1065
- 前提: blocked の status の行は、人の返事の後の手順だけを言う
  - path: plugins/spec-autopilot/scripts/autopilot.py:1138
- 前提: `--by-advisor` は、spec.md の最後の変更と block の時刻の遅い方より後に起動した相談役だけを数え、phase が blocked で自走の範囲の節が最後の承認と同じ spec だけを受ける
  - path: plugins/spec-autopilot/scripts/autopilot.py:966-982
  - path: plugins/spec-autopilot/scripts/advisor_approval.py:1-40
- 前提: 軽量フローの approve は `scope_sha256` を書かないので、その spec の最初の block の後は `--by-advisor` が断る
  - path: plugins/spec-autopilot/scripts/light.py:152-183
  - path: plugins/spec-autopilot/scripts/autopilot.py:982
- 前提: fable-advisor の `承認:` の欄は、夜の間の承認し直しの相談に限っている
  - path: plugins/spec-autopilot/agents/fable-advisor.md:85
- 前提: command の C の冒頭は、承認の後に変える必要があるならすぐ「人に戻るとき」に進むと書いている
  - path: plugins/spec-autopilot/commands/autopilot.md:85
- 前提: 「人に戻るとき」の承認し直しの手順は、夜の間（人の返事を待てないとき）に限っている
  - path: plugins/spec-autopilot/commands/autopilot.md:152-158
- 前提: 夜の間に止まった spec のセッションは、相談役を block より前に回し、block の後は人に聞いて turn を終えた
  - コマンド: `grep -F '"kind": "block"' ~/.claude/spec-autopilot/runs.jsonl` → 00:59 の block の行（R2）。その後の承認し直しは 11:21
  - 未確認: 相談役の起動の時刻（fable-advisor 00:54、advice-checker 00:56）は、そのセッションの transcript を読んで得た。別の repo の記録なので、ここに path を書かない

## 作り方
この spec の ADR のとおり、「夜の間か」を決めずに、block の後はいつも承認し直しを先に試す順にそろえる。

- cmd_block の print と status の blocked の行の文を、R1・R2 の順を示す文に置き換える（行は増やさない）
- commands/autopilot.md は、85 行目・128 行目・「人に戻るとき」の 3 か所だけを直す。「夜の間（人の返事を待てないとき）」の限定を外し、通らないときの道（人に 1 通・`lineup.py next`）を手順の最後に置く
- テストは、block と status の出力に、承認し直しの道（`--by-advisor`）と `lineup.py next` が出ることを確かめる（CLI の出力を確かめるテストで、文書の語を確かめるテストではない）

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | 一時の repo で spec を承認して自走に入れ、`autopilot.py block` を打って出力を読む | 出力に `--by-advisor` と、spec を直した後の相談役だけを数えることと、`lineup.py next` が出る。終了コードは 0 で、phase は blocked |
| R2 | 手元で実物 | R1 の spec で `autopilot.py status` を打つ | blocked の行が、承認し直しを試す → 通らなければ人の返事を待つ、の順を 1 行で示す |
| R3 | 手元で実物 | commands/autopilot.md の C の冒頭を読み、`autopilot.py check` の「承認の後に変わった」のエラー文（scripts/autopilot.py の check）と突き合わせる | park と block の使い分けが同じで、「変える必要があるなら『人に戻るとき』に進む」の文が残っていない |
| R4 | 手元で実物 | commands/autopilot.md の「人に戻るとき」と再開の項を読み、R1 の出力と、`approve --by-advisor` が受ける条件（advisor_approval.py）と突き合わせる | 承認し直しを先に試す順が R1 の出力と同じで、通らない場合に挙げた条件が approve の ERROR の条件と食い違わず、夜の間の限定が残っていない |
| R6 | 手元で実物 | `light.py approve` で承認した spec と、state から `scope_sha256` を消した spec で block と status を打つ | 出力に `--by-advisor` が出ず、人に 1 通で示す道だけが出る |
| R5 | 手元で実物 | plugin.json の version を読み、`python3 -m pytest plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py -q` を回す | version が上がり、テストが通る |

## 制約
- 予算: 60 分
- 大きさ: M
- playbook: bug-fix
- 脅威: 事故だけ（main が block の後に承認し直しの道を見落として朝まで止まること）。判定は変えない

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
