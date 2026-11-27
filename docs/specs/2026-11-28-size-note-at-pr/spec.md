# 大きさが L の NOTE を、PR を作る前の `check --stage pr` でも出す

- ADR: docs/adr/2026-11-28-size-note-at-pr.md

## 目的
人の発言:「まとめて承認」「spec（5 案）もOK」「夜なのでできるだけ確認せずに自走して欲しい」。親の spec（2026-11-27-flow-review-goal）の R4 を受け持つ。

観測: 「大きさが L になった」の NOTE は `done` だけが出す。範囲がマージ以上の spec では done はマージの後なので、PR を分けるかを決める段（PR を作る前）より後に NOTE が出た。できあがったら、PR を作る前の検査で、分けるかを決められる。

## 要件
- R1: 申告の大きさか数えた大きさが L のとき（大きさの行が読めないときは L とみなす。done と同じ）、`CLI check <dir> --stage pr` は、`大きさが L になった` で始まる NOTE を、申告と数えた大きさの説明と一緒に出す。申告も数えた大きさも L でないときは、その NOTE を出さない。NOTE は check の終了コードを変えない。

## 非目標
- `CLI done` が出す NOTE を消すこと（範囲が「PR まで」の spec では、今までどおり done でも出す）
- `CLI check` の既定（`--stage` なし）で NOTE を出すこと
- L の spec を check で止めること
- 版数を上げること（マージの後に版数だけの PR で上げる）

## 影響範囲
- 変える: plugins/spec-autopilot/scripts/autopilot.py:1016-1050（cmd_check、cmd_done）
  - メモ: cmd_done の大きさの判定（1036-1047）を新しいファイルの関数に移し、cmd_done と cmd_check（stage が pr のとき）から呼ぶ。autopilot.py は 1391 行なので、移して行を減らす
- 新規: plugins/spec-autopilot/scripts/size_note.py
- 変える: plugins/spec-autopilot/commands/autopilot.md（全体）
  - メモ: 102 行（C の 5 の PR）と 112 行（戻ったときの PR）。どちらも NOTE の出どころを `CLI done` だけと書いているので、「`CLI check <dir> --stage pr` か `CLI done` が出したら」に直す
- 変える: plugins/spec-autopilot/tests/test_size.py（全体）
  - メモ: 既存のテストは変えず、check --stage pr の L と M の場合のテストを足す
- 呼び出し元: plugins/spec-autopilot/scripts/autopilot.py:1352
  - メモ: check のサブコマンドの `--stage` の引数
- 手本: plugins/spec-autopilot/scripts/autopilot.py:1036-1047
- 別の実装: plugins/spec-autopilot/scripts/autopilot.py:1000-1013
  - メモ: cmd_size が同じ大きさの行と影響範囲から大きさを数える（評価役の観点 8 用。数えられないときは ERROR で L に倒す）。出力の形と終了コードが違うので size_note.py とは共有せず、そのまま残す
- 同じ入力: stated_size、counted_size
  - メモ: どちらも spec.md の制約の大きさの行と影響範囲を読む。state の記録は変えない
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_size.py plugins/spec-autopilot/tests/test_autopilot.py plugins/spec-autopilot/tests/test_stages.py plugins/spec-autopilot/tests/test_merge_qa.py -q -n auto

## 変えない挙動
- done が L の NOTE を出す: plugins/spec-autopilot/tests/test_size.py::test_a_reapproval_does_not_look_at_the_size_and_done_says_to_split_the_pr
- done は読めない大きさの行を L とみなす: plugins/spec-autopilot/tests/test_size.py::test_done_treats_an_unreadable_size_line_as_large
- 新しい repo の done も L の NOTE を出す: plugins/spec-autopilot/tests/test_size.py::test_a_new_repo_reapproval_passes_a_declared_large_size_and_done_says_to_split_the_pr

## 前提
- 目的に届く: PR を作る前の check で NOTE が出るので、main は PR を作る前に分けるかを決められる。分けるかを main が決める段の手順の文も同じ PR で直す
- 運用: main は C の 4 で `check --stage pr` の出力を読み、NOTE があれば 5 で stacked PR に分ける
- 普通のやり方: なし（この plugin に固有の大きさの数え方で、外の慣習が無い）
- 過去: L の NOTE は、自走の途中で育った L と合意し直しの L を PR の前に知らせるために done に入った。範囲がマージ以上の spec では done がマージの後に回るので、その目的に届いていない
- 前提: L の NOTE（SPLIT_PR）を出すのは cmd_done だけで、check は大きさを数えない
  - path: plugins/spec-autopilot/scripts/autopilot.py:556
  - path: plugins/spec-autopilot/scripts/autopilot.py:1036-1047
- 前提: 範囲がマージ以上の spec は、C の 4 で `check --stage pr` を通し、done にせずに PR を作る
  - path: plugins/spec-autopilot/commands/autopilot.md:101
- 前提: cmd_check は check の (errors, notes) を report に渡して出す
  - path: plugins/spec-autopilot/scripts/autopilot.py:1016-1018

## 作り方
この spec の ADR のとおり。cmd_done の 1036-1047 を size_note.py の関数（autopilot の module と spec のディレクトリと state を受け、出す NOTE の行の一覧を返す）に移す。cmd_done はその行を今までどおり出し、cmd_check は stage が pr のときにその行を notes に足して report に渡す。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | 一時の git repo で、申告 M で差分が L に育った spec と、申告 M で M のままの spec を作り、それぞれ `CLI check <dir> --stage pr` を回す。申告を L にした spec でも回す | L に育った spec と申告 L の spec では `大きさが L になった` の NOTE が出て、M のままの spec では出ない。どれも終了コードは NOTE の有無で変わらない |

## 制約
- 予算: 45 分
- 大きさ: M
- playbook: feature
- 親 spec: 2026-11-27-flow-review-goal
- 親の要件: R4

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
