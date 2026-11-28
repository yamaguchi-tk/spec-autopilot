# setup でセッション単位の上書きを既定の上に重ねる（3 本目）

- ADR: docs/adr/2026-11-28-role-model-setup-session.md

## 目的
人は「セッション単位で変えられるのと　デフォルト値と両方あるのが理想」と言った（役ごとの model・effort について）。1 本目（docs/specs/2026-11-28-role-model-setup-advisors）と 2 本目（docs/specs/2026-11-28-role-model-setup-command）で、手元の既定（models.md）から 5 つの役の段を選べる。この spec は、その上にセッション単位の上書きを重ねる。できあがると、利用者は既定を残したまま、今のセッションだけ役の段を変えられる。

## 要件
- R1: `ladder.py setup --session` に役の段（`--impl`・`--review`・`--advisor`・`--checker`・`--spec-checker`）を付けて実行したとき、ladder.py は今のセッションの上書きを書き（渡していない役の行は残す）、既定は変えず、書いたファイルのパスと中身を出す。相談・検証・照合の上書きは、今のセッションで使う agent の読み替えの行も出す。実装・評価の上書きは、そのセッションで後から init する spec にだけ効く（R5）。
- R2: 今のセッションが分からない（id が無いか、既存のセッション id の形に合わない）とき、`setup --session` は 0 以外で終わり、どのファイルも変えない。受けない段は今の setup と同じく断る。`--session --reset [役]` はセッションの上書きだけを消す。
- R3: 役ごとの段は、セッションの上書き → 手元の既定 → 同梱の既定の順で決まる。`ladder.py show` は役ごとに、既定の設定の段に加えて「このセッション」の段（無ければ「なし」）を出す。
- R4: セッションの上書きがある間に始まり直したセッション（compaction・resume）で main が受け取る読み替えの指示は、R3 の順で決めた段で作られる。上書きのファイルが読めないか、payload の id がセッション id の形に合わないときは、既定の段で作る（読めないファイルには直し方を 1 行出す）。
- R5: セッションの上書きのある実装・評価の段は、そのセッションで `autopilot.py init` が作る spec の `## モデル` に、既定より優先して写る。作った後の spec は変わらない。
- R6: `commands/setup.md` は、選んだ段を既定に書くか今のセッションだけに書くかを人に選ばせる手順を持ち、README の setup の節にセッション単位の上書きと優先の順を書く。

## 非目標
- 既定（models.md）を変えたときに、今のセッションで効かせること（既定は次のセッションから。1 本目の前提のまま）
- 終わったセッションの上書きのファイルの掃除
- 作った後の spec への反映、repo ごとの設定、版数を上げること

## 影響範囲
- 変える: plugins/spec-autopilot/scripts/ladder.py（全体）
  - メモ: 読み方を 1 つの関数にまとめ、セッションの層を足す
- 変える: plugins/spec-autopilot/hooks/session_start.py（全体）
  - メモ: ADVISE の文は変えない。読み替えの行を作る所にセッションの id を渡すだけ
- 変える: plugins/spec-autopilot/commands/setup.md（全体）
- 変える: plugins/spec-autopilot/README.md（全体）
- 呼び出し元: plugins/spec-autopilot/scripts/autopilot.py:906
- 呼び出し元: plugins/spec-autopilot/hooks/hooks.json:43
- 手本: plugins/spec-autopilot/tests/test_ladder_setup.py:1
- 同じ入力: models.md、CLAUDE_CODE_SESSION_ID
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_watch.py plugins/spec-autopilot/tests/test_lineup.py plugins/spec-autopilot/tests/test_ladder.py plugins/spec-autopilot/tests/test_ladder_setup.py plugins/spec-autopilot/tests/test_init_models.py plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py plugins/spec-autopilot/tests/test_advisor_approval.py plugins/spec-autopilot/tests/test_autopilot.py -q -n auto

## 変えない挙動
- init が models.md の行を spec に写す: plugins/spec-autopilot/tests/test_init_models.py
- init が discovery の spec を作る: plugins/spec-autopilot/tests/test_autopilot.py::test_init_creates_artifacts_in_discovery

## 前提
- 目的に届く: 上書きが効くのは、そのセッションの読み替えの指示と、そのセッションで init した spec だけ。main が指示に従わず既定の agent を起動しても機械では止めない（1 本目と同じ）
- 運用: 利用者が `/spec-autopilot:setup` で「このセッションだけ」を選ぶ。セッションが終われば上書きは使われなくなる（ファイルは残る）
- 普通のやり方: pstack の `/setup-pstack` は規則ファイル 1 つで、セッション単位の上書きは持たない（https://github.com/backnotprop/pstack/blob/main/skills/setup-pstack/SKILL.md）。Claude Code の設定は user・project・local の層を重ね、狭い層が勝つ。この spec はその重ね方に合わせる。手順との対応: 今の設定を読む → R3。役ごとに選ぶ → R6。書き出す → R1。行を消すと既定 → R2。置き方は、同じ置き場の `sessions/<id>.host.json`（plugins/spec-autopilot/scripts/watch.py:9）と同じく id ごとの別ファイルにする
- 過去: 1 本目・2 本目（この日に承認）が既定の層と 5 つの役を作る
- 前提: Bash の中では `CLAUDE_CODE_SESSION_ID` で今のセッションの id が取れ、SessionStart の payload の `session_id` と同じ値である
  - path: plugins/spec-autopilot/scripts/autopilot.py:206
  - path: plugins/spec-autopilot/hooks/stop.py:132
  - path: plugins/spec-autopilot/scripts/autopilot.py:1109（command 本文の Bash から打つ adopt が同じ変数を読む）
  - path: plugins/spec-autopilot/commands/autopilot.md:93（変数が無いことがある。そのときは R2 で断る）
