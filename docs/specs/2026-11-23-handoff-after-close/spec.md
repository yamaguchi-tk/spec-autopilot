# 閉じた handoff の後の、dispatch の無い起動と main のコードを止める

- ADR: docs/adr/2026-11-23-implementer-launch-gate.md

## 目的
`overnight.py handoff` は、閉じた後に dispatch を打たずに起動した実装役と、閉じた後に main が書いたコードを見分けない（Issue #2）。ユーザーは「いま直す」を選んだ。できあがったら、閉じた後の 2 つの形は、dispatch の打ち忘れや main の書き込みという事故のまま評価役に届かず、起動の時点か handoff で止まる。

## 要件
- R1: 実装役（subagent_type の名前の最後の `:` の後が `autopilot-implementer` で始まる）を Agent で起動するとき、PreToolUse hook は、prompt に書かれた spec のディレクトリ（state.json があるもの）のうち、次の 3 つ（phase が building、最後の dispatch を閉じた handoff が無い、その dispatch の agent が起動する名前と同じ）をすべて満たすものが 1 つも無ければ、deny し、理由に `overnight.py dispatch` を打ってから起動するよう書く。
- R2: prompt に spec のディレクトリが無い・state.json が読めない・判定の途中で例外が出たときも、R1 の hook は deny し、理由にそのことを書く。hook のスクリプトが答えを出さずに終わった（import の失敗・終了コード 0 以外）ときも、hooks.json の command（`python3 <agent_gate.py> || <deny を出す printf>` の形）が deny を出す。prompt の相対パスは payload の cwd から引く。
- R3: R1 の 3 つをすべて満たす spec が 1 つでもあれば、R1 の hook は何も出さずに終わる（同じ dispatch の間の起動し直し、lineup で別の spec の dispatch に従う起動を含む）。実装役でない agent の起動では、state を読まずに何も出さない。
- R4: `overnight.py handoff` で最後の dispatch が閉じていて HEAD が閉じたときの tip と違うとき、spec のファイルの外で、閉じた tip と今の HEAD で中身が違うファイルから、統合先が変えたファイルを除いたものが 1 つでもあれば、handoff は拒み、そのファイルの名前と、閉じた tip に戻して commit するか dispatch から実装役に直させるよう出す。統合先が変えたファイルは、手元と remote のブランチのうち、今のブランチ・その upstream・名前が今のブランチと同じ remote のブランチ・閉じた tip か今の HEAD を含むブランチを除いたものごとに、閉じた tip と今の HEAD の merge-base から、今の HEAD とそのブランチの merge-base まで（前者が後者の祖先のときだけ）の差分に出るファイルとする。
- R5: 閉じた後の rebase（手元か remote の統合先の上）、統合先の merge、spec のファイルだけを変える commit・amend の後は、R4 で拒まない。
- R6: 閉じたときの tip が repo に無い（読めない）とき、handoff は拒み、そのことを出す。
- R7: `commands/autopilot.md` の C の 3 の handoff の項と、`overnight.py` の冒頭の使い方の handoff の行・handoff と launch_errors の docstring は、閉じた後の 2 つの形を見分けるようになったことと、見分けない残り（統合先も変えたファイルへの main の書き込み）を書き、README の hook の表に R1 の hook の行を足す。
- R8: hooks.json は PreToolUse に R1 の hook を、Agent と Task の tool に当たる matcher で登録する。この plugin を読み込んだ Claude Code で、開いた dispatch の無い spec を prompt に書いて実装役を起動させると、起動は deny され、実装役は動かない。

## 非目標
- 統合先も変えたファイルに、閉じた後に main が書いたコードを見分けること（rebase の衝突の解消と区別できない）
- わざと避ける形（prompt に別の spec を書く、state.json を書き換える、統合先のブランチに書いて取り込む）
- この spec の変更を載せ替えた写しを持つ、ほかの名前のブランチ（R4 は統合先として数え、そこで変えたファイルへの main の書き込みを見分けない）
- 定義と違う model が書いた commit を handoff が取り除くこと（戻すのは今の手順書の main の手順）

## 影響範囲
- 変える: plugins/spec-autopilot/scripts/overnight.py:758-821（launch_errors、cmd_handoff）
  - メモ: 8-10 行目の冒頭の使い方の handoff の行も直す
- 新規: plugins/spec-autopilot/hooks/agent_gate.py
- 新規: plugins/spec-autopilot/tests/test_agent_gate.py
- 変える: plugins/spec-autopilot/hooks/hooks.json（全体）
- 変える: plugins/spec-autopilot/commands/autopilot.md（全体）
  - メモ: 91 行目の handoff の項だけ
