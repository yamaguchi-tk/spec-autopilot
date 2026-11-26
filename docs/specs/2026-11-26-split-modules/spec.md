# 上限に届いた autopilot.py と overnight.py を、挙動を変えずに責務ごとのファイルに分ける

- ADR: docs/adr/2026-11-26-split-modules.md

## 目的
人の発言（順に）:「autopilotの改善をしたい」「別のセッションで改善中なので被らないようにして」「リファクタしてから改善を始めたい」「全部終わるまで自走して欲しい」。

観測した事実: `plugins/spec-autopilot/scripts/autopilot.py` は 1500 行で、利用者の規則（1 ファイル 1500 行以内、超えたファイルは増やさない）の上限に届いている。open の PR（#51・#63）と未 PR の trust-marker-origin が autopilot.py に行を足すと、どれも目安を超える。`overnight.py` は 1429 行で、次に上限に当たる。300 行を超える関数は無いので、直すのはファイルの分け方だけ。

できあがったら、autopilot.py と overnight.py に行を足す改善を、目安を超えずに始められる。挙動・CLI の出力・テストの期待は変わらない。

## 要件
- R1: transcript を読んで数える部分を autopilot.py の外に移したとき、autopilot.py は 1400 行以下になり、autopilot.py に移した名前を外へ出し直す行（re-export）は無く、テストの全量が通り、CLI の出力とエラー文は変わらない。
- R2: overnight.py の scope・deploy・production・rollback の判定を overnight.py の外に移したとき、overnight.py は 1100 行以下になり、overnight.py に re-export の行は無く、テストの全量が通り、CLI の出力とエラー文は変わらない。

## 非目標
- 挙動・CLI の出力・エラー文を変えること
- 関数の中身を書き換えること（移すだけ。import の行と、参照の名前の頭だけを変える）
- tests/test_autopilot.py などのテストのファイルを分けること（利用者の規則で test は対象外）
- 版数を上げること（挙動を変えないので、利用者に届ける変更が無い）
- 承認の後の spec の直し（Issue #22）・auto mode の拒否の改善（このリファクタの後に、別の spec で扱う）

## 影響範囲
- 変える: plugins/spec-autopilot/scripts/autopilot.py:1280-1416（ANOMALY_KINDS、EMPTY_BLOCKS、POLL_SEC、APPROVED_OUT、DONE_OUT、WAIT_OUT、RESUME_OUT、_LOOP、_LOOP_SLEEP、_SLEEP_SEC、_LONE_SLEEP、_NOT_HUMAN、_iso_epoch、_text、_results、Overdue、transcript_lines、_polls、anomalies、anomaly_line）
- 新規: plugins/spec-autopilot/scripts/transcript.py
- 変える: plugins/spec-autopilot/scripts/overnight.py:74-503（scope_rows、budgets、rollback_cmd、scope_lint、scope_errors、production、production_errors、rollback_error、stage_errors）
  - メモ: 子 2 を作るときに、その時点の行番号と移す名前で書き直す。区画は awaits・parked_ops・exempt_kinds・budget_view（641-694）も呼ぶので、循環を避ける境界は子 2 で決める
- 新規: plugins/spec-autopilot/scripts/deploy.py
- 呼び出し元: plugins/spec-autopilot/hooks/stop.py:190
- 呼び出し元: plugins/spec-autopilot/hooks/stop.py:400-408
- 呼び出し元: plugins/spec-autopilot/hooks/stop.py:76
- 呼び出し元: plugins/spec-autopilot/scripts/overnight.py:1242
- 呼び出し元: plugins/spec-autopilot/scripts/autopilot.py:584
- 呼び出し元: plugins/spec-autopilot/scripts/autopilot.py:618
- 呼び出し元: plugins/spec-autopilot/scripts/autopilot.py:721-722
- 呼び出し元: plugins/spec-autopilot/scripts/autopilot.py:1030
- 呼び出し元: plugins/spec-autopilot/scripts/autopilot.py:1051
- 呼び出し元: plugins/spec-autopilot/scripts/preflight.py:118-122
- 呼び出し元: plugins/spec-autopilot/scripts/light.py:120-131
- 呼び出し元: plugins/spec-autopilot/scripts/lineup.py:38
- 呼び出し元: plugins/spec-autopilot/scripts/lineup.py:77
- 呼び出し元: plugins/spec-autopilot/scripts/lineup.py:252
- 呼び出し元: plugins/spec-autopilot/tests/test_stop_bounds.py:36-116
  - メモ: autopilot.Overdue・autopilot.anomalies・autopilot._polls と、88 行目の monkeypatch の向け先
- 呼び出し元: plugins/spec-autopilot/tests/test_merge_qa.py:105-162
- 手本: plugins/spec-autopilot/scripts/stages.py:1（overnight.py から import される小さいモジュール）
- 同じ入力: なし
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_stop_bounds.py plugins/spec-autopilot/tests/test_anomalies.py plugins/spec-autopilot/tests/test_autopilot.py plugins/spec-autopilot/tests/test_merge_qa.py plugins/spec-autopilot/tests/test_rollback.py plugins/spec-autopilot/tests/test_overnight.py plugins/spec-autopilot/tests/test_lineup.py plugins/spec-autopilot/tests/test_light.py -q -n auto

## 変えない挙動
- Stop hook の transcript の走査は予算を過ぎたら止める側に倒れる: plugins/spec-autopilot/tests/test_stop_bounds.py
- 自走の異常の件数の数え方と出力: plugins/spec-autopilot/tests/test_anomalies.py
- 承認の人の発言の門: plugins/spec-autopilot/tests/test_autopilot.py::test_approve_after_block_needs_new_user_prompt
- マージ・デプロイ・QA の段の判定: plugins/spec-autopilot/tests/test_merge_qa.py
- ロールバックの判定: plugins/spec-autopilot/tests/test_rollback.py

