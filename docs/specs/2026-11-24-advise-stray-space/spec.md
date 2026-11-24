# SessionStart の相談役の規則の文から、余分な半角スペースを除く

- ADR: docs/adr/2026-11-24-advise-stray-space.md

## 目的
PR #13 で SessionStart の相談役の規則（ADVISE）を直したとき、「渡して」と「最初の推奨を出した相談役」の間に半角スペースが 1 つ入った。ユーザーは「小さな直しをして」と指示した。直すと、全セッションに入る規則の文が崩れずに読める。

## 要件
- R1: SessionStart の hook を起動したとき、出力の additionalContext の相談役の規則は「渡して最初の推奨を出した相談役を 1 本起動し」と続けて書き、「渡して 最初」（間に半角スペース）を含まない。

## 非目標
- 規則の文の中身を変えること
- ほかの文の空白や句読点を見直すこと

## 影響範囲
- 変える: plugins/spec-autopilot/hooks/session_start.py:32（ADVISE）
- 呼び出し元: plugins/spec-autopilot/hooks/session_start.py:75-81
  - メモ: ADVISE を additionalContext に入れる
- 手本: plugins/spec-autopilot/tests/test_autopilot.py:1592（test_session_start_gives_only_the_advisor_rule_without_active_specs）
- 同じ入力: なし
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_advisors.py plugins/spec-autopilot/tests/test_autopilot.py -q -k "advis or session_start"

## 変えない挙動
- 続きのある spec が無いとき SessionStart は相談役の規則だけを出す: plugins/spec-autopilot/tests/test_autopilot.py::test_session_start_gives_only_the_advisor_rule_without_active_specs

## 前提
- 目的に届く: 届く。空白 1 つを除くだけで、規則の中身は変わらない
- 運用: なし（文の直しで、運用の手順は変わらない）
- 普通のやり方: なし（この plugin に固有の文の直し）
- 過去: PR #13（bc9e4a2）で入った空白（git log で確かめた）
- 前提: 余分な空白は ADVISE の 32 行目の 1 か所だけにある
  - コマンド: `grep -n "渡して 最初" plugins/spec-autopilot/hooks/session_start.py` → 32 行目の 1 件
  - path: plugins/spec-autopilot/hooks/session_start.py:32

## 作り方
ADVISE の 32 行目の文字列から半角スペースを 1 つ除く。文書の語の有無だけを見るテストは足さない（repo の規則）。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | session_start.py に SessionStart の payload を渡して起動し、出力の additionalContext を読む | 「渡して最初の推奨を出した相談役」を含み、「渡して 最初」を含まない。出力は今までどおり ASCII の JSON で、回帰テストが通る |

## 制約
- 予算: 30 分
- 大きさ: S
- playbook: なし（文字列の空白 1 つの直しで、機能の振る舞いは変えない）

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
