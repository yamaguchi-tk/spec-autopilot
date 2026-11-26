# 夜の間の承認し直しを、相談役の推奨と検証で通す

- ADR: docs/adr/2026-11-26-advisor-reapproval.md

## 目的
人の発言（順に）:「複数Specになるときに朝までに実装完了させることができないのは欠陥」「specの度に人間の承認が必要で夜中回すことが出来ない」「基本相談役のFableが人間の代わりでいい　価値観を追加しているはず」「承認の単位とPRの単位を切り離す　で途中の承認はFableでよい」「Fableの直しの裏取りしたら間違っていたことも複数あるので裏取りはして欲しい」。

観測した失敗: 全 repo の runs.jsonl の 26 件のうち block は 4 件で、4 件とも理由は「承認し直しが要る」だった（spec の前提の取り違え、承認済みの workflow 名の誤り、人が要件を足すと決めた、合意し直しの記録）。今は `autopilot.py approve` が人の発言（transcript の origin が human の行）を求めるので、夜の間に承認し直しが要ると、その spec と、それに依る spec が朝まで止まる。

できあがったら、人が一度承認した spec の承認し直しは、夜の間に、fable-advisor が価値観で決め、advice-checker が根拠の反証を探して、反証が無いときだけ通る。通らなければ、その spec は朝まで block のまま残り、行列の次の spec に進む。人の初回の承認は今のまま残る。

## 要件
- R1: phase が blocked で、最後の承認（`--queue` を含む）のときの `## 自走の範囲` の節が記録されている spec で、`autopilot.py approve <dir> --by "<要約>" --by-advisor` を打ったとき、spec.md の最後の変更（block の後ならその時刻）より後に、このセッションで fable-advisor が起動し、その後に advice-checker が起動していて、fable-advisor の最後の返答に `承認: 可` の行があり、advice-checker の最後の返答に `判定: 反証なし（確かめられない 0 / <n>）` の行があれば、approve は承認を記録して自走に戻し、approved_by に `相談役（fable-advisor・advice-checker 反証なし）: <要約>` を書く。
- R2: R1 の条件のどれかが欠けたとき（どちらかの起動の記録が無い・読めない、advice-checker の起動が fable-advisor の起動より前、`承認: 否`、`承認:` の行が無い、`反証あり`、確かめられない が 1 以上）、approve は ERROR で終わり、欠けた条件を挙げ、spec は blocked のまま残る。
- R3: phase が discovery か queued の spec（初回の合意）か、最後の承認のときと今の spec.md で `## 自走の範囲` の節の中身が違う spec か、最後の承認のときの節の記録が無い spec で `--by-advisor` を打ったとき、approve は人の返事が要ると言って ERROR で終わる。
- R4: agents/fable-advisor.md の出力に、承認し直しの相談のときだけ `承認: 可` か `承認: 否` の 1 行を書く欄がある。commands/autopilot.md の「人に戻るとき」に、夜の間（人の返事を待てないとき）に承認し直しが要るなら、fable-advisor → advice-checker の 2 段を回してから `approve --by-advisor` を打ち、通らなければ block のまま `lineup.py next` で次の spec に進み、通った巡は approved_by を朝の報告（done の後の人への報告）に 1 行書く手順がある。
- R5: plugins/spec-autopilot/.claude-plugin/plugin.json の version を上げ、marketplace の description は plugin.json と同じに保つ。

## 非目標
- 初回の承認（discovery・queued）を相談役で代えること（人の承認 1 回は残す）
- 目的の spec を塊の spec に分けること（別の spec: 2026-11-26-goal-split）
- 自走の範囲を広げる承認し直し（範囲の外の操作は今までどおり park に積む）
- 相談役の推奨を main が自分で検証すること
- `overnight.py report` に相談役で承認した巡を出すこと（main が人への報告に書く）
- fable-advisor と advice-checker の最後の返答が同じ推奨を指すかを突き合わせること（起動の順だけを見る）
- 承認の検査を敵対的な書き換え（agent が subagent の記録を偽造する）から守ること

## 影響範囲
- 変える: plugins/spec-autopilot/scripts/autopilot.py:930-963（cmd_approve）
  - メモ: 945-955 の「いつより後の承認か」の計算を新しいモジュールへ移し、ここは呼び出しと引数だけにする
- 新規: plugins/spec-autopilot/scripts/advisor_approval.py
- 変える: plugins/spec-autopilot/agents/fable-advisor.md（全体）
  - メモ: 出力の節（74-86 行）に承認の欄を足すだけ
