# subagent の記録を、本文の U+2028 で割らずに読む

- ADR: docs/adr/2026-11-26-fix-read-launch.md

## 目的
人の発言:「全部終わるまで自走して欲しい」。観測した失敗: 2026-11-26-split-transcript の自走で、実装役が tests/test_stop_bounds.py（U+2028 を生の文字で持つ）を読んだ後、`overnight.py handoff` が「autopilot-implementer の起動の記録 agent-… が読めない（照合できない）」で止まった。原因は、subagent の transcript を `str.splitlines()` で割るので、JSON の文字列の中の U+2028 で 1 行が切れて JSONDecodeError になること。実装役を起動し直しても、同じファイルを読むので同じ所で止まる（その spec は blocked）。相談役の記録を読む advisor_approval.py も同じ割り方をしている。

できあがったら、subagent が何を読んでも、handoff の照合と相談役の承認の検査は transcript を最後まで読める。

## 要件
- R1: dispatch の後に起動した実装役の transcript のどれかの行（読んだファイルの中身が入る user の tool_result の行を含む）の文字列の中に、JSON の文字列に生のまま残る改行に似た文字（U+2028・U+2029・U+0085）があるとき、`overnight.py handoff` は、その記録を読めないとせず、ほかの条件（model・effort・commit）だけで判定する。
- R2: 相談役（fable-advisor・advice-checker）の transcript のどれかの行（user の tool_result の行を含む）の文字列の中に R1 の文字があるとき、`autopilot.py approve --by-advisor` は、その記録を読めないとせず、返答の `承認:`・`判定:` の行で判定する。
- R3: transcript の 1 行が JSON として壊れているとき（書きかけ・途中で切れた行）、handoff と approve --by-advisor は今までどおり読めない記録として止める。

## 非目標
- 2026-11-26-split-transcript の実装を変えること（resume の後に handoff からやり直す）
- transcript の行の割り方を 1 つの関数にまとめること（split-transcript が transcript.py を作ってから、別の spec で扱う）
- 相談役の返答の本文から `承認:`・`判定:` の行を探す割り方（advisor_approval.py:110 の _lines_of）を変えること（返答は相談役が書く文で、読んだファイルの中身は入らない。U+2028 で割っても行の頭の判定は変わらない向きにしか効かない）
- JSON が \u000b などのエスケープで書く制御文字（\x0b・\x0c・\x1c〜\x1e・\r）を扱うこと（transcript のファイルに生では残らないので、今も割れない）
- 版数を上げること（体験会向けの直しがそろってから上げる。手元の checkout には pull で届く）

## 影響範囲
- 変える: plugins/spec-autopilot/scripts/overnight.py:931-946（read_launch）
- 変える: plugins/spec-autopilot/scripts/advisor_approval.py:96-103（launches）
- 呼び出し元: plugins/spec-autopilot/scripts/overnight.py:919
- 呼び出し元: plugins/spec-autopilot/scripts/advisor_approval.py:118
- 手本: plugins/spec-autopilot/scripts/autopilot.py:1349-1356（transcript_lines。b"\n" だけで割る）
- 手本: plugins/spec-autopilot/tests/test_overnight.py:930-940（test_handoff_refuses_an_unreadable_implementer_record）
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
この spec の ADR のとおり、read_launch と advisor_approval.launches が transcript を、手本の transcript_lines と同じくバイトで読んで b"\n" だけで割る（`read_bytes().split(b"\n")` を行ごとに utf-8 で読む。text mode の改行の変換を通さない。空の行は今までどおり飛ばす）。autopilot.py の transcript_lines は呼ばない（split-transcript がそれを transcript.py に移すので、ここで参照を足すと載せ替えで衝突する）。

- テストは、U+2028 などを生の文字で書かず、Python の `" "` のエスケープで書く（生の文字で書くと、このテストのファイルを読んだ実装役の transcript が、直っていない手元の CLI で同じ所で切れる）

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | user の tool_result の行と assistant の行の文字列に R1 の文字を持つ実装役の transcript を tmp の CLAUDE_CONFIG_DIR に置き、`overnight.py handoff` を回す | base で「読めない」で落ち、tip で通る |
| R2 | 手元で実物 | user の tool_result の行の文字列に R1 の文字を持つ相談役の transcript を置き、`autopilot.py approve --by-advisor` を回す | base で「読めない」で落ち、tip で通る |
| R3 | 手元で実物 | 途中で切れた行の transcript で、handoff と approve --by-advisor を回す | tip でも読めない記録として止まる |

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
