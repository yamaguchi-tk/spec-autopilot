# 手元で実物の証拠の `- commit:` が巡の tip と spec の置き場の中だけ違うなら、その巡の証拠として数える

- ADR: docs/adr/2026-11-28-evidence-commit-spec-only.md

## 目的
人の発言:「まとめて承認」「spec（5 案）もOK」「夜なのでできるだけ確認せずに自走して欲しい」。親の spec（2026-11-27-flow-review-goal）の R3 を受け持つ。

観測: 評価役が返った後に state を commit すると、証拠の頭の `- commit:` が `CLI review` の記録した巡の tip と合わず、check が止まった。違いは state.json の 1 行だけだった。できあがったら、spec の置き場の中だけの commit が挟まっても、評価役を回し直さずに check が通る。

## 要件
- R1: 段が手元で実物の要件の証拠（evidence/R<n>.txt）の頭の `- commit:` が、その要件の証拠として数えてよい評価役の巡（最後に high になった巡より後の巡）の sha のどれとも一致しないとき、`- commit:` の commit とその巡の sha の間で spec の置き場（docs/specs と docs/adr）の外のファイルが同じなら、`CLI check` はその証拠をその巡のものとして数える。`- commit:` の値が 7〜40 桁の 16 進でなければ、git に渡さずに今までどおり落とす。外が違うか、git で比べられない（commit が無い・読めない）なら、今までどおり「評価役の巡の tip でない」で落とす。

## 非目標
- 証拠が書かれた時刻の条件（最後の high の巡か承認より後）を緩めること
- デプロイ後の要件の証拠（`- commit:` が最後のマージの sha）の照合を変えること
- 評価役が書く `- commit:` の値を変えること（評価役の定義には触れない）
- 版数を上げること（マージの後に版数だけの PR で上げる）
- commands/autopilot.md:95 の「巡の tip の出力だけを数える」の括弧を直すこと（main と評価役が頭に書く値は今までどおり巡の tip で、手順の指示は変わらない。手順の文は兄弟の子 2 の spec が同じファイルを直すので、そちらと衝突させない）

## 影響範囲
- 変える: plugins/spec-autopilot/scripts/stages.py（全体）
  - メモ: 104-147 の checked_in_review と check、8 行目のモジュールの docstring（「評価役の巡の tip のものだけを数える」を、置き場の外が同じ commit も数える文に直す）
- 呼び出し元: plugins/spec-autopilot/scripts/deploy.py:301-312
  - メモ: stage_errors が stages.check を呼ぶ。repo の root は check の中で autopilot.repo_root(d) から取り、呼び出しの引数は変えない
- 手本: plugins/spec-autopilot/scripts/carry.py:7-21
  - メモ: same_outside と同じ pathspec（carry.OUTSIDE）で、git が 0 で終わったときだけ同じとみなす
- 変える: plugins/spec-autopilot/tests/test_stages.py（全体）
  - メモ: 既存のテストは変えず、置き場の中だけの commit・外を変えた commit・存在しない sha・16 進でない値（`--output=x` など）の場合のテストを足す
- 同じ入力: reviews
  - メモ: overnight.py の review_gate と autopilot.py の review が同じ記録を書く・読む。この spec は読み方だけを変える
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_stages.py plugins/spec-autopilot/tests/test_autopilot.py plugins/spec-autopilot/tests/test_merge_qa.py plugins/spec-autopilot/tests/test_overnight.py plugins/spec-autopilot/tests/test_rollback.py -q -n auto

## 変えない挙動
- 前の承認の巡の証拠は通さない: plugins/spec-autopilot/tests/test_stages.py::test_a_real_run_output_from_before_a_reapproval_is_refused
- fail の巡の証拠は通さない: plugins/spec-autopilot/tests/test_stages.py::test_a_real_run_output_from_a_failed_round_is_refused
- デプロイ後の要件は宣言した commit と Confirmed を求める: plugins/spec-autopilot/tests/test_stages.py::test_a_deploy_stage_pass_needs_the_declared_commit_and_confirmed

## 前提
- 目的に届く: 評価役の後に state・qa.md・証拠だけを commit した場合は check が通る。評価役の後にコードを変えた場合は今までどおり落ち、評価役を回し直す
- 運用: main は評価役が返った後、state と qa.md を commit してから check を回してよい。手順の文は変えない
- 普通のやり方: なし（この plugin に固有の証拠の照合で、外の慣習が無い）
- 過去: 承認し直しの持ち越し（reapproval-carry-merge）が、spec の置き場の外が同じかで記録を持ち越す照合を carry.py に入れた。この spec は同じ照合を証拠の commit に使う
- 前提: check は手元で実物の証拠の `- commit:` を、巡の sha と文字列（先頭 7 文字以上の前方一致）で比べ、git の中身では比べない
  - path: plugins/spec-autopilot/scripts/stages.py:104-116
- 前提: `CLI review` は、review_gate が返した tip を巡の sha として記録する
  - path: plugins/spec-autopilot/scripts/autopilot.py:1259-1266
- 前提: 証拠の頭の `- commit:` の値は、評価役（起動の prompt が渡した tip）か main が書く文字列で、check は形を検査していない（sha の形とは限らない）
  - path: plugins/spec-autopilot/agents/autopilot-reviewer.md:16、plugins/spec-autopilot/scripts/stages.py:108-116
- 前提: stages.check の呼び出し元は deploy.py の stage_errors だけ
  - コマンド: `grep -rn "stages.check(" plugins/spec-autopilot/scripts` → deploy.py:306 の 1 件

## 作り方
この spec の ADR のとおり。stages.py の checked_in_review に repo の root を渡し、数えてよい巡の sha のどれかと文字列で一致しなければ、`git diff --quiet <commit> <sha> -- <carry.OUTSIDE>` が 0 で終わる巡があるかを見る。check は root を autopilot.repo_root(d) で取って渡す。`- commit:` の値は 7〜40 桁の 16 進だけを git に渡し（`--` で pathspec と分ける）、git が 0 以外で終わる・例外は「同じでない」とする。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | 一時の git repo で spec を承認・実装・review まで進め、証拠の頭を review の tip にしたうえで、spec の置き場の中だけを commit し、証拠の頭をその新しい commit に書き直して `CLI check` を回す。spec の外を 1 行変えた commit を頭にした場合、存在しない sha を頭にした場合、`--output=<一時のパス>` を頭にした場合も回す | 置き場の中だけの場合は check が R1 の証拠を通し（終了コード 0）、外を変えた場合・存在しない sha・16 進でない値の場合は「評価役の巡の tip でない」で落ちる |

## 制約
- 予算: 45 分
- 大きさ: M
- playbook: bug-fix
- 親 spec: 2026-11-27-flow-review-goal
- 親の要件: R3
- 想定する脅威: 評価役（外の内容を読む LLM）が証拠の頭に書いた値が、git の option として読まれてファイルを書く・別の ref を指して、コードの違う巡の証拠を通す

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
- 合意した要件を満たす方法が無いと分かったとき（park に積む。どの要件も進められないときだけ block）
- 承認した自走の範囲の外の操作が要るとき（実行せずに park に積む）
