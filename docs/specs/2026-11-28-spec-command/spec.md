# ふわっとした依頼を、速い往復の壁打ち（/spec）で具体例から完了条件に熟成させる

- ADR: docs/adr/2026-11-28-spec-command.md

## 目的
人の発言（順に）:「完了までに時間がかかるのと、ちょいちょい止まるので体験が悪い 最初の反応までに時間がかかるのも体験が悪い」「壁打ちの往復で、要件と完了条件、制約条件、実装方法 を決めて後は完了まで自走するスタイルがいいのでは？ 往復で何分も待たされるのは体験が悪い 一発で正解を出さなくても良いから反応良く壁打ちして熟成させたい」「要件自体もふわっとしたものだったりするので、それを言語化して完了条件として使えるように壁打ちで熟成させたい」「壁打ちスキルを作ってそこで開始するのはふわっとした話にしたい autopilotで始めたけどふわっとした話はmainの判断に任せたい 要件と完了条件が明示されない指示はふわっとした話で良いと思う」「superpowersのbrainstormingスキルの起動条件が良く出来ている」「specにする」。

観測した事実（2026-11-20〜28 の /autopilot の 33 セッションの transcript）: `/autopilot` を打ってから最初の返事まで中央値 8.9 分（最大 23.4 分）。承認の前の往復は、agent を回した往復が中央値 11 分（遅い 1 割は 93 分以上）、回さない往復が中央値 0.4 分。承認までの lint は中央値 3 回。最初の返事から lint を通した草案を出す決まりと、示す前の照合役が、待ちの大半だった。

目的に届かなかった事例（利用者の repo と spec-autopilot の 22 件と、調査の記憶の 13 本の spec）のうち、目的そのものの確かめ方が spec に無かったものが 6〜7 件あった。調査の記憶は「覚えて賢くなる」を完了条件にしないまま、書く・読む・消すの要件を全部満たし、4 日後に「賢くなる仕組みはできた？」に「できていない」と答えた。

できあがったら、要件と完了条件が明示されない依頼は `/spec` の速い往復で、AI が出す具体例を人が選ぶ形で完了条件まで熟成し、「固めて」の 1 回だけ lint と照合役を回して承認に進む。spec はどれも目的そのものの確かめ方を 1 行持つ。

## 要件
- R1: `/spec` を起動したとき、main は最初の返事の前に、依頼に要件と完了条件が明示されているかを判断し、明示されていれば `/autopilot` の合意（B）の手順で spec を書いて示し、明示されていなければ壁打ちに入る。
- R2: 要件も完了条件も書いていない 1 文の依頼で `/spec` を起動したとき、main は最初の返事を 60 秒以内に返し、返事に要件・完了条件・制約・実装方法の 4 項目のたたき台と問い 1 つを入れる。「固めて」の前の 2 往復目以降の返事も、それぞれ 60 秒以内に返す。
- R3: 壁打ちの依頼か人の返事に、何が見えたら満たしたかを言えない語（例:「賢くなる」）が要件か完了条件として出たとき、main は「何が見えたら完了か」の具体例を 2〜3 個出して人に選ばせ、選ばれた例を `〜とき、〜になる` の形の完了条件としてたたき台に入れる。
- R4: 壁打ちの途中で人が「固めて」と言ったとき、main は spec と ADR を書き、lint と照合役を 1 回ずつ通して照合役の ng を直してから spec を示し、人の OK を受けて承認に進む。
- R5: `/autopilot` を起動したとき、依頼に要件と完了条件が明示されていなければ、main は `/spec` の壁打ちの手順（R2〜R4）で進み、明示されていれば今の手順（最初の返事から lint を通した草案を示す）で進む。
- R6: spec の「## QA の方向性」に `- 目的の確かめ: R<n>`（その要件の QA で目的に届いたかを確かめる）か `- 目的の確かめ: マージ後（<確かめ方>）` の行がちょうど 1 本無いとき、または `R<n>` が要件に無いとき、`CLI lint` は ERROR にする。