- 変える: plugins/spec-autopilot/commands/autopilot.md（全体）
  - メモ: 「人に戻るとき」（130 行目から）に夜の間の手順を足すだけ
- 変える: plugins/spec-autopilot/.claude-plugin/plugin.json（全体）
  - メモ: version の行だけ
- 呼び出し元: plugins/spec-autopilot/scripts/autopilot.py:1462-1465
  - メモ: approve の引数
- 別の実装: plugins/spec-autopilot/scripts/autopilot.py:250-277
  - メモ: require_user_after。人の発言の門
- 別の実装: plugins/spec-autopilot/scripts/overnight.py:831-871
  - メモ: launches・read_launch。subagent の起動の記録を読む（返答の文は読まない）
- 別の実装: plugins/spec-autopilot/scripts/lineup.py:64-100
  - メモ: enqueue・begin・block。承認と block を state.json に書く。変えない
- 手本: plugins/spec-autopilot/tests/test_autopilot.py:1144（test_approve_after_block_needs_new_user_prompt）
- 同じ入力: history、blocked、CLAUDE_CODE_SESSION_ID
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/ -q -n auto
  - メモ: approve を呼ぶテストが 11 ファイルにあるので全体を回す

## 変えない挙動
- block の後の承認は、人の新しい発言を求める（--by-advisor を付けないとき）: plugins/spec-autopilot/tests/test_autopilot.py::test_approve_after_block_needs_new_user_prompt
- block の後の承認で、spec を記録し直す: plugins/spec-autopilot/tests/test_autopilot.py::test_approve_after_block_records_the_spec_again
- 承認し直しは、新しいレビューを求める: plugins/spec-autopilot/tests/test_autopilot.py::test_reapproval_requires_a_new_review

## 前提
- 目的に届く: 届くのは、人が一度承認した spec の承認し直しで夜が止まらなくなるところまで。夜の間に新しく生まれた spec（分割・後続）の承認は 2026-11-26-goal-split で扱う。相談役が否と言うか、検証で反証が出た承認し直しは、朝まで止まる。直列で回すので、一晩に入る本数は増えない
- 運用: main が、夜の間に承認し直しが要ると分かったときに、commands の手順どおりに相談役 2 本を回して `approve --by-advisor` を打つ。朝の報告で、人が相談役の承認を読み直す
- 普通のやり方: なし（agent の承認の代わりを別の agent に検証させる仕組みに、決まった作り方は無い。この repo の相談役の 2 段の規則に合わせる）
- 過去: 相談役の 2 段（fable-advisor の推奨を advice-checker が検証する）は SessionStart の規則にある。人の発言の門は、agent が事故で自分を承認し直すのを止めるために入れた（hooks/user_prompt.py の docstring）。人の発言（目的の 5 つ目）で、Fable の直しは裏取りで誤りが複数見つかったので、検証を外さない
- 前提: approve は、spec.md の最後の変更（block の後ならその時刻）より後に、transcript の origin が human の行が無いと止まる
  - path: plugins/spec-autopilot/scripts/autopilot.py:250-277
  - path: plugins/spec-autopilot/scripts/autopilot.py:947-958
- 前提: approve は phase が discovery・blocked・done の spec だけを受け、block の後の承認は lineup の begin が前の巡を history に移す
  - path: plugins/spec-autopilot/scripts/autopilot.py:942-944
  - path: plugins/spec-autopilot/scripts/lineup.py:73-90
- 前提: このセッションで起動した subagent の agent の名前と起動の時刻は、host が書く meta.json と transcript から読める
  - path: plugins/spec-autopilot/scripts/overnight.py:831-871
- 前提: subagent の返答は、transcript の最後の assistant の行の、text の文か SubagentHandback の tool_use の `input.message` に入る
  - コマンド: `find "$CLAUDE_CONFIG_DIR/projects" -path '*/subagents/*.meta.json'` → 見つけた相談役の実物の記録 4 本の最後の assistant の行は、2 本が SubagentHandback の input.message、2 本が text
- 前提: lineup の着手で block した spec（queued の後に spec.md を変えたなど）は approved_at を None にし、最上位に承認の記録を残さない
  - path: plugins/spec-autopilot/scripts/lineup.py:93-98
- 前提: advice-checker は `判定: 反証あり` か `判定: 反証なし` に続けて `（確かめられない <n> / <主張の数>）` を書く
  - path: plugins/spec-autopilot/agents/advice-checker.md:30-36