- 前提: セッションごとの記録は手元の置き場の `sessions/<id>.json` に置く規約がある
  - path: plugins/spec-autopilot/scripts/autopilot.py:318
- 前提: compaction ではセッションの id が変わらず、/clear と fork では新しい id になる（上書きはそこで切れ、既定に戻る）
  - path: plugins/spec-autopilot/tests/test_autopilot.py:2411
  - path: plugins/spec-autopilot/tests/test_autopilot.py:2366
- 前提: セッション id は形を検査してからファイルの名前に使う
  - path: plugins/spec-autopilot/scripts/autopilot.py:103
  - path: plugins/spec-autopilot/scripts/autopilot.py:315

## 作り方
この spec の ADR のとおり。上書きのファイルは、`CLAUDE_CODE_SESSION_ID`（SessionStart では payload の `session_id`）を `autopilot.SESSION_ID` で検査してから、手元の置き場の `sessions/<id>.models.md` に置き、行の形・検査は models.md と同じ `ladder.lint` と段の表を使う。役ごとの段を決める関数を 1 つにし、show・write_spec・読み替えの行がそれを使う。SessionStart は payload の `session_id` を渡す。setup の command は AskUserQuestion で「既定に書く／このセッションだけ」を先に聞く。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | 一時の `SPEC_AUTOPILOT_HOME` と `CLAUDE_CODE_SESSION_ID` で `setup --session --advisor opus-high` を打ち、ファイルと models.md を読む | セッションのファイルに行があり、models.md は打つ前と同じで、出力に読み替えの行が出る |
| R2 | 手元で実物 | 環境変数を外して `setup --session --advisor opus-high`、続けて `--session --reset` | 前者は 0 以外で何も変わらず、reset はセッションのファイルだけを消す |
| R3 | 手元で実物 | 既定とセッションに違う段を書いて `show` | 役ごとにセッションの段が勝ち、両方の欄が出る |
| R4 | 手元で実物 | 同じ id の payload（source: compact）で session_start.py を回す。読めない上書きのファイルでも回す | 読み替えの行がセッションの段で出て、読めないときは既定の段と直し方が出る |
| R5 | 手元で実物 | 既定とセッションに違う実装の段を書いて init | spec の `## モデル` にセッションの段が写る |
| R6 | 手元で実物 | 評価役が commands/setup.md の手順のコマンドを一時の置き場で打ち、README を読む | 既定・セッションの選択があり、コマンドが通り、README に優先の順がある |

## 制約
- 予算: 60 分
- 大きさ: M
- playbook: feature
- 依る spec: 2026-11-28-role-model-setup-command
- hooks/session_start.py の ADVISE の文と commands/autopilot.md は変えない（並行の spec docs/specs/2026-11-28-fewer-advisor-calls が直している）

## モデル
<!-- 書かなければ既定（実装 sonnet-high・評価 opus-high）。始めから上げる役だけ書く。実装: sonnet-high・opus-medium・opus-xhigh・fable、評価: opus-high・opus-xhigh・fable（評価は既定より下げない） -->

## 自走の範囲
<!-- 必須（`CLI lint` が求める）。6 行とも消さない。`- 範囲:` は「マージ・デプロイ・QA まで」（既定）・「マージまで」・「PR まで」のどれか。
「マージ・デプロイ・QA まで」では、ほかの 5 行も空にできない（デプロイの起動が「なし（マージした commit で QA）」なら、デプロイの確かめだけは空にする。QA の環境・QA の書き込み先は人しか知らないことが多いので、壁打ちで聞く）。
デプロイの起動は「マージで自動」か「コマンド: <1 行のコマンド>」か「なし（マージした commit で QA）」のどれか（ほかは lint が ERROR。デプロイの workflow が無い repo は「なし（マージした commit で QA）」にし、デプロイの確かめを空にする。マージの記録が QA の起点になる。コマンドなら lint が NOTE を出し、承認の前に人に示す。コマンドの起動を park に積んだマージは、本番を変えていないものとして数える）。デプロイの確かめは、待つ workflow の名前を `、` で並べる。
ロールバックは「revert の PR をマージし、デプロイの完了を確かめる」（既定）か「コマンド: <1 行のコマンド>」のどちらか（ほかの形は lint が ERROR にする。夜の間はこの宣言どおりの戻し方だけを受ける）。マージ後の直しの巡に別の予算を持たせるなら「## 制約」に `- マージ後の予算: <分> 分`（無ければ予算と同じ）。
通知は朝の報告の知らせ方で、デスクトップ・Slack の DM・なしのどれか（無ければなし）。`- AWS の profile:` は AWS SSO で操作する spec なら profile の名前、使わないなら「なし」（承認の lint が、見込みの夜の終わりまで SSO が切れないかを見る）。範囲が「マージ・デプロイ・QA まで」なら、デプロイの起動は空にできず、起動がコマンドでデプロイ後の要件も無いときと、起動が「なし（マージした commit で QA）」のとき以外は、デプロイの確かめ（待つ workflow の名前を `、` で並べる）も空にできない -->
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
