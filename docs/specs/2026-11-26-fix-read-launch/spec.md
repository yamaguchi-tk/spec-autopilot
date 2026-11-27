# subagent の記録を、本文の U+2028 で割らずに読む

- ADR: docs/adr/2026-11-26-fix-read-launch.md

## 目的
人の発言:「全部終わるまで自走して欲しい」。観測した失敗: 2026-11-26-split-transcript の自走で、実装役が tests/test_stop_bounds.py（U+2028 を生の文字で持つ）を読んだ後、`overnight.py handoff` が「autopilot-implementer の起動の記録 agent-… が読めない（照合できない）」で止まった。原因は、subagent の transcript を `str.splitlines()` で割るので、JSON の文字列の中の U+2028 で 1 行が切れて JSONDecodeError になること。実装役を起動し直しても、同じファイルを読むので同じ所で止まる（その spec は blocked）。相談役の記録を読む advisor_approval.py も同じ割り方をしている。

できあがったら、subagent が何を読んでも、handoff の照合と相談役の承認の検査は transcript を最後まで読める。

## 要件
- R1: dispatch の後に起動した実装役の transcript のどれかの行（読んだファイルの中身が入る user の tool_result の行を含む）の文字列の中に、JSON の文字列に生のまま残る改行に似た文字（U+2028・U+2029・U+0085）があるとき、`overnight.py handoff` は、その記録を読めないとせず、ほかの条件（model・effort・commit）だけで判定する。
- R2: 相談役（fable-advisor・advice-checker）の transcript のどれかの行（user の tool_result の行を含む）の文字列の中に R1 の文字があるとき、`autopilot.py approve --by-advisor` は、その記録を読めないとせず、返答の `承認:`・`判定:` の行で判定する。
- R3: transcript の 1 行が JSON として壊れているとき（書きかけ・途中で切れた行）、handoff と approve --by-advisor は今までどおり読めない記録として止める。
- R4: 待ちの記録（awaits.jsonl）の行の文字列の中に R1 の文字があるとき、deploy の failure を数える判定（failed_deploys・deploy_exhausted・deploy_smoke）は、その行を飛ばさずに数える。空でないのに記録として読めない行（途中で切れた行など）があれば、数えずに通さず、ファイルと行番号を名指しして止める。読めない行があっても、壊れた本番の戻し（ready --rollback・merged --rollback・deploy の待ち・qa --smoke・rolled-back）と block と朝の報告は回る（朝の報告は、読めない間は pass の要件も done と書かず、Slack の DM の知らせにも載る）。await の書き手は、前の記録が改行で終わっていなければ改行を足してから書く（2 巡目の独立レビューの high を受けた再設計で、人が「源で止める」を選んだ）。

## 非目標
- 2026-11-26-split-transcript の実装を変えること（resume の後に handoff からやり直す）
- transcript の行の割り方を 1 つの関数にまとめること（split-transcript が transcript.py を作ってから、別の spec で扱う）
- 相談役の返答の本文から `承認:`・`判定:` の行を探す割り方（advisor_approval.py:110 の _lines_of）を変えること（この直しの後は、返答に生の U+2028 などがあると _lines_of がそこで割るので、`承認: 可` の後に U+2028 で続けた返答も `承認: 可` の行として数える。Unicode では U+2028 は行の区切りで、その行は実際にある。判定を変えるなら、別の spec で返答の割り方と止め方を決める）
- JSON が \u000b などのエスケープで書く制御文字（\x0b・\x0c・\x1c〜\x1e・\r）を扱うこと（transcript のファイルに生では残らないので、今も割れない）
- 版数を上げること（体験会向けの直しがそろってから上げる。手元の checkout には pull で届く）

