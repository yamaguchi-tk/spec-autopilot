# 自走の結果を、読む時点まで残る記録に書く

- ADR: docs/adr/2026-11-23-run-log-outside-the-repo.md

## 目的
この plugin 自身の開発の進め方（CLAUDE.md「この plugin 自身を直すときの進め方」）は、`/autopilot` で回した最初の 5 本で、承認からの分数・blocked の回数と理由・マージ後の手戻りの PR の数を読むと決めた。今の仕組みでは、その 3 つが読む時点まで残らない（Issue #6）。できあがったら、5 本を回した後に 1 つのファイルを読めば、3 つの値がそろう。

## 要件
- R1: `CLI done` が done にしたとき、`CLI` は `SPEC_AUTOPILOT_HOME`（無ければ `~/.claude/spec-autopilot`）の `runs.jsonl` に 1 行の JSON を追記する。キーは `kind`（`done`）・`at`（unix 秒）・`spec`（spec のディレクトリ名）・`repo`（repo の root の絶対パス）・`active_min`（承認から done までの分。確認待ちを除き、巡ごとに足す）・`total_min`（着手から done までの分）・`size`（spec の `- 大きさ:`）・`blocks`（これまでの block の `req` と `reason` の一覧）・`rework_of`（下の R4。無ければ null）・`prs`（state.json に記録したマージの PR 番号の一覧）。done にする前の phase がすでに done なら、行を足さない。
- R2: `CLI block` が blocked にしたとき、`CLI` は同じファイルに `kind` が `block` の 1 行を追記する。キーは R1 と同じで、`active_min` は承認から block までの分（確認待ち〔wait〕のまま block したら、その待ちの始まりまで）、`total_min` は着手から block までの分、`blocks` には今回の block も入れる。
- R3: `lineup.py next` が着手の時点で block にしたとき、`lineup.py` は R2 と同じ 1 行を追記する。この巡には承認が無いので、`active_min` は前の巡までの和（前の巡が無ければ null）にし、`blocks` には前の巡の block と今回の block を入れる。
- R4: spec の「## 制約」に `- 手戻り元: <spec のディレクトリ名>` の行があるとき、R1・R2 の記録の `rework_of` はその名前になる。行が無いときは null になる。
- R5: block の後や done の後に再承認したとき、`lineup.py` の begin は前の巡の `paused_sec` も history に移す。R1・R2 の `active_min` は、history の巡の行（`approved_at` を持つ行。wait の行は除く）ごとに、`approved_at` から、その巡の `done_at` か `blocked.at` までの秒から、その巡の `paused_sec`（無い古い行は 0）を引き、今の巡と足した値になる。
- R6: `runs.jsonl` に書けない（置き場がファイルである・書き込み権が無い）とき、`CLI done`・`CLI block`・`lineup.py next` は今までどおり終わり、書けなかったことを NOTE の 1 行で出す。
- R7: `commands/autopilot.md` の「マージ済みの PR の直しなら」の行は、新しい spec の「## 制約」に `- 手戻り元:` を書くよう指示し、CLAUDE.md の「この plugin 自身を直すときの進め方」の最後の項目は、読むファイルが `runs.jsonl` だと書く。

## 非目標
- 記録を読む CLI（`CLI runs` など）。読む形が決まってから足す
- 既にある spec の過去の done・block を、記録に書き戻すこと
- 記録の rotate・削除

## 影響範囲
- 変える: plugins/spec-autopilot/scripts/autopilot.py:988-1037（cmd_done、cmd_block）
- 変える: plugins/spec-autopilot/scripts/lineup.py:73-95（begin、block）
- 新規: plugins/spec-autopilot/scripts/runlog.py
- 変える: plugins/spec-autopilot/commands/autopilot.md（全体）
  - メモ: 110 行目の「マージ済みの PR の直しなら」だけ
- 変える: CLAUDE.md（全体）
  - メモ: 18 行目の最後の項目だけ
- 呼び出し元: plugins/spec-autopilot/scripts/autopilot.py:1452-1461
- 呼び出し元: plugins/spec-autopilot/scripts/lineup.py:139-224
- 呼び出し元: plugins/spec-autopilot/scripts/autopilot.py:960
  - メモ: cmd_approve が begin を呼ぶ（再承認の入口）
- 手本: plugins/spec-autopilot/scripts/autopilot.py:281-285（session_file。SPEC_AUTOPILOT_HOME の読み方）
- 手本: plugins/spec-autopilot/scripts/overnight.py:649-651（await の記録。追記だけの jsonl の書き方）
- 手本: plugins/spec-autopilot/tests/test_autopilot.py:852（test_done_passes_with_a_note_when_the_record_cannot_be_updated）
- 同じ入力: SPEC_AUTOPILOT_HOME、paused_sec
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_autopilot.py plugins/spec-autopilot/tests/test_lineup.py plugins/spec-autopilot/tests/test_rollback.py plugins/spec-autopilot/tests/test_overnight.py plugins/spec-autopilot/tests/test_anomalies.py -q

