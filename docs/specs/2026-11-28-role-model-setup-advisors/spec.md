# setup の CLI で相談役・検証役の model と effort も選べるようにする（1 本目）

- ADR: docs/adr/2026-11-28-role-model-setup-advisors.md

## 目的
人は「相談役含めて　modelとeffortをセットアップで選択可能にして」と言った。今の `/spec-autopilot:setup` は実装役・評価役の始めの段しか選べず、相談役（fable-advisor・opus-advisor）・検証役（advice-checker）・照合役（autopilot-spec-checker）の model と effort は agent の定義で固定されている。前の spec（docs/specs/2026-11-27-role-model-setup）は非目標に「照合役・相談役のモデルの上書き」を置いたが、人の発言でこの非目標を外す。できあがると、利用者は setup を 1 回回せば、相談の 1 段目・2 段目を、決まった段（model と effort の組）から選べる。

## 要件
- R1: `ladder.py setup --advisor <段>`・`--checker <段>`（実装・評価と並べてもよい）を実行したとき、ladder.py は models.md に `- 相談: <段>`・`- 検証: <段>` の行を書き（渡していない役の行は残す）、書いたファイルのパスと中身を出す。受ける段は、相談 fable-medium（既定、fable-advisor）・fable-high・opus-high（opus-advisor）、検証 opus-high（既定、advice-checker）・fable-high とする（照合役と検証の opus-xhigh は 2 本目の spec で足す）。
- R2: 受けない段を渡したとき、ladder.py は 0 以外で終わり、役ごとに受ける段を挙げ、models.md を変えない。`--reset 相談`・`--reset 検証` は、その役の行だけを消す。
- R3: `ladder.py show` を実行したとき、ladder.py は 4 つの役（実装・評価・相談・検証）ごとに、受ける段（安い順）・既定の段・手元の設定の段（無ければ「なし」）と、設定のファイルのパスを出す。
- R4: 段ごとの agent の定義が plugin にあり、frontmatter の model・effort が段の名前の組と一致し、本文は同じ役の既定の定義と同じである。
- R5: models.md に相談・検証のどちらかの行が読める段であるとき、SessionStart hook は相談役の規則の後に、役ごとに使う agent の名前（`spec-autopilot:<名前>`）を挙げ、規則と /autopilot の本文の fable-advisor・advice-checker をその名前に読み替えるよう指示する 1 行を足す。行が無いか読めないときは、今と同じ文脈を出す（読めないときは直し方を 1 行で出す）。
- R6: `autopilot.py approve --by-advisor` は、1 段目に相談の段のどの agent の記録も、2 段目に検証の段のどの agent の記録も、今の fable-advisor・advice-checker と同じ条件で数える。
- R7: `autopilot.py init` は、相談・検証の行を spec の `## モデル` に写さない（実装・評価の行だけを今のとおり写す）。

## 非目標
- 段に無い model・effort の組（Haiku、任意の effort など）を選べるようにすること
- opus-advisor の名指しの扱いを変えること（人が名指ししたら今のとおり opus-advisor を 1 段目にする）
- 作った後の spec への反映、repo ごとの設定
- 版数を上げること
- 照合役の段・検証の opus-xhigh・`commands/setup.md` と README の直し（2 本目の spec docs/specs/2026-11-28-role-model-setup-command）

## 影響範囲
- 変える: plugins/spec-autopilot/scripts/ladder.py（全体）
  - メモ: 役と段の表を足し、setup・show・read_config・write_spec を 5 つの役に広げる。梯子の段の計算（climb・impl_agent・review_agent）は変えない
- 変える: plugins/spec-autopilot/hooks/session_start.py（全体）
  - メモ: ADVISE の文は変えない（並行の spec が直している）。blocks に読み替えの 1 行を足すだけ
- 変える: plugins/spec-autopilot/scripts/advisor_approval.py（全体）
- 新規: plugins/spec-autopilot/agents/fable-advisor-high.md
- 新規: plugins/spec-autopilot/agents/advice-checker-fable.md
- 呼び出し元: plugins/spec-autopilot/scripts/autopilot.py:906
- 呼び出し元: plugins/spec-autopilot/scripts/autopilot.py:970
- 呼び出し元: plugins/spec-autopilot/hooks/hooks.json:43
- 手本: plugins/spec-autopilot/tests/test_ladder.py:199（test_every_rung_has_an_agent_with_the_declared_model_and_the_same_body）
- 手本: plugins/spec-autopilot/tests/test_advisor_approval.py:68（test_approve_by_advisor_returns_a_blocked_spec_to_building）
- 同じ入力: models.md
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_ladder.py plugins/spec-autopilot/tests/test_advisor_approval.py plugins/spec-autopilot/tests/test_advisors.py plugins/spec-autopilot/tests/test_autopilot.py -q -n auto