## 影響範囲
（行番号は、この直しを入れた後の tip のもの）
- 変える: plugins/spec-autopilot/scripts/overnight.py:969-984（read_launch）
- 変える: plugins/spec-autopilot/scripts/advisor_approval.py:96-103（launches）
- 変える: plugins/spec-autopilot/scripts/overnight.py:652-699（awaits・deploy_floor・UNREADABLE_PROD・UnreadableAwaits・_awaits。1 巡目の独立レビューの high を人に確かめて足した）
- 変える: plugins/spec-autopilot/scripts/overnight.py:421-455（production_errors が UnreadableAwaits を「本番が良くない」として返す。マージの後なら先に戻させ、block --no-rollback で人に戻す道を残す）
- 変える: plugins/spec-autopilot/scripts/overnight.py:702-721（parked_ops・exempt_kinds が report のために strict を受ける）
- 変える: plugins/spec-autopilot/scripts/overnight.py:1123-1136（ready_rollback の CI の記録は読める行だけで見る）
- 変える: plugins/spec-autopilot/scripts/overnight.py:1170-1229（qa・rolled-back の証拠の下限は deploy_floor）
- 変える: plugins/spec-autopilot/scripts/overnight.py:1253-1306（report は読めない行を先頭に出し、block の行を落とさず、読めない間は pass の要件も done と書かない）
- 変える: plugins/spec-autopilot/scripts/overnight.py:857-861（cmd_await の書き手。2 巡目の再設計で足した）
- 変える: plugins/spec-autopilot/scripts/overnight.py:1401-1425（notify が読めない待ちの記録で落ちず、Slack の DM には朝の報告の行を、ほかの知らせには読めない行の場所を載せる）
- 呼び出し元: plugins/spec-autopilot/scripts/overnight.py:957
- 呼び出し元: plugins/spec-autopilot/scripts/advisor_approval.py:118
- 呼び出し元: plugins/spec-autopilot/scripts/overnight.py:652-657（awaits。overnight.py の 13 か所〔_awaits を直接読む deploy_floor・report・notify は別〕と、budget_view を通して hooks/stop.py・autopilot.py、production_errors を通して autopilot.py の block・wait と lineup.py の hold が呼ぶ）
- 手本: plugins/spec-autopilot/scripts/autopilot.py:1349-1356（transcript_lines。b"\n" だけで割る）
- 手本: plugins/spec-autopilot/tests/test_overnight.py:941-951（test_handoff_refuses_an_unreadable_implementer_record）
- 手本: plugins/spec-autopilot/tests/test_advisor_approval.py:202（test_approve_by_advisor_refuses_an_unreadable_record）
- 同じ入力: meta.json
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_overnight.py plugins/spec-autopilot/tests/test_advisor_approval.py plugins/spec-autopilot/tests/test_goal_child.py -q -n auto

## 変えない挙動
- 実装役と読めて transcript が壊れていれば止める: plugins/spec-autopilot/tests/test_overnight.py::test_handoff_refuses_an_unreadable_implementer_record
- ほかの agent の壊れた記録は飛ばす: plugins/spec-autopilot/tests/test_overnight.py::test_handoff_skips_a_broken_record_of_another_agent
- 相談役の壊れた記録は止める: plugins/spec-autopilot/tests/test_advisor_approval.py::test_approve_by_advisor_refuses_an_unreadable_record

## 前提
- 目的に届く: handoff と相談役の承認の検査が、本文の改行に似た文字で止まらなくなる。手元の checkout（CLI の symlink の向け先）は人が pull するまで古いままなので、split-transcript を resume できるのは pull の後
- 運用: マージの後、人が docs/pull-checkout.md の手順で手元の checkout を pull する（scripts の差分なので人が決める）。その後 split-transcript を `autopilot.py resume` してから handoff をやり直す
- 普通のやり方: JSON Lines は "\n" だけを行の区切りにする（JSON の文字列の中の U+2028 などは区切りではない。Python の str.splitlines はこれらでも割る）。この repo でも autopilot.py の transcript_lines が b"\n" だけで割っている
  - メモ: 出典は Python の公式の文書（str.splitlines の割る文字の表）と JSON Lines の仕様
- 過去: transcript の走査で同じ欠陥を直した記録が tests/test_stop_bounds.py の docstring（「本文の U+2028 や \r で割らない」）にある
- 前提: 本文に U+2028 を持つ assistant の行 1 行の transcript で、read_launch は JSONDecodeError を投げる
  - コマンド: `cd plugins/spec-autopilot/scripts && python3 -c "<本文に \u2028 を持つ assistant の 1 行を tmp の jsonl に書いて overnight.read_launch を呼ぶ>"` → JSONDecodeError