- 前提: fable-advisor の出力に、承認するかを返す欄は無い
  - path: plugins/spec-autopilot/agents/fable-advisor.md:74-86

## 作り方
この spec の ADR のとおり、承認の門に、人の発言の代わりとして「相談役 2 本の起動の記録」を受ける道を足す。

- `advisor_approval.py` に、spec.md の最後の変更（block の後ならその時刻）より後に起動した fable-advisor と advice-checker の、最後の返答を読む関数を置く。起動の記録は `overnight.launches` と同じ置き場（`<config>/projects/*/<session>/subagents/`）から読み、返答は transcript の最後の assistant の行の文から取る
- 判定は、`承認: 可` の行と、`判定: 反証なし（確かめられない 0 / <n>）` の行の両方があるときだけ通す（許可の形を 1 つに決め、ほかは全部止める）。行の先頭が `承認:` の行と `判定:` の行を、それぞれの最後の返答で数え、どちらもちょうど 1 本のときだけ判定に進む（0 本と 2 本以上は止める）。起動の記録の meta.json が読めないときも、transcript と同じく、spec.md の最後の変更より後に書かれたものなら止める
- approve は `--by-advisor` があるときだけこの判定を使い、無いときは今の人の発言の門のまま
- R3 の「自走の範囲の節が同じか」は、承認した時点の spec の中身を持っていないので、cmd_approve が門を通った後、`lineup.enqueue`・`lineup.begin` を呼ぶ前に、spec.md の `## 自走の範囲` の節のハッシュを s に入れる（enqueue・begin がそのまま save する。begin は history に移すキーを選ぶので、このキーは最上位に残る）。`--by-advisor` の判定は、その上書きの前に、s に残る前の値と突き合わせる。残っていない（この版より前に承認した）spec は、`--by-advisor` を受けない（lineup.py は変えない）。lineup の着手の block（approved_at が None になる）でも、この記録は残るので対象になる
- 返答は、最後の assistant の行の text の文か、SubagentHandback の tool_use の `input.message` から取る（実物の記録で両方の形を見た）
- scripts/autopilot.py は 1500 行を超えない（今 1498 行。cmd_approve の 945-955 を新しいモジュールへ移して空ける）
- 相談役の条件の判定（起動の順と 2 つの行）は、phase と自走の範囲の判定と別の関数にする（2026-11-26-goal-split が子の承認でこの関数だけを呼ぶ）
- `overnight.py report` は変えない（変えるファイルを 5 本に収める。相談役で承認した巡は、main が人への報告に書く）

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | 一時の repo で spec を承認し、block してから spec.md を直し、fable-advisor と advice-checker の起動の記録（meta.json と transcript）を host の置き場の形で置いて `approve --by-advisor` を打つ。あわせて、手元の host の置き場にある実物の fable-advisor・advice-checker の記録（text の形と SubagentHandback の形を 1 本ずつ）に返答を読む関数を当てる | 自走（building）に戻り、approved_by が `相談役（fable-advisor・advice-checker 反証なし）: ` で始まる。実物の記録から最後の返答の文が取れる |
| R2 | 手元で実物 | R1 の記録から 1 つずつ欠く（fable-advisor が無い、advice-checker が無い、advice-checker が先に起動した、`承認: 否`、`承認:` が無い、`反証あり`、確かめられない 1、記録が spec.md の変更より前）入力で打つ | どれも ERROR で、欠けた条件を挙げ、phase は blocked のまま |
| R3 | 手元で実物 | discovery の spec、queued の spec、自走の範囲の節を変えた block の spec で `--by-advisor` を打つ | どれも ERROR で、人の返事が要ると出る |
| R4 | 手元で実物 | fable-advisor.md の出力の節と commands の「人に戻るとき」を読み、R1 のコードが読む `承認: 可` の形と突き合わせる | 定義の欄の形とコードが読む形が同じで、commands に 2 段と `--by-advisor` と `lineup.py next` と朝の報告の手順がある |
| R5 | 手元で実物 | plugin.json の version を読み、 `python3 -m pytest plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py -q` を回す | version が上がり、テストが通る |

## 制約
- 予算: 90 分
- 大きさ: M
- playbook: feature
- 脅威: 事故だけ（main が人の返事も相談役の検証も無いまま承認し直すこと）。agent が subagent の記録を偽造する形は想定しない

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