## 変えない挙動
- 段が既定の実装役・評価役になる: plugins/spec-autopilot/tests/test_ladder.py::test_the_default_agents_are_the_measured_pair
- 段ごとの実装役・評価役の定義: plugins/spec-autopilot/tests/test_ladder.py::test_every_rung_has_an_agent_with_the_declared_model_and_the_same_body
- 相談役の承認し直しの門: plugins/spec-autopilot/tests/test_advisor_approval.py::test_approve_by_advisor_returns_a_blocked_spec_to_building
- 同梱の相談役の定義: plugins/spec-autopilot/tests/test_advisors.py::test_agent_front_matter

## 前提
- 目的に届く: 選べるのは段の表にある組だけで、任意の model・effort は選べない。相談役の読み替えは SessionStart の文脈で main に指示するもので、main が読み替えずに既定の agent を起動しても機械では止めない（承認し直しの門は、どちらの名前の記録も数える）
- 運用: 利用者が `/spec-autopilot:setup` を回す。相談・検証の設定は次に始めたセッションから効く（SessionStart が読む）
- 普通のやり方: pstack の `/setup-pstack` は役ごとにモデルを選ばせ、規則ファイルに書き出す（https://github.com/backnotprop/pstack/blob/main/skills/setup-pstack/SKILL.md）。前の spec と同じく、起動に model を渡さず段ごとの定義を選ぶ形に合わせる
- 過去: 前の spec（docs/specs/2026-11-27-role-model-setup、PR #72）が実装・評価の setup を作り、相談役を非目標にした
- 前提: agent の定義は frontmatter で model・effort を固定し、起動で model を渡さない
  - path: plugins/spec-autopilot/agents/fable-advisor.md:1-8
  - path: plugins/spec-autopilot/scripts/ladder.py:1-3（起動の model は別名しか受けない）
- 前提: 承認し直しの門は fable-advisor・advice-checker の名前で記録を探す
  - path: plugins/spec-autopilot/scripts/advisor_approval.py:22
- 前提: SessionStart は ADVISE を毎回文脈に入れる
  - path: plugins/spec-autopilot/hooks/session_start.py:90
- 前提: 手元の設定は models.md で、init が実装・評価の行を spec に写す
  - path: plugins/spec-autopilot/scripts/ladder.py:146-212

## 作り方
この spec の ADR のとおり。`ladder.py` に、相談・検証の役の段の表（段 → agent の名前・model・effort）を足し、設定の読み書きと show・setup を 5 つの役に広げる。spec の `## モデル` の lint と写しは実装・評価だけのまま。段ごとに agent の定義を足す（本文は既定の定義の写し）。SessionStart は models.md を読み、設定がある役の agent の名前を 1 行で足す。承認し直しの門は、相談・検証の段の agent の名前の集まりで記録を探す。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | 一時の `SPEC_AUTOPILOT_HOME` で `ladder.py setup --advisor opus-high --checker fable-high` → `--impl opus-medium` を打ち、models.md を読む | 3 行が残り、出力にパスと中身が出る |
| R2 | 手元で実物 | `--advisor sonnet-high`、`--checker haiku` を打ち、続けて `--reset 相談` | 受けない段は 0 以外で models.md が変わらず、reset は相談の行だけを消す |
| R3 | 手元で実物 | 設定のある置き場と無い置き場で `ladder.py show` | 4 つの役の段・既定・設定・パスが出る |
| R4 | 手元で実物 | 単体テストで段ごとの定義の frontmatter と本文を既定の定義と比べる | model・effort が段と合い、本文が同じ |
| R5 | 手元で実物 | 一時の置き場で設定あり・なし・読めない設定の 3 つで session_start.py に payload を渡して出力を読む | 設定ありは読み替えの行が出て、なしは今と同じ、読めないときは直し方の行が出る |
| R6 | 手元で実物 | 単体テストで fable-advisor-high と advice-checker-fable の記録を置いて approve --by-advisor | 今の名前と同じく通り、片方が欠ければ断る |
| R7 | 手元で実物 | 相談・検証の行を含む設定で init を打ち、spec の `## モデル` と lint を見る | 実装・評価の行だけが写り、lint がモデルの節の誤りを出さない |

## 制約
- 予算: 90 分
- 大きさ: M
- playbook: feature
- autopilot.py は行を増やさない（足す処理は ladder.py に置く）
- hooks/session_start.py の ADVISE の文と commands/autopilot.md は変えない（並行の spec docs/specs/2026-11-28-fewer-advisor-calls が直している。衝突したら main の後に載せ替える）
- 想定する脅威: 設定の読み替えの誤りで、承認し直しの門が相談役でない agent の記録を数えること。門が数えるのは段の表の名前だけにする

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
