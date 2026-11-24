# 2 段の相談の文書の規定を、Issue #5 の 7 件に合わせて直す

- ADR: docs/adr/2026-11-24-advice-two-stage-doc-fixes.md

## 目的
#4 で相談を 2 段（fable-advisor の推奨 → advice-checker の反証）にしたときに、独立レビューで出て直していない文書の指摘が 7 件ある（Issue #5）。ユーザーは「2,3も進めて」と指示した（2 がこの Issue）。この spec は 7 件のうち agent 定義と SessionStart の規則に当たる 1・2・3・6 と 7 の一部（名指しの扱い）を直す。直すと、検証できなかった推奨が検証済みと同じ形で届かなくなり、呼べない環境・名指しのときの扱いが読めるようになる。

## 要件
- R1: advice-checker が判定を出すとき、`判定:` の行は `反証あり` か `反証なし` に続けて `（確かめられない <n> / <主張の数>）` を書き、`反証なし` のときも `主張ごとの結果:` の行を書く（:28 の「とだけ判定する」を、主張ごとの結果を書いたうえで同意の理由を足さない、に直す）。
- R2: advice-checker の agent 定義の description は、起動の入口として、SessionStart の相談役の規則と /autopilot の手順に加えて、利用する repo の規則が名指ししたときを挙げ、1 段目の推奨を fable-advisor に限らず、人が名指ししたときの opus-advisor の推奨も含める。
- R3: fable-advisor と opus-advisor の出力の規定にある「呼び出し側へ: 推奨が一致していても、引いた行を読み直してから使う」は、2 段目の advice-checker が `引いた決定:` の主張を `成り立つ` としたときはその検証で読み直しに代え、反証ありで直させた推奨と、`引いた決定:` の主張が `確かめられない` だったときは、main が引いた行を読み直してから使うと書く。SessionStart の相談役の規則も同じことを書く。
- R4: SessionStart の相談役の規則は、fable-advisor か advice-checker を起動できないとき（再試行は 1 回まで）、本文に `<agent>: unavailable（理由）` と書いて進むこと、2 段目を起動できなければ推奨が検証されていないと書くことを書く。
- R5: 人が opus-advisor を名指ししたとき、SessionStart の相談役の規則は、opus-advisor を 1 段目にして、2 段目の advice-checker は同じく回し、反証ありの直しは最初の推奨を出した相談役にさせると書く。

## 非目標
- 2 段の相談の効果を測ること（#4 で決めた、10 回使った後に読む）
- 相談役の判断の基準（fable-advisor・opus-advisor の「選ぶときの基準」）を変えること
- 判定に 3 つ目の値を足すこと（件数を添える形にする。この spec の ADR）
- Issue #5 の 4・5・7（commands/autopilot.md と README の相談役の節）。repo の規則で .md だけの直しは pre-pr-review で回すので、別の PR にする

## 影響範囲
- 変える: plugins/spec-autopilot/agents/advice-checker.md（全体）
  - メモ: 8 行目の description、28 行目、34 行目
- 変える: plugins/spec-autopilot/agents/fable-advisor.md（全体）
  - メモ: 64 行目と 81 行目の読み直しの文
- 変える: plugins/spec-autopilot/agents/opus-advisor.md（全体）
  - メモ: 48 行目と 65 行目の読み直しの文
- 変える: plugins/spec-autopilot/hooks/session_start.py:27-38（ADVISE）
- 呼び出し元: plugins/spec-autopilot/hooks/session_start.py:75-81
  - メモ: ADVISE を additionalContext に入れる
- 手本: plugins/spec-autopilot/tests/test_autopilot.py:1592（test_session_start_gives_only_the_advisor_rule_without_active_specs）
- 同じ入力: なし
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_advisors.py plugins/spec-autopilot/tests/test_autopilot.py -q -k "advis or session_start"

## 変えない挙動
- 相談役と検証役の model・effort が定義のまま: plugins/spec-autopilot/tests/test_advisors.py::test_agent_front_matter
- 続きのある spec が無いとき SessionStart は相談役の規則だけを出す: plugins/spec-autopilot/tests/test_autopilot.py::test_session_start_gives_only_the_advisor_rule_without_active_specs

## 前提
- 目的に届く: 文書の規定を直すだけで、agent が規定どおりに書くかは、実際に使った回でしか分からない
- 運用: main が SessionStart の規則と /autopilot の手順に従って 2 段の相談を回す。検証役の判定の行は、#4 で決めた 10 回の読み取りで数える
- 普通のやり方: なし（この plugin に固有の相談の規定で、外に同じ種類の作り方は無い）
- 過去: #4（0971bbd）で 2 段にし、独立レビューで出た low・advisory を Issue #5 に残した（git log と Issue #5 の本文で確かめた）
- 前提: advice-checker の判定は、成り立たない主張が 1 つ以上で反証あり、それ以外は反証なしで、確かめられない件数は判定の行に出ない
  - path: plugins/spec-autopilot/agents/advice-checker.md:28-35
- 前提: fable-advisor と opus-advisor は、引いた決定があれば呼び出し側に読み直すよう書く
  - path: plugins/spec-autopilot/agents/fable-advisor.md:64-81（基準 0 と 引いた決定の欄）
  - path: plugins/spec-autopilot/agents/opus-advisor.md:48-65（同じ）
- 前提: SessionStart の相談役の規則は ADVISE の文字列で、毎回 additionalContext に入る
  - path: plugins/spec-autopilot/hooks/session_start.py:27-38（ADVISE）
  - path: plugins/spec-autopilot/hooks/session_start.py:75-81

## 作り方
agent 定義 3 本と、SessionStart の ADVISE の文字列だけを直す。判定に 3 つ目の値は足さず、確かめられない件数を判定の行に添える。読み直しは、advice-checker が成り立つとした引いた決定ではその検証で代え、直した推奨と確かめられない主張では main が読み直す。名指しの opus-advisor は 1 段目に入れ替え、2 段目は同じく回す。文書の語があるかだけを assert するテストは足さない（repo の規則）。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | advice-checker.md を読む | 判定の行の形が要件どおりで、反証なしでも主張ごとの結果を書くと読め、28 行目と食い違わない |
| R2 | 手元で実物 | advice-checker.md の description を読み、fable-advisor・opus-advisor の description と比べる | repo の規則が名指ししたときが入口に入る |
| R3 | 手元で実物 | fable-advisor.md・opus-advisor.md と、session_start.py を起動した出力の additionalContext を読む | 読み直しを advice-checker の検証で代える場合と、main が読み直す場合（直した推奨・確かめられない主張）が分かれて読め、「main は反証しない」と 2 通りに読めない |
| R4 | 手元で実物 | session_start.py に SessionStart の payload を渡して起動し、出力の additionalContext を読む | unavailable の書き方と、2 段目が無いときの書き方がある。出力は今までどおり ASCII の JSON |
| R5 | 手元で実物 | session_start.py を起動した出力の additionalContext を読む | 名指しの opus-advisor を 1 段目にし 2 段目を回すと読める |

## 制約
- 予算: 90 分
- 大きさ: M
- playbook: なし（agent 定義と SessionStart の規則の文の直しで、機能の振る舞いは変えない）

## モデル

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