## 前提
- 目的に届く: R1 で autopilot.py は約 135 行減り、R2 で overnight.py は約 450 行減る。改善を足す余裕はできるが、改善そのものは入らない。R2 は #51・#63・#57 のマージを待つので、その PR が朝までにマージされなければ、R2 の子は作らずに残り、親は done にならない
- 運用: 移した後は、transcript の数え上げは transcript.py、デプロイの段の判定は deploy.py を直す。CLI の入口（autopilot.py・overnight.py の main）は変わらないので、利用者の手順は変わらない
- 普通のやり方: 大きいモジュールは、外から呼ばれる名前の塊ごとに別のモジュールへ移し、呼び出し元を新しいモジュールへ向け直す（互換の re-export を残さない。利用者の規則の「互換レイヤーを足さない」）
- 過去: stages.py・ladder.py・goal.py・light.py は、autopilot.py・overnight.py から切り出した、または横に足した小さいモジュールで、`sys.path` に scripts/ を入れて import している
  - メモ: `git log --oneline -- plugins/spec-autopilot/scripts/stages.py` で確かめた
- 前提: transcript の区画（1280-1416）は json・re・time・datetime だけを使い、autopilot.py のほかの関数を呼ばない
  - path: plugins/spec-autopilot/scripts/autopilot.py:1280-1416
- 前提: autopilot.py の中では human_said_at（241・247）、cmd_done（1001）、done_anomalies（1434）、cmd_anomalies（1445）が区画の名前を使う
  - path: plugins/spec-autopilot/scripts/autopilot.py:237-249
  - path: plugins/spec-autopilot/scripts/autopilot.py:987-1001
  - path: plugins/spec-autopilot/scripts/autopilot.py:1419-1450
- 前提: hooks/stop.py と overnight.py は、scripts/ を sys.path に入れてから import する
  - path: plugins/spec-autopilot/hooks/stop.py:45
  - path: plugins/spec-autopilot/scripts/overnight.py:43
- 前提: stop.py は autopilot の import を main の try の中（434）と関数の中（190）に置き、import の失敗を最初の停止なら止め、続行中なら放す
  - path: plugins/spec-autopilot/hooks/stop.py:425-443
  - path: plugins/spec-autopilot/tests/test_stop_bounds.py:202-212
- 前提: trust-marker-origin（未 PR）は autopilot.py の human_said_at・require_user_after（237-279）を変える予定で、今は tests/test_autopilot.py に 20 行足しただけ。#63 は #51 と同じブランチに commands/autopilot.md の直しを足したもの
  - コマンド: `git diff main...claude/trust-marker-origin --stat` → 変えたのは docs と tests/test_autopilot.py だけ
  - コマンド: `gh pr view 63 --json headRefName` → claude/night-notes-short-run
- 前提: #51 は preflight.py に `overnight.budgets` を呼ぶ行を足し、#57 は overnight.py の input_dispatch_errors・input_handoff_errors を変える
  - コマンド: `git diff origin/main...origin/claude/night-notes-short-run -- plugins/spec-autopilot/scripts/preflight.py` → `overnight.budgets(text)` を足す
  - コマンド: `gh pr view 57 --json files` → overnight.py と test_input_kinds.py

## 作り方
この spec の ADR のとおり、目的の spec として承認し、子を 2 本に分ける。

- 子 1（R1）: 今すぐ作る。定数 `ANOMALY_KINDS` から `anomaly_line` までを新しい `scripts/transcript.py` に移す。autopilot.py の中で使う名前は冒頭の import で取り込み、human_said_at・require_user_after の本文（237-279）は 1 文字も書き換えない（trust-marker-origin と被らないため）。外の呼び出し元（stop.py・overnight.py・test_stop_bounds.py）は `transcript` を直接参照する。stop.py では、transcript の import も今の autopilot の import と同じく main の try か関数の中に置く（import の失敗の守りを外さないため）。`session_transcript`・`done_anomalies`・`cmd_anomalies` は autopilot.py に残す（prompt_file と cmd_done に絡み、循環 import になるため）。増えるのは import の行だけで、autopilot.py は約 130 行減る（#51 の 0 行・trust-marker-origin の増分を足しても 1500 行に余裕が残る）
- 子 2（R2）: #51・#63・#57 が main にマージされた後に、その時点の行番号で作る。新しい `scripts/deploy.py` に移し、外の呼び出し元は `deploy` を直接参照する。deploy.py が overnight.py の名前（awaits・budget_view など）を呼ぶなら、それも移すか、区画を狭める（子の spec で決める）

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | テストの全量を回し、`wc -l` で行数を数え、grep で autopilot.py に移した名前の定義と、外へ出し直す行が無いことを確かめる。CLI の `anomalies` を移す前と後で同じ transcript に回し、出力を突き合わせる | テストが全部通り、autopilot.py が 1400 行以下、re-export が 0 件、出力が同じ |
| R2 | 手元で実物 | テストの全量を回し、`wc -l` で行数を数え、grep で overnight.py に re-export が無いことを確かめる。CLI の `check`・`report` を移す前と後で同じ spec に回し、出力を突き合わせる | テストが全部通り、overnight.py が 1100 行以下、re-export が 0 件、出力が同じ |

## 制約
- 予算: 120 分
- 大きさ: L
- playbook: なし（挙動を変えないリファクタで、feature・bug-fix・iac・external-service のどれにも当たらない）

## モデル

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
- R2 の子を作る時点で、#51・#63・#57 のどれかがまだマージされていないとき（子を作らずに残し、朝の報告に書く）