- 前提: read_launch の例外は launches で「読めない記録」になり、launch_errors が ERROR にする
  - path: plugins/spec-autopilot/scripts/overnight.py:917-926
  - path: plugins/spec-autopilot/scripts/overnight.py:960-962
- 前提: advisor_approval.launches も read_text().splitlines() で割り、読めないと ValueError にする
  - path: plugins/spec-autopilot/scripts/advisor_approval.py:96-103

## 作り方
この spec の ADR のとおり、read_launch と advisor_approval.launches が transcript を、バイトで読んで utf-8 で decode し、"\n" だけで割る（`read_bytes().decode("utf-8").split("\n")`。text mode の改行の変換を通さない。不正な UTF-8 は今までどおり記録全体を読めないとする。空の行は今までどおり飛ばす）。overnight._awaits は awaits.jsonl を `read_bytes().split(b"\n")` で割って行ごとに decode し、空でない読めない行（マルチバイトの途中で切れた行を含む）では、ファイルと行番号を名指しした UnreadableAwaits で止める（読み手を選んで止めると、通す側に倒れる読み手が残るため）。production_errors はそれを「本番が良くない」として返し（マージの後なら先にロールバックを促す）、block --no-rollback で人に戻せるようにする（本番の判定に効く spec では wait・hold は断る。ほかの範囲の spec は production_errors が先に空を返すので block も wait も今までどおり）。記録が欠けても断る側にしか倒れない読み手（ready --rollback の「CI が通った記録があるか」）は読める行だけで見る。smoke・戻しの証拠の下限（qa・rolled-back）は、読めない行があれば記録のファイルの更新の時刻も足す（どの記録よりも後なので、消えた deploy の後の証拠だけを受ける）。朝の報告は判定の門に使わないので読める行だけで組むが、読めない間は pass の要件も done と書かない。await の書き手は、前の記録が改行で終わらなければ改行を足す。autopilot.py の transcript_lines は呼ばない（split-transcript がそれを transcript.py に移すので、ここで参照を足すと載せ替えで衝突する）。

- テストは、U+2028 などを生の文字で書かず、Python の `"\u2028"` のエスケープで書く（生の文字で書くと、このテストのファイルを読んだ実装役の transcript が、直っていない手元の CLI で同じ所で切れる）

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | user の tool_result の行と assistant の行の文字列に R1 の文字を持つ実装役の transcript を tmp の CLAUDE_CONFIG_DIR に置き、`overnight.py handoff` を回す | base で「読めない」で落ち、tip で通る |
| R2 | 手元で実物 | user の tool_result の行の文字列に R1 の文字を持つ相談役の transcript を置き、`autopilot.py approve --by-advisor` を回す | base で「読めない」で落ち、tip で通る |
| R3 | 手元で実物 | 途中で切れた行の transcript で、handoff と approve --by-advisor を回す | tip でも読めない記録として止まる |
| R4 | 手元で実物 | detail に R1 の文字を持つ deploy の failure の行を awaits.jsonl に書き、failed_deploys・deploy_exhausted・deploy_smoke を呼ぶ | base で数え漏れ、tip で数える。途中で切れた行・記録でない行は tip ではファイルと行番号を名指しして止まり、切れた行の後の await の記録は新しい行に書かれ、壊れた本番の戻しと block と朝の報告は回り、朝の報告は pass の要件も done と書かない。Slack の DM の知らせには報告の行が 1 回ずつ載り、ほかの知らせには読めない行のファイルと行番号が 1 回載る |

## 制約
- 予算: 45 分
- 大きさ: M
- playbook: bug-fix

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
- この spec の handoff も手元の CLI の同じ欠陥で止まったとき（CLAUDE.md の「/autopilot が壊れていて回せないとき」として pre-pr-review に切り替え、マージは人の指示を待つ）
