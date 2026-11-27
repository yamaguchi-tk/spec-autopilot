# 親の goal が、作業ツリーで done でない子を、子のブランチの done の state とマージ済みの PR から done と読む

- ADR: docs/adr/2026-11-28-goal-reads-merged-child.md

## 目的
人の発言:「まとめて承認」「spec（5 案）もOK」「夜なのでできるだけ確認せずに自走して欲しい」。親の spec（2026-11-27-flow-review-goal）の R5 を受け持つ。

観測: 子の done の state はマージの後に子のブランチへ commit され、main に入らない。main の作業ツリーにある子の state.json はマージの前（building）のままなので、親の `goal` は子を done と読めなかった。できあがったら、子を全部マージした後に、main の作業ツリーで `goal` を打てば親を閉じられる。

## 要件
- R1: 目的の spec の子の state.json が今の作業ツリーで done でないとき、`CLI goal <親>` は、この repo のブランチのどれかで、同じ子のディレクトリの state.json が done で、その最後のマージの記録（PR の番号と commit）について、PR の記録で次の 7 つが確かめられれば、その子を done と読む: 記録の PR の番号が正の整数で、記録が戻し（rollback）でない、PR が MERGED で mergedAt がある、PR のマージの commit が記録の commit と同じ、PR の base が repo の既定のブランチ、PR の head のブランチ名が done の state を読んだブランチの名前（remote-tracking なら remote の名前を除いたもの）と同じ、PR の変更したファイルにその子のディレクトリの下のファイルがある。どれかが確かめられない（PR の記録が読めない・done の state が無い）子は、今までどおり作業ツリーの phase で読む。done と読んだ子の行には、読んだブランチと PR の番号を書く。

## 非目標
- 作業ツリーの子の state.json を書き換えること（goal は親の state だけを書く）
- 子の done の state を main に入れる手順（PR の後の commit・別の PR）を足すこと
- 子のブランチを fetch すること（今あるローカルと remote-tracking の ref だけを読む）
- 版数を上げること（マージの後に版数だけの PR で上げる）

## 影響範囲
- 変える: plugins/spec-autopilot/scripts/goal.py:121-144（cover）
  - メモ: 作業ツリーで done でない子に、新しいファイルの関数を当てる。cmd（147-186）の表の行に、読んだブランチと PR を足す
- 新規: plugins/spec-autopilot/scripts/merged_child.py
- 新規: plugins/spec-autopilot/tests/test_goal_merged.py
- 呼び出し元: plugins/spec-autopilot/scripts/goal.py:147-186
  - メモ: cmd が cover を呼ぶ。cover の呼び出し元はほかに無い
- 手本: plugins/spec-autopilot/scripts/overnight.py:600-611
  - メモ: merged の、gh pr view の state・mergedAt・mergeCommit でマージを確かめる形
- 同じ入力: merges
  - メモ: overnight.py の merged が書く記録（pr・sha）を読むだけ
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_goal.py plugins/spec-autopilot/tests/test_goal_done.py plugins/spec-autopilot/tests/test_goal_child.py plugins/spec-autopilot/tests/test_goal_command.py plugins/spec-autopilot/tests/test_goal_merged.py -q -n auto

## 変えない挙動
- 子が全部 done なら親を done にする: plugins/spec-autopilot/tests/test_goal_done.py::test_goal_marks_the_parent_done_when_every_requirement_has_a_done_child
- done でない子を挙げて親を閉じない: plugins/spec-autopilot/tests/test_goal_done.py::test_goal_refuses_while_a_child_is_not_done_and_names_it
- 子の無い要件を挙げる: plugins/spec-autopilot/tests/test_goal_done.py::test_goal_refuses_a_requirement_no_child_takes
- 読めない子を挙げて親を閉じない: plugins/spec-autopilot/tests/test_goal_done.py::test_goal_names_a_child_whose_state_json_cannot_be_read_and_does_not_finish_the_parent

## 前提
- 目的に届く: 子を全部マージし、子のブランチがローカルか remote-tracking に残っていれば、main の作業ツリーで goal が親を閉じる。子のブランチを消した後は読めないので、今までどおり閉じない
- 運用: 子を全部マージした後、main は親のディレクトリに `CLI goal` を打つ。手順の文は変えない
- 普通のやり方: マージを gh の PR の state・mergedAt・mergeCommit で確かめるのは、この plugin の merged と同じ
- 過去: 目的の spec と goal は goal-split で入り、子の state.json を作業ツリーから直に読むと決めた。範囲がマージ以上の子では done の state がマージの後に子のブランチに入るので、その読み方では閉じられない
- 前提: goal は、親と同じ置き場の子の state.json を今の作業ツリーから直に読む
  - path: plugins/spec-autopilot/scripts/goal.py:121-144
- 前提: merged は、gh で MERGED と mergedAt を確かめてから、merges に pr・sha（マージの commit）・head を記録する
  - path: plugins/spec-autopilot/scripts/overnight.py:600-611
- 前提: 範囲がマージ以上の spec は、マージしてから done にし、done の state をその後に commit する
  - path: plugins/spec-autopilot/references/after-pr.md:21、plugins/spec-autopilot/references/after-pr.md:26

## 作り方
この spec の ADR のとおり。merged_child.py に、子のディレクトリ（repo の root からの相対）を受け、`git for-each-ref refs/heads refs/remotes` の各 ref で `git show <ref>:<相対>/state.json` を読み、phase が done で merges の最後に pr と sha がある state を探す関数を置く。見つかれば `gh pr view <pr> --json state,mergedAt,mergeCommit,baseRefName,headRefName,files` で条件を確かめ、通れば (ブランチ, PR) を返す。PR の番号は int で、真偽値・0 以下・文字列は git・gh に渡さずに「確かめられない」とする。最後のマージの記録が `rollback: true` なら「確かめられない」とする。base は `gh pr view` の baseRefName と `gh repo view --json defaultBranchRef` の名前を比べる。git・gh が失敗する・読めない・例外は「確かめられない」として None を返す。探す ref はローカルのブランチと remote-tracking のブランチ（`refs/heads`・`refs/remotes`）。goal.py の cover は、作業ツリーで done でない子にだけこれを当てる。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | この repo で、マージ済みの子（2026-11-28-reapproval-carry-dispatch の PR 105、2026-11-28-size-note-at-pr の PR 106。done の state はローカルの子のブランチにだけある）に、作った関数を本物の gh で読み取りだけで当て、ブランチと PR が返ることを確かめる。あわせて、一時の git repo と PATH に置いた gh の代役で、親と子 2 本を作り、子の done の state を子のブランチにだけ commit して、main の作業ツリーで `CLI goal` を回す。片方の子の PR を未マージにした場合、マージの commit が記録と違う場合、PR の変更したファイルに子のディレクトリが無い場合、PR の base が既定のブランチでない場合、記録の PR が整数でない場合、最後の記録が rollback の場合も回す | 本物の gh では 2 本ともブランチと PR が返る。代役では、両方マージ済みで条件がそろえば親が done になり、子の行に読んだブランチと PR が出る。ほかの場合は親は done にならず、その子を done でない子として挙げる |

## 制約
- 予算: 60 分
- 大きさ: M
- playbook: feature
- 親 spec: 2026-11-27-flow-review-goal
- 親の要件: R5
- 想定する脅威: ブランチに書かれた done の state（agent が書ける）が、ほかの spec のマージ済みの PR・積んだブランチ宛ての PR・戻しの PR を指すか、PR の番号の欄に URL やオプションの形の文字列を書いて、子のマージを経ずに親を閉じる

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