## 変えない挙動
- done・block の後に spec がセッションの記録から外れる: plugins/spec-autopilot/tests/test_autopilot.py::test_done_and_block_drop_the_spec_from_the_session_record
- セッションの記録を更新できないときも done は通る: plugins/spec-autopilot/tests/test_autopilot.py::test_done_passes_with_a_note_when_the_record_cannot_be_updated
- block の後の再承認で spec がセッションの記録に戻る: plugins/spec-autopilot/tests/test_autopilot.py::test_approve_after_block_records_the_spec_again

## 前提
- 目的に届く: 3 つの値は手元の 1 台に残る。別の Mac・別のアカウントで回した spec の記録は、その環境のファイルにしか残らない。手戻りの数は `- 手戻り元:` を書いた spec だけを数え、書き忘れは lint が検出しない。同じ spec の中の直し（マージ後の後続の PR）は `prs` の本数でしか分からない
- 運用: 人か agent が、5 本を回した後に `runs.jsonl` を `jq` で読む。承認からの分数は `kind` が done の行の `active_min`、blocked の回数と理由は `kind` が block の行（spec ごとの数と `blocks`）、手戻りの PR の数は `rework_of` が元の spec の名前の done の行の数と、元の spec の `prs` の 2 本目以降。ファイルは消さない限り残る
- 普通のやり方: CLI の実行の記録は、利用者の設定ディレクトリの下に追記だけのファイルで残すのが普通（この plugin も、セッションの記録を同じ置き場に置いている）
  - メモ: 手本は autopilot.py の session_file
- 過去: なし（この repo は 11-23 に切り出したばかりで、記録の置き場を変えた PR は無い）
- 前提: done は state.json に done_at を書き、承認からの分を approved_at と paused_sec から出す
  - path: plugins/spec-autopilot/scripts/autopilot.py:988-999（cmd_done）
- 前提: 再承認の begin は、paused_sec を history に移さずに 0 に戻し、approved_at を書き直す。begin を呼ぶのは cmd_approve と lineup.start
  - path: plugins/spec-autopilot/scripts/lineup.py:73-86（begin）
  - path: plugins/spec-autopilot/scripts/autopilot.py:960（cmd_approve）
  - path: plugins/spec-autopilot/scripts/lineup.py:154（start）
- 前提: history には巡の行のほかに、resume が wait の行（phase が wait）を足す
  - path: plugins/spec-autopilot/scripts/autopilot.py:1062（cmd_resume）
  - path: plugins/spec-autopilot/scripts/lineup.py:189-191（resume）
- 前提: 確認待ちの時間が paused_sec に入るのは resume のときだけで、wait のまま block するとその待ちは入らない
  - path: plugins/spec-autopilot/scripts/autopilot.py:1050（cmd_wait）、plugins/spec-autopilot/scripts/autopilot.py:1063（cmd_resume）
- 前提: queued のまま着手の時点で block になる spec には、その巡の approved_at が無い
  - path: plugins/spec-autopilot/scripts/lineup.py:64-70（enqueue）
- 前提: cmd_done は phase を見ないので、done の spec にもう一度回せる
  - path: plugins/spec-autopilot/scripts/autopilot.py:988-996（cmd_done）
- 前提: 「## 制約」の、lint が知らない行は、lint が ERROR にしない
  - コマンド: `制約に - 手戻り元: 2026-11-01-x を足して CLI lint` → lint: OK（足した行で ERROR・NOTE は出ない）
- 前提: SPEC_AUTOPILOT_HOME は、テストで置き場を差し替える環境変数として既に使われている
  - path: plugins/spec-autopilot/tests/test_autopilot.py:115

## 作り方
この spec の ADR のとおり、repo の外の追記だけのファイル（`runs.jsonl`）に、done・block のたびに 1 行を書く。書く関数は新しい `scripts/runlog.py` に置き（autopilot.py は 1,493 行で、ほかの部品と同じく行の予算のため分ける）、autopilot.py の done・block と lineup.py の block から呼ぶ。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | 一時ディレクトリの git repo で init・approve・done まで CLI を実際に回し、SPEC_AUTOPILOT_HOME の runs.jsonl を読む | 1 行が増え、R1 のキーが全部あり、spec と kind が合う |
| R2 | 手元で実物 | 同じ repo で approve の後に CLI block を回す | kind が block の 1 行が増え、blocks に今回の req と reason が入る |
| R3 | 手元で実物 | 承認の後に spec.md を変えてから lineup.py next を回す | kind が block の 1 行が増える |
| R4 | 手元で実物 | 制約に `- 手戻り元: x` を書いた spec と書かない spec で done まで回す | rework_of が x と null |
| R5 | 手元で実物 | 承認 → wait・resume で paused_sec を作る → block → 再承認 → done を、時刻を差し替えたテストで回す | active_min が 2 つの巡の（終わり − 承認 − paused_sec）の和と一致する |
| R6 | 手元で実物 | SPEC_AUTOPILOT_HOME の runs.jsonl の場所にディレクトリを置いて done と block を回す | 終了コードが 0 で、NOTE の行が出る |
| R7 | 手元で実物 | 2 つの文書の該当の行を読む | 手戻り元の書き方と runs.jsonl の名前がある |

## 制約
- 予算: 90 分
- 大きさ: M
- playbook: feature

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