- 変える: plugins/spec-autopilot/README.md（全体）
  - メモ: hook の表に 1 行を足すだけ
- 呼び出し元: plugins/spec-autopilot/scripts/overnight.py:1197
- 呼び出し元: plugins/spec-autopilot/scripts/overnight.py:460-470
  - メモ: review_gate が閉じた handoff を求める
- 別の実装: plugins/spec-autopilot/scripts/overnight.py:434-446
  - メモ: review_errors がレビュー後のコードの変更を見る
- 手本: plugins/spec-autopilot/hooks/user_prompt.py:22-41（payload の読み方）
- 手本: plugins/spec-autopilot/hooks/stop.sh:1-18（全体）
  - メモ: 答えを出さずに終わったときの扱い（hooks.json の command に書く）
- 手本: plugins/spec-autopilot/scripts/autopilot.py:456-475（main_only。統合先が変えたファイルの数え方）
- 手本: plugins/spec-autopilot/tests/test_overnight.py:683（test_handoff_passes_after_a_rebase）
- 同じ入力: dispatches、handoffs、SPEC_FILES
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_overnight.py plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py plugins/spec-autopilot/tests/test_stop_bounds.py plugins/spec-autopilot/tests/test_lineup.py plugins/spec-autopilot/tests/test_agent_gate.py -q

## 変えない挙動
- 閉じた後の rebase の後に handoff が通る: plugins/spec-autopilot/tests/test_overnight.py::test_handoff_passes_after_a_rebase
- 開いた dispatch で別の段の実装役を拒む: plugins/spec-autopilot/tests/test_overnight.py::test_handoff_refuses_an_implementer_of_another_rung
- hooks.json が指すスクリプトがある: plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py::test_hooks_json_points_to_existing_scripts

## 前提
- 目的に届く: 起動の入口の hook は、plugin を入れ直した後に始めたセッションでしか効かない。統合先も変えたファイルへの main の書き込みは残る。Issue #2 の 2 つの形は、実際の run では 1 本・起動 4 回で 0 件で、効果は件数では確かめられない
- 運用: /autopilot の main が、今までどおり dispatch → 実装役 → handoff の順に打つ。hook に止められたら、理由のとおり dispatch を打ち直す
- 普通のやり方: Claude Code の PreToolUse hook で tool の呼び出しを deny するのは、hook で手順を強制する普通の形
  - メモ: Claude Code の hooks の文書（docs.claude.com の claude-code/hooks）の PreToolUse の permissionDecision
- 過去: 閉じた後の起動を拒む形を入れて（322a700）取り下げた（57802c8）。セッションで数える形と、履歴で数える形は、amend・adopt・lineup で抜けるか誤って拒んだ（Issue #2 の本文）
- 前提: handoff は、最後の dispatch が閉じていて HEAD が違うと、増分も起動も見ない
  - path: plugins/spec-autopilot/scripts/overnight.py:785-829（cmd_handoff）
- 前提: dispatch は agent の名前を state.json の dispatches に書き、handoff は閉じた dispatch の番号と tip を handoffs に書く
  - path: plugins/spec-autopilot/scripts/overnight.py:667-681（cmd_dispatch）
  - path: plugins/spec-autopilot/scripts/overnight.py:819-820（cmd_handoff）
- 前提: マージの前の rebase は、既定のブランチの上で行う
  - path: plugins/spec-autopilot/references/after-pr.md:17
- 前提: /autopilot の手順は、実装役に spec のディレクトリを渡す
  - path: plugins/spec-autopilot/commands/autopilot.md:88
- 前提: Claude Code は subagent の起動を tool の名前 Agent で呼び、入力は subagent_type・prompt・description・run_in_background を持つ
  - コマンド: `このセッションの transcript で autopilot-implementer を起動した tool_use を数える` → 4 件、名前はすべて Agent、入力のキーは description・prompt・run_in_background・subagent_type
- 前提: PreToolUse の payload は tool_name・tool_input・cwd を持ち、hook が permissionDecision の deny を返すと tool は動かない
  - 未確認: repo の外の Claude Code の振る舞いで、R8 の QA で実物で確かめる
- 前提: 今の hooks.json に PreToolUse は無い
  - path: plugins/spec-autopilot/hooks/hooks.json:1-38