## 非目標
- approve の門（人の発言の起点の判定）を変えること。「固めて」と「OK」で人の発言が 2 回要るのを 1 回にするには門を変える必要があり、今回は入れない
- 方法の選び方（要件と方法の表・要件を緩めた案・運用の前提の出どころ・人の発言の原文を照合役に渡す）。この spec の後に別の spec にする
- 承認の後に止まること（block・park・承認し直し）。人の「ちょいちょい止まる」は、この spec では扱わない
- 本番で小さく 1 周させる段、仕組みの効果を後で測り直す段。別の spec にする
- 承認から done までの時間（中央値 36 分の大半は実装役と評価役）を短くすること
- 評価役の定義を変えること（目的の確かめは、R6 のとおり要件の QA に寄せるので、評価役は今の要件ごとの確かめのまま）
- 版数を上げること（repo の CLAUDE.md の決まりどおり、マージの後に版数だけの PR で上げる）

## 影響範囲
- 新規: plugins/spec-autopilot/commands/spec.md
- 変える: plugins/spec-autopilot/commands/autopilot.md（全体）
  - メモ: 44〜48 行目（A の 1・2、最初の返事の草案と試作）、64 行目（A の 5）、76〜77 行目（B の 3、lint と照合役）
- 変える: plugins/spec-autopilot/scripts/stages.py:116-133（lint）
- 変える: plugins/spec-autopilot/templates/spec.md（全体）
  - メモ: 36〜40 行目の QA の方向性の雛形
- 変える: plugins/spec-autopilot/README.md（全体）
  - メモ: 8 行目の始め方の例と、26 行目の lint の説明
- 呼び出し元: plugins/spec-autopilot/scripts/autopilot.py:603
- 別の実装: plugins/spec-autopilot/tests/test_autopilot.py:19-60
  - メモ: テストの GOOD_SPEC に `- 目的の確かめ:` の行が無いと、これを使うテストの lint・approve が全部落ちる。GOOD_SPEC に 1 行足す
- 同じ入力: なし
- 呼び出し元: plugins/spec-autopilot/scripts/light.py:160
- 呼び出し元: plugins/spec-autopilot/scripts/lineup.py:58
- 呼び出し元: plugins/spec-autopilot/scripts/lineup.py:235
  - メモ: 承認と着手のときに既存の spec を lint し直す。`- 目的の確かめ:` の無い既存の spec は、承認し直しと着手で止まる（ADR の Consequences）
- 呼び出し元: plugins/spec-autopilot/tests/test_light.py:485
- 呼び出し元: plugins/spec-autopilot/tests/test_ladder.py:333
- 呼び出し元: plugins/spec-autopilot/tests/test_init_models.py:10
  - メモ: 3 本とも templates/spec.md を読む。雛形の `- 目的の確かめ:` の行が、これらのテストの検査を通る形にする
