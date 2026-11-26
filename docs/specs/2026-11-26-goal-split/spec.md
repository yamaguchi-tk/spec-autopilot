# 人が 1 回承認した目的の spec を、夜の間に子の spec に分けて回す

- ADR: docs/adr/2026-11-26-goal-split.md

## 目的
人の発言（順に）:「複数Specになるときに朝までに実装完了させることができないのは欠陥」「specの度に人間の承認が必要で夜中回すことが出来ない」「そもそもspecが複数に分かれてそれぞれ毎に承認する形式も無駄　どういった形式が最善かを検討して」「承認の単位とPRの単位を切り離す　で途中の承認はFableでよい」「Fableの直しの裏取りしたら間違っていたことも複数あるので裏取りはして欲しい」。

観測した失敗: 今は大きさ L の spec を初回の合意で lint と approve が ERROR にし、人が分けた spec を 1 本ずつ承認する。このセッションでも 3 本の spec を 1 本ずつ示して 1 本ずつ承認を受け、runs.jsonl に `approve --queue` でまとめて承認して夜通し回した記録は無い。夜の間に分けた spec は人の承認が無いので回らない。

できあがったら、人は目的の spec（大きさ L でよい）を 1 回承認し、main が夜の間にそれを M 以下の子の spec に分け、子は相談役の推奨と検証で承認されて行列に入り、1 本ずつ PR になる。子が全部 done になり、親の要件を全部受け持ったら、親も done になる。

## 要件
- R1: `autopilot.py approve <dir> --by "<要約>" --goal` を打ったとき、approve は大きさ L を理由に止めず（ほかの lint の ERROR では今までどおり止まる）、人の発言の門を通ったときだけ、その spec を目的として承認した記録（時刻・`--by` の要約）を残す。phase は discovery のままで、実装役の dispatch と自走（building）には入らない。`--goal` を付けない approve は、今までどおり L で止まる。
- R2: `## 制約` に `- 親 spec: <親の spec のディレクトリ名>` と `- 親の要件: R<n>、…` を書いた phase が discovery の spec で、`autopilot.py approve <dir> --by "<要約>" --queue --by-advisor` を打ったとき、親が目的として承認されていて、子の `## 自走の範囲` の節が親の承認のときと同じで、`- 親の要件:` の番号が全部親の要件にあり、2026-11-26-advisor-reapproval の相談役の条件を満たせば、approve は子を queued にし、approved_by に `相談役（fable-advisor・advice-checker 反証なし）: <要約>` を書く。
- R3: R2 の条件のどれかが欠けたとき（親が無い・親が目的として承認されていない、自走の範囲の節が親と違う、`- 親の要件:` に親に無い番号がある、相談役の条件が欠ける）、approve は ERROR で終わり、欠けた条件を挙げ、子は discovery のまま残る。
- R4: `autopilot.py goal <親の dir>` を打ったとき、親の要件ごとに、それを `- 親の要件:` に挙げた子と、その子の phase を出す。親の要件が全部どれかの子に挙がり、挙げた子が全部 done なら、親を done にする（done の時刻を記録し、runs.jsonl に done の行を書く）。そうでなければ ERROR で終わり、子の無い要件と done でない子を挙げる。
- R5: commands/autopilot.md の A の 3 の L の項に、人が目的の spec を `--goal` で承認したら、main が子の spec を init し、B の 1〜3（lint と照合役を含む）を済ませ、fable-advisor → advice-checker を回して `approve --queue --by-advisor` を打ち、`lineup.py next` で回し、子が全部 done になったら `autopilot.py goal` を打ち、朝の報告に子ごとの approved_by と goal の結果を書く手順がある。
- R6: plugins/spec-autopilot/.claude-plugin/plugin.json の version を上げ、marketplace の description は plugin.json と同じに保つ。

## 非目標
- 子の spec を作り忘れたときに Stop hook で止めること（測ってから足す）
- 子を並行に回すこと（今の行列のまま直列）
- 子の自走の範囲を親より広げること（親と同じ節だけを受ける）
- 親の要件の文と子の要件の文が同じ意味かを機械で確かめること（`- 親の要件:` の番号と、相談役の検証で見る）
- 承認の検査を敵対的な書き換えから守ること
- 子を親と別の worktree に置くこと（このアプリのセッションは自分の worktree の外に書けないので、子は親と同じ worktree に置き、ブランチを切り替えて回す）

