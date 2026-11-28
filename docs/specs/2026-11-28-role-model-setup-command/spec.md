# setup で照合役も選べるようにし、command と README を 5 つの役に広げる（2 本目）

- ADR: docs/adr/2026-11-28-role-model-setup-command.md

## 目的
人は「相談役含めて　modelとeffortをセットアップで選択可能にして」と言った。1 本目（docs/specs/2026-11-28-role-model-setup-advisors）が `ladder.py setup` で相談・検証の段を選べるようにし、選んだ段の agent を使わせる。この spec（2 本目）は、照合役（autopilot-spec-checker）の段と検証役の fable の段を足し、`/spec-autopilot:setup` の対話と README を 5 つの役（実装・評価・相談・検証・照合）に広げる。できあがると、利用者は setup の対話を 1 回回せば全部の役の model と effort を選べる。

## 要件
- R1: `ladder.py setup --spec-checker <段>` を実行したとき、ladder.py は models.md に `- 照合: <段>` の行を書く。受ける段は照合 sonnet-high（既定）・opus-high とし、検証の段に fable-high を足す。`--reset 照合` はその行だけを消す。受けない段は 0 以外で終わり、models.md を変えない。
- R2: `ladder.py show` は 1 本目の形のまま、照合を足した 5 つの役を出す。
- R3: 検証の fable-high・照合の opus-high で使う役は、段の名前のとおりの model と effort で動き、同じ役の既定（advice-checker・autopilot-spec-checker）と同じ指示で答える。
- R4: models.md に照合の行が既定でない段で読めるとき、次に始めたセッションで main が受け取る読み替えの指示は、autopilot-spec-checker もその段の agent の名前に読み替えるよう示す。`autopilot.py init` は照合の行を spec に写さない。検証の fable-high の記録は、`approve --by-advisor` で 2 段目として数える。
- R5: `commands/setup.md`（`/spec-autopilot:setup`）は、5 つの役ごとに今の段と受ける段を示して人に選ばせ、選んだ段を setup か reset で書き、結果をそのまま示す手順を持つ。plugin の README の setup の節に、相談・検証・照合の役、次のセッションから効くこと、相談と検証を同じ model にすると別の目で見る効きが減ることを書く。

## 非目標
- 段に無い model・effort の組を選べるようにすること
- 照合役の起動の仕組み（`commands/autopilot.md` の B の 3 と合意し直しの照合）を変えること（並行の spec が直している）
- 検証の opus-xhigh（足すなら別の spec）
- 版数を上げること

## 影響範囲
- 変える: plugins/spec-autopilot/scripts/ladder.py（全体）
  - メモ: 1 本目の相談・検証の段の表に、照合の役と検証の fable-high を足す。session_start.py・advisor_approval.py は表を読むので変えない
- 新規: plugins/spec-autopilot/agents/advice-checker-fable.md
- 新規: plugins/spec-autopilot/agents/autopilot-spec-checker-opus.md
- 変える: plugins/spec-autopilot/commands/setup.md（全体）
- 変える: plugins/spec-autopilot/README.md（全体）
- 呼び出し元: plugins/spec-autopilot/scripts/autopilot.py:906
- 呼び出し元: plugins/spec-autopilot/hooks/session_start.py:1
- 呼び出し元: plugins/spec-autopilot/scripts/advisor_approval.py:1
- 手本: plugins/spec-autopilot/tests/test_ladder.py:199（test_every_rung_has_an_agent_with_the_declared_model_and_the_same_body）
- 同じ入力: models.md
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_ladder.py plugins/spec-autopilot/tests/test_ladder_setup.py plugins/spec-autopilot/tests/test_init_models.py plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py plugins/spec-autopilot/tests/test_advisor_approval.py plugins/spec-autopilot/tests/test_advisors.py plugins/spec-autopilot/tests/test_autopilot.py -q -n auto

## 変えない挙動
- 段ごとの実装役・評価役の定義: plugins/spec-autopilot/tests/test_ladder.py::test_every_rung_has_an_agent_with_the_declared_model_and_the_same_body
- init が discovery の spec を作る: plugins/spec-autopilot/tests/test_autopilot.py::test_init_creates_artifacts_in_discovery

## 前提
- 目的に届く: 1 本目と合わせて 5 つの役を選べる。照合役の読み替えは SessionStart の指示で、main が既定の照合役を起動しても機械では止めない
- 運用: 利用者が `/spec-autopilot:setup` を回し、次に始めたセッションから効く
- 普通のやり方: pstack の `/setup-pstack`（https://github.com/backnotprop/pstack/blob/main/skills/setup-pstack/SKILL.md）。手順との対応: 今の設定を読む → R2。役ごとに選んで確かめる → R5。書き出す → R1。行を消すと既定 → R1。使えるモデルを調べる → 扱わない（段の表だけ）。budget → 扱わない
- 過去: 前の spec（docs/specs/2026-11-27-role-model-setup、PR #72）が setup の command を実装・評価の 2 問で作った
- 前提: setup の command は役ごとに 1 問ずつ AskUserQuestion で選ばせ、1 問の選択肢は 4 個まで
  - path: plugins/spec-autopilot/commands/setup.md:18-23
- 前提: AskUserQuestion は 1 回に 4 問まで受ける（5 つの役を 2 回に分ける根拠）
  - 未確認: Claude Code の tool の仕様で、repo の中に書いた所が無い。実装のときに tool の説明で確かめ、5 問を 1 回で受けるなら 1 回にする
- 前提: 照合役は /autopilot の本文が名前で起動する。読み替えは文脈の指示だけで効かせ、本文は直さない
  - path: plugins/spec-autopilot/commands/autopilot.md:75
  - path: plugins/spec-autopilot/commands/autopilot.md:117
- 前提: 照合役は定義で model・effort を固定している
  - path: plugins/spec-autopilot/agents/autopilot-spec-checker.md:1-6

## 作り方
この spec の ADR のとおり。1 本目の相談・検証の段の表に照合の役（sonnet-high: autopilot-spec-checker、opus-high: autopilot-spec-checker-opus）と検証の fable-high（advice-checker-fable）を足す。新しい定義は既定の定義の本文を写し、frontmatter の model・effort だけを変える（本文の同一はテストで見る）。読み替えの行と承認し直しの門は 1 本目が表から作るので、表に足せば効く。command は AskUserQuestion の 1 回目に実装・評価・相談・検証の 4 問、2 回目に照合の 1 問を聞く（1 回に 5 問受けるなら 1 回）。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | 一時の `SPEC_AUTOPILOT_HOME` で `--spec-checker opus-high`・`--checker fable-high`・`--spec-checker fable`・`--reset 照合` を打つ | 受ける段は書かれ、受けない段は 0 以外で変わらず、reset は照合の行だけを消す |
| R2 | 手元で実物 | `ladder.py show` | 5 つの役が出る |
| R3 | 手元で実物 | 単体テストで定義の frontmatter と本文を比べる | 段と合い本文が同じ |
| R4 | 手元で実物 | 照合の行を置いて session_start.py と init を回し、単体テストで advice-checker-fable の記録で approve --by-advisor | 読み替えの行に照合が出て、spec に照合の行が写らず、承認し直しが通る |
| R5 | 手元で実物 | 評価役が commands/setup.md の手順のコマンドを一時の置き場で打ち、README の節を読む | 手順が 5 つの役を選び、コマンドが通り、README に役・効く時点・注意が書いてある |

## 制約
- 予算: 60 分
- 大きさ: M
- playbook: feature
- 依る spec: 2026-11-28-role-model-setup-advisors
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