- 呼び出し元: plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py:16
  - メモ: commands/*.md の references の実在を見るので、新規の commands/spec.md も対象になる
- 呼び出し元: plugins/spec-autopilot/tests/test_goal_command.py:18
- 呼び出し元: plugins/spec-autopilot/tests/test_advisor_approval.py:390
  - メモ: どちらも commands/autopilot.md の文を読む。読む見出しと CLI の呼び出しの行を変えない
- 手本: plugins/spec-autopilot/references/small-prototype.md:3
  - メモ: 「A の 2 から読む」と書く。壁打ちの道では試作を「固めて」の後に回すので、読む時点の書き方を合わせる。references/playbooks/feature.md:7 の「推奨で埋める草案」は、明示された依頼の道の草案として変えない
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_stages.py plugins/spec-autopilot/tests/test_autopilot.py plugins/spec-autopilot/tests/test_light.py plugins/spec-autopilot/tests/test_ladder.py plugins/spec-autopilot/tests/test_init_models.py plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py plugins/spec-autopilot/tests/test_goal_command.py plugins/spec-autopilot/tests/test_advisor_approval.py -q -n auto

## 変えない挙動
- QA の方向性の段（手元で実物・デプロイ後・代役）と理由の行の検査: plugins/spec-autopilot/tests/test_stages.py::test_lint_requires_the_reason_for_a_deploy_stage
- 段の読めない行の検査: plugins/spec-autopilot/tests/test_stages.py::test_lint_rejects_a_row_without_a_known_stage
- 要件の無い理由の行の検査: plugins/spec-autopilot/tests/test_stages.py::test_lint_rejects_a_reason_for_an_unknown_requirement

## 前提
- 目的に届く: R2 は 1 回の起動の速さを確かめるだけで、完了条件の「壁打ちの往復の中央値が 1 分以下」「最初の返事まで 1 分以内」は、マージ後の 5 本の run の transcript で測り直すまで届いたと言えない。R3 は具体例を出すことまでで、選んだ例が目的に合うかは人の選びに頼る
- 運用: 人が `/spec <やりたいこと>` か `/autopilot <やりたいこと>` を打つ。マージ後、/autopilot の 5 本の run が済んだら、次に壁打ちを直す spec を始める前に main が transcript を数え直し（人の発言から最初の assistant の返事まで、と承認の前の 1 往復の時間の中央値）、往復の中央値 1 分以下と最初の返事 1 分以内を見る。届かなければ、その数字を観測した失敗として次の spec にする。plugin を入れた人に main へのマージで届く。保つのは repo の持ち主で、commands/spec.md と commands/autopilot.md の A を一緒に直す
- 普通のやり方: 依頼の曖昧さを潰す段を、実装の前に別のコマンドで持つ（GitHub Spec Kit の `/speckit.specify` と `/speckit.clarify`、Agent OS の `/shape-spec`、Matt Pocock の `/grill-me`）。起動条件を広く取り、依頼に大事なことが全部あるかを本文の冒頭で判断する形は superpowers の brainstorming（出典: https://github.github.com/spec-kit/reference/agentic-sdd.html 、https://buildermethods.com/agent-os/shape-spec ）
- 過去: values-driven-main（main が人に問う範囲を 3 つに絞る）と fewer-advisor-calls（相談役は承認の門と名指しだけ）が、A の 2 と B の 3 の同じ文を直してマージ済み。この spec はその文の上に載せる（commands/autopilot.md の 45・77 行目で確かめた）
- 前提: lint の QA の方向性の検査は stages.py の lint が受け持ち、autopilot.py の lint から呼ばれる
  - path: plugins/spec-autopilot/scripts/stages.py:116-133
  - path: plugins/spec-autopilot/scripts/autopilot.py:603
- 前提: plugin の `commands/<名前>.md` は `/<名前>` で打てるコマンドになり、description で model からも選ばれる
  - path: plugins/spec-autopilot/commands/setup.md:1-3（`/spec-autopilot:setup` として一覧に出ている）
- 前提: `claude -p --plugin-dir <worktree>/plugins/spec-autopilot --output-format stream-json` で `/spec` を 1 回起動すると、最初の返事までの時間と、その turn で呼んだ tool が出力から読める
  - path: docs/specs/2026-11-23-handoff-after-close/evidence/R8.txt:3（入れ子の `claude -p --plugin-dir ... --output-format stream-json --verbose` で tool の呼び出しを読んだ前例）
  - 未確認: 返事までの時間を stream-json の出力から読めるか（前例は tool だけを読んだ）。読めなければ、起動の前後の時刻と出力の行の到着で測る

## 作り方
`commands/spec.md` を足し、壁打ちの手順（冒頭の判断・最初の返事の型・具体例で完了条件にする・「固めて」で 1 回だけ検査）をそこに 1 か所で書く。速さは、「固めて」の前の往復で Agent（subagent・相談役・照合役）も `CLI` も呼ばず、Read・Grep・Glob でコードを読むだけにすることで出す。「固めて」の後は、init していなければ `CLI init` を打ち、spec と ADR を書き、`CLI lint`、照合役 1 回の順に回して示し、OK で `/autopilot` の B の 5（approve）に進む。

普通のやり方の資料から採るもの・採らないもの: 冒頭で依頼に大事なことが全部あるかを判断する形と、広い起動条件（brainstorming、R1・R5）は採る。開いた問いを 1 つずつ聞く形（brainstorming・grill-me）は採り、選べる問いには具体例を出す（BMAD の番号で選ぶ掘り下げ方に近い、R3）。決めることの木を全部詰めるまで問い続ける形（grill-me）と、spec を走査して 10 種の曖昧さを問う段（Spec Kit の clarify）は採らない（往復が長くなり、R2 の速さに反する。曖昧さは「固めて」の lint と照合役で拾う）。plan mode で回す形（Agent OS の shape-spec）は採らない（spec-autopilot は plan mode に依らない）。`/autopilot` の A は、依頼に要件と完了条件が明示されていなければ `commands/spec.md` に従うと書き、明示されていれば今の A の 2 のまま進む。S の試作は、壁打ちの道では「固めて」の後に回す。`- 目的の確かめ:` の行は stages.py の lint で形と要件の番号を見る（評価役は変えず、目的の確かめを要件の QA に寄せる）。退けた案と理由はこの spec の ADR。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | `claude -p --plugin-dir` で、要件と完了条件を書いた依頼と、書いていない依頼で `/spec` を 1 回ずつ起動し、出力を読む | 書いた依頼では spec を書く道（`CLI init`・`CLI lint`）に進み、書いていない依頼では 4 項目と問い 1 つを返して tool の CLI を呼ばない |
| R2 | 手元で実物 | `claude -p --plugin-dir ... --output-format stream-json --verbose` で、1 文のふわっとした依頼（「障害調査が賢くなるようにしたい」）で `/spec` を起動し、続けて `--resume` で問いへの答えを 1 回送り、それぞれの返事の時刻と呼んだ tool を数える | 2 回とも、送ってから返事まで 60 秒以内（Agent と CLI の呼び出しが 0 回）。1 回目の返事に 4 項目と問いが 1 つ |
| R3 | 手元で実物 | R2 の出力の返事を読む | 「賢くなる」に、何が見えたら完了かの具体例が 2〜3 個あり、選ばせる問いになっている |
| R4 | 手元で実物 | R2 のセッションを `--resume` して「固めて」を送り、出力の tool の順を読む | `CLI init`・spec と ADR の書き込み・`CLI lint`・照合役の起動の順に呼び、spec を示して OK を求める（approve は打たない） |
| R5 | 手元で実物 | `claude -p --plugin-dir` で、要件と完了条件を書いていない依頼で `/autopilot` を起動し、出力を読む | 最初の turn で lint を通した草案を出さず、R2 と同じく 4 項目と問い 1 つを返す |
| R6 | 手元で実物 | 単体テスト（`CLI lint` を一時 repo の spec に当てる） | 行が無い・2 本ある・`R<n>` が要件に無い spec は ERROR、`- 目的の確かめ: R1` と `- 目的の確かめ: マージ後（<確かめ方>）` の spec は通る |

- 目的の確かめ: R2

## 制約
- 予算: 90 分
- 大きさ: L
- playbook: feature
- 想定する脅威: なし（lint の検査を 1 つ足すだけで、通していた spec を止める向き。人の発言の門は変えない）

## モデル

## 自走の範囲
- 範囲: マージまで
- QA の環境: 手元の一時 repo と、この worktree の plugin を `--plugin-dir` で読む headless の claude
- QA の書き込み先: 手元の一時 repo と spec のディレクトリの evidence だけ
- デプロイの起動:
- デプロイの確かめ:
- ロールバック: revert の PR をマージし、デプロイの完了を確かめる
- 通知: デスクトップ
- AWS の profile: なし

## 止まる条件
- 合意した要件のどれかを満たす方法が無いと分かったとき（その要件だけを park に積み、ほかを進める。どの要件も進められないときだけ block）
- 承認した自走の範囲の外の操作が要るとき（実行せずに park に積む）