## 影響範囲
- 変える: plugins/spec-autopilot/scripts/autopilot.py:539-611（size_errors、lint）
  - メモ: lint に、L を初回の合意でも止めない引数を足す（`--goal` のときだけ渡す）
- 変える: plugins/spec-autopilot/scripts/autopilot.py:930-963（cmd_approve）
  - メモ: `--goal` と子の承認の分岐の呼び出しだけを置き、判定は goal.py に置く
- 変える: plugins/spec-autopilot/scripts/advisor_approval.py（全体）
  - メモ: 2026-11-26-advisor-reapproval が作る。相談役の条件の判定の関数を、そのまま呼ぶ
- 新規: plugins/spec-autopilot/scripts/goal.py
- 変える: plugins/spec-autopilot/commands/autopilot.md（全体）
  - メモ: A の 3 の L の項に手順を足すだけ
- 変える: plugins/spec-autopilot/.claude-plugin/plugin.json（全体）
  - メモ: version の行だけ
- 呼び出し元: plugins/spec-autopilot/scripts/autopilot.py:1462-1465
  - メモ: approve の引数。goal の subcommand もここに足す
- 別の実装: plugins/spec-autopilot/scripts/lineup.py:46-70
  - メモ: queue_lint・enqueue。子を queued にする
- 別の実装: plugins/spec-autopilot/scripts/autopilot.py:987-1001
  - メモ: cmd_done。done_at・release・runlog の記録。親の done で同じ記録を書く
- 別の実装: plugins/spec-autopilot/hooks/stop.py:49
  - メモ: RELEASED。discovery を放す。変えない
- 手本: plugins/spec-autopilot/tests/test_autopilot.py:1144（test_approve_after_block_needs_new_user_prompt）
- 同じ入力: phase、approved_by
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/ -q -n auto
  - メモ: approve を呼ぶテストが 11 ファイルにあるので全体を回す

## 変えない挙動
- 初回の合意で大きさ L の spec を止める（--goal を付けないとき）: plugins/spec-autopilot/tests/test_size.py
- block の後の承認は、人の新しい発言を求める: plugins/spec-autopilot/tests/test_autopilot.py::test_approve_after_block_needs_new_user_prompt
- 依る spec のある spec は --queue でだけ承認できる: plugins/spec-autopilot/tests/test_lineup.py

## 前提
- 目的に届く: 届くのは、人の承認 1 回で、夜の間に分けた子が承認されて回るところまで。子は直列で回るので、一晩に入る本数は増えない（M の 1 本は約 100 分）。相談役が否と言うか、検証で反証が出た子は discovery のまま残り、親は朝まで done にならない。`--goal` の後に main が子を作らずに止まると、親は discovery なので Stop hook は止めず、朝まで何も回らない
- 運用: 人は寝る前に目的の spec を 1 回承認する。main が commands の手順どおりに子を作って回し、朝の報告で子ごとの approved_by と、`autopilot.py goal` の結果を人に示す。子を作らずに止まる失敗は Stop hook で止めず、最初の 3 回の `--goal` の夜で、朝の goal の結果（子の無い要件の数）を数えてから止め方を決める
- 普通のやり方: なし（大きい変更を塊の PR に分けるのは stacked PR の作り方で、この repo の A の 3 の L の項にある。承認の単位と PR の単位を分ける決まった作り方は無い）
- 過去: A の 3 の L の項は、L のまま 1 本の PR にした spec で plan のコメントが GitHub に入りきらずにレビューできなくなり、人が分割と stacked PR を指示した事例から入れた。人の発言（目的の 4 つ目）で、承認の単位と PR の単位を分けると決めた
- 前提: 初回の合意（discovery・queued）で、申告か数えた大きさが L の spec を lint が ERROR にする。L の ERROR は 3 か所で出て、lint に L を外す引数は無い
  - path: plugins/spec-autopilot/scripts/autopilot.py:549-550
  - path: plugins/spec-autopilot/scripts/autopilot.py:594-611
- 前提: Stop hook は phase が discovery の spec を放し、building のほかの知らない phase は読めないものとして止める
  - path: plugins/spec-autopilot/hooks/stop.py:49-64
- 前提: check は phase が building・done でない spec を ERROR にする
  - path: plugins/spec-autopilot/scripts/autopilot.py:657-661