## 作り方
この spec の ADR のとおり、dispatch の無い起動は Agent の PreToolUse hook（新しい `hooks/agent_gate.py`）で起動の入口で止め、閉じた後の main のコードは handoff の閉じた側の道で、ファイルの中身を閉じた tip と比べて見分ける。prompt の spec のパスは、docs/adr/2026-11-24-spec-path-anchored-on-dir-name.md のとおり、`docs/specs/<日付>-<slug>` の名前を手がかりにして、その前の `/`・`~/` と payload の cwd から候補を作り、stat で確かめて引く。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | 一時の repo で dispatch・handoff まで回した spec と、dispatch の無い spec に対し、hook のスクリプトに Agent の PreToolUse の payload を stdin で渡す | 閉じた dispatch・dispatch の無い spec・別の段の名前で、permissionDecision が deny になり、理由に dispatch がある |
| R2 | 手元で実物 | prompt に spec のディレクトリが無い payload、state.json が壊れた spec、JSON でない stdin を渡す。hooks.json の command を、python のスクリプトを import できない形に差し替えて起動する | どれも deny で、終了コードが 0 |
| R3 | 手元で実物 | 開いた dispatch の spec、別の spec が開いた dispatch を持つ prompt、実装役でない agent の payload を渡す | 出力が空で終了コードが 0 |
| R4 | 手元で実物 | 閉じた後に spec の外のファイルを変えて commit してから handoff を回す | 終了コードが 0 以外で、そのファイルの名前が出る |
| R5 | 手元で実物 | 閉じた後に、手元の統合先の上への rebase・統合先の merge・spec のファイルだけの amend をしてから handoff を回す | どれも終了コードが 0 |
| R6 | 手元で実物 | state.json の閉じた tip を repo に無い sha にしてから、HEAD を動かして handoff を回す | 終了コードが 0 以外で、tip が読めないと出る |
| R7 | 手元で実物 | 3 つの文書の該当の箇所を読む | 見分ける 2 つの形と残りの形、README の hook の行がある |
| R8 | 手元で実物 | headless の `claude -p --plugin-dir <この worktree の plugin>` で、dispatch の無い一時の spec のディレクトリを prompt に書いて spec-autopilot:autopilot-implementer を起動させ、出力と transcript を読む | 起動が deny され、理由に dispatch がある。実装役の subagent の記録が無い |

## 制約
- 予算: 90 分
- 大きさ: M
- playbook: feature
- 想定する脅威: 事故（dispatch の打ち忘れ、閉じた後に main がコードを書く）。わざと避ける形は想定しない

## モデル
<!-- 書かなければ既定（実装 sonnet-low・評価 opus-high）。始めから上げる役だけ書く。実装: sonnet-low・sonnet-high・opus-medium・opus-xhigh・fable、評価: opus-high・opus-xhigh・fable（評価は既定より下げない） -->

## 自走の範囲
<!-- 必須（`CLI lint` が求める）。6 行とも消さない。`- 範囲:` は「マージ・デプロイ・QA まで」（既定）・「マージまで」・「PR まで」のどれか。
「マージ・デプロイ・QA まで」では、ほかの 5 行も空にできない（QA の環境・QA の書き込み先は人しか知らないことが多いので、壁打ちで聞く）。
デプロイの起動は「マージで自動」か「コマンド: <1 行のコマンド>」のどちらか（ほかは lint が ERROR。コマンドなら lint が NOTE を出し、承認の前に人に示す。コマンドの起動を park に積んだマージは、本番を変えていないものとして数える）。デプロイの確かめは、待つ workflow の名前を `、` で並べる。
ロールバックは「revert の PR をマージし、デプロイの完了を確かめる」（既定）か「コマンド: <1 行のコマンド>」のどちらか（ほかの形は lint が ERROR にする。夜の間はこの宣言どおりの戻し方だけを受ける）。マージ後の直しの巡に別の予算を持たせるなら「## 制約」に `- マージ後の予算: <分> 分`（無ければ予算と同じ）。
通知は朝の報告の知らせ方で、デスクトップ・Slack の DM・なしのどれか（無ければなし）。`- AWS の profile:` は AWS SSO で操作する spec なら profile の名前、使わないなら「なし」（承認の lint が、見込みの夜の終わりまで SSO が切れないかを見る）。範囲が「マージ・デプロイ・QA まで」なら、デプロイの起動は空にできず、起動がコマンドでデプロイ後の要件も無いとき以外は、デプロイの確かめ（待つ workflow の名前を `、` で並べる）も空にできない -->
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