- 前提: `--queue` の承認は queued にし、`lineup.py next` が承認の順に着手する
  - path: plugins/spec-autopilot/scripts/lineup.py:64-70
- 前提: 2026-11-26-advisor-reapproval は、相談役の条件の判定を、phase と自走の範囲の判定と別の関数にして advisor_approval.py に置く（その spec の `--by-advisor` は discovery の spec を ERROR にするので、子の承認はその関数だけを呼ぶ）
  - path: docs/specs/2026-11-26-advisor-reapproval/spec.md:15
  - path: docs/specs/2026-11-26-advisor-reapproval/spec.md:31

## 作り方
この spec の ADR のとおり、親は phase を discovery のまま置き、目的として承認した記録を state.json に残す。子は、その記録と相談役の 2 段の記録を合わせて承認する。

- `goal.py` に、`--goal` の承認（L を止めない lint の呼び方と、記録の書き込み）、子の承認の条件（親の記録・自走の範囲の節のハッシュ・`- 親の要件:` の番号）、`goal` の subcommand（受け持ちの表と親の done）を置く
- 親の記録は、承認の時刻・`--by` の要約・`## 自走の範囲` の節のハッシュ（2026-11-26-advisor-reapproval と同じハッシュの取り方）を、state.json の 1 つのキーに入れる。phase を新しく足さない（Stop hook・SessionStart・status・check が知らない phase を読めないものとして扱うため）
- 相談役の条件（fable-advisor の最後の返答の `承認: 可` の行と、その後に起動した advice-checker の `判定: 反証なし（確かめられない 0 / <n>）` の行）は、advisor_approval.py の判定の関数をそのまま呼ぶ（同じ形を 2 か所に書かない）
- 子は `--queue` だけで承認する（行列に入れ、`lineup.py next` で回す）。子どうしの順は、承認の順と `- 依る spec:` で決める
- 親の done は、cmd_done と同じく done_at を書き、release し、runlog に done の行を書く（親には approved_at が無いので、runlog か done の表示が approved_at を読むなら、目的の承認の時刻を使う）
- scripts/autopilot.py は 1500 行を超えない（cmd_approve の分岐は goal.py の関数を呼ぶだけにし、足りなければ承認の門のまわりを advisor_approval.py へ移す）

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | 一時の repo で、変えるファイルを 6 つ以上書いた spec を作り、人の発言を記録して `approve --goal` を打つ。`--goal` なしでも打つ。その後に `overnight.py dispatch` と Stop hook を当てる | `--goal` では目的の承認の記録が残り、phase は discovery のまま。`--goal` なしでは L の ERROR。dispatch は承認されていないと拒み、Stop hook は放す |
| R2 | 手元で実物 | R1 の親に対して、`- 親 spec:` と `- 親の要件:` を書いた子を init し、fable-advisor と advice-checker の起動の記録を host の置き場の形で置いて `approve --queue --by-advisor` を打つ | 子が queued になり、approved_by が `相談役（fable-advisor・advice-checker 反証なし）: ` で始まる |
| R3 | 手元で実物 | R2 から 1 つずつ欠く（親が無い、親が目的として承認されていない、自走の範囲の節が違う、親に無い要件の番号、`承認: 否`）入力で打つ | どれも ERROR で、欠けた条件を挙げ、子は discovery のまま |
| R4 | 手元で実物 | R2 の子を done にした場合と、1 本を queued のまま残した場合と、親の要件を 1 つ受け持たない場合に `autopilot.py goal` を打つ | 全部 done で全部の要件を受け持つときだけ親が done になり、ほかは子の無い要件と done でない子を挙げて ERROR |
| R5 | 手元で実物 | commands の A の 3 の L の項を読み、R1〜R4 の subcommand と引数の名前を、argparse の定義と突き合わせる | 手順の subcommand と引数が argparse の定義と同じ |
| R6 | 手元で実物 | plugin.json の version を読み、`python3 -m pytest plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py -q` を回す | version が上がり、テストが通る |

## 制約
- 予算: 90 分
- 大きさ: M
- playbook: feature
- 依る spec: 2026-11-26-advisor-reapproval
- 脅威: 事故だけ（main が人の承認の無い子を回すこと、子の自走の範囲を親より広げること）。agent が subagent の記録を偽造する形は想定しない

## モデル
- 実装: sonnet-high

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
