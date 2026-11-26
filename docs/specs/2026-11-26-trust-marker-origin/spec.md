# 信頼の印が、人の発言に origin の無い transcript で効くようにする

- ADR: docs/adr/2026-11-26-trust-marker-origin.md

## 目的
人が「trust-marker の不具合を直す」と頼んだ。人の役を別の agent が演じる run（`SPEC_AUTOPILOT_TRUST_PROMPT_RECORD=1` で hook が記録に `trust: true` を書く run）で、人の役の発言には origin が無く、subagent の報告の行にだけ origin があると、印を立てても approve が「届いたのは知らせ・subagent の報告だけ」で止まる。体験会のリハーサルでこれに当たり、承認できずに止まった。できあがったら、印を立てた run は人の役の返事で承認と再開ができ、印の無い run の判定は今のまま残る。

## 要件
- R1: hook の記録に `trust: true` があり、transcript の人の役の発言の行に origin が無く、ほかの行（subagent の報告など）に origin があるとき、`CLI approve` と `CLI resume` は、origin の無いその行の時刻が spec.md の変更（resume は wait）より後なら通す。
- R2: hook の記録に `trust: true` があっても、spec.md の変更（resume は wait）より後の発言の行が、origin の付いた知らせ・subagent の報告だけのとき、`CLI approve` と `CLI resume` は止める。

## 非目標
- 印の無い run（hook の環境に `SPEC_AUTOPILOT_TRUST_PROMPT_RECORD=1` が無い run）の判定を変えること
- hook が印を書く条件（user_prompt.py）を変えること
- 版数を上げること（体験会向けの直しがそろってから上げる）

## 影響範囲
- 変える: plugins/spec-autopilot/scripts/autopilot.py:237-279（human_said_at、require_user_after）
- 変える: plugins/spec-autopilot/hooks/user_prompt.py（全体）
  - メモ: 先頭の docstring に、印が origin のある transcript でも origin の無い発言の行で効くと書き足すだけ
- 変える: plugins/spec-autopilot/README.md（全体）
  - メモ: 56 行目の印の説明に同じことを書き足すだけ
- 呼び出し元: plugins/spec-autopilot/scripts/autopilot.py:951
- 呼び出し元: plugins/spec-autopilot/scripts/autopilot.py:1065
- 手本: plugins/spec-autopilot/scripts/autopilot.py:220-234（_human_row）
- 手本: plugins/spec-autopilot/tests/test_autopilot.py:2517-2541（印のテスト）
- 同じ入力: SPEC_AUTOPILOT_TRUST_PROMPT_RECORD
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_autopilot.py -q -k "origin or trust or human or approve or resume"

## 変えない挙動
- origin の無い transcript で印が無ければ止める: plugins/spec-autopilot/tests/test_autopilot.py::test_refuses_when_the_transcript_has_no_origin
- CLI の環境変数だけでは印にならない: plugins/spec-autopilot/tests/test_autopilot.py::test_the_cli_environment_does_not_opt_in
- 記録の印は真偽値の true だけを受ける: plugins/spec-autopilot/tests/test_autopilot.py::test_only_a_boolean_trust_mark_in_the_record_opts_in
- origin の無い transcript で印があれば通す: plugins/spec-autopilot/tests/test_autopilot.py::test_trusts_the_hook_record_when_the_driver_opts_in
- origin のある transcript で印があっても、知らせだけでは通さない: plugins/spec-autopilot/tests/test_autopilot.py::test_the_opt_in_does_not_loosen_a_transcript_with_origin

## 前提
- 目的に届く: 印を立てた run で、人の役の発言に origin が無くても承認と再開が通る。印を立てた run では、origin の無い発言の行（ci-monitor の知らせなど、host が origin を書かない知らせを含む）も人の役の発言として数える。印は人の役を agent が演じる run だけが立てるので、そこでは人の発言と知らせを見分けないことを受け入れる
- 運用: リハーサルや実験で人の役を agent が演じる人が、Claude Code を起動する側の環境に `SPEC_AUTOPILOT_TRUST_PROMPT_RECORD=1` を立てる（docs/experiments の drive.sh と同じ）
- 普通のやり方: なし（spec-autopilot に固有の承認の門で、同じ種類の普通の作り方が無い）
- 過去: 体験会のリハーサルで、印を立てても approve が止まった。人の役の発言 4 件に origin が無く、origin があったのは subagent の報告の行（kind が peer）だけだった（このセッションの前の会話で読んだリハーサルの transcript。repo の外）
- 前提: origin の付いた行が transcript に 1 つでもあると、human_said_at は人の発言の時刻を 0 で返し、require_user_after は印を見る分岐に届かずに止まる
  - path: plugins/spec-autopilot/scripts/autopilot.py:237-249（human_said_at の has_origin）
  - path: plugins/spec-autopilot/scripts/autopilot.py:270-276（印は human が None のときだけ見る）
  - 未確認: 再現は repo の外の一時のテストで回した（印を立て、origin の付いた peer の行と origin の無い「OK」の行を書いて approve すると、終了コード 1 で「届いたのは知らせ・subagent の報告だけ」と止まる）。T1 で repo のテストにする
- 前提: 対話の Claude Code の transcript にも、origin の無い発言の候補の行がある（会話の要約の行と、ci-monitor の知らせの queued_command）。そのため、印の無い run で origin の無い行を出どころ不明として扱うと、普通の承認が止まる
  - 未確認: このセッションの transcript を数えた（human 10・peer 26・task-notification 60・origin なしの要約 2・origin なしの queued_command 1）。transcript は repo の外にある
- 前提: 印は hook が、Claude Code を起動した側の環境の変数がちょうど 1 のときだけ記録に書く
  - path: plugins/spec-autopilot/hooks/user_prompt.py:35-36

## 作り方
この spec の ADR のとおり。human_said_at が、origin が human の行の最後の時刻に加えて、origin の無い発言の行の最後の時刻も返す。発言の行は _human_row と同じ候補（type が user で tool_result でなく isMeta でない行、または queued_command の attachment）で、会話の要約（isCompactSummary）を除く。require_user_after は、origin がどこかの行にあり、記録に印（`trust` が true）があるとき、どちらかの時刻が spec.md の変更（resume は wait）より後なら通す。origin がどの行にも無いときに印で記録の時刻だけで通す今の分岐は、そのまま残す。印が無いときの判定は変えない。user_prompt.py の docstring と README の印の説明に、origin のある transcript でも origin の無い発言の行で効くことを書き足す。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | 一時の repo で、hook（user_prompt.py）を `SPEC_AUTOPILOT_TRUST_PROMPT_RECORD=1` の環境で動かし、origin の付いた peer の行と origin の無い人の役の行を transcript に書いてから、本物の CLI で approve と、approve・wait の後の resume を回す。base と tip で回す | base は approve が終了コード 1 で止まり、tip は approve が通って phase が building になり、resume も通る |
| R2 | 手元で実物 | 同じ一時の repo で、印を立て、spec.md の変更の後に origin の付いた知らせ（task-notification）と peer の行だけを書いて approve と resume を回す。印を立てずに R1 と同じ transcript でも回す | 4 本とも終了コード 1 で止まり、state.json が変わらない |

## 制約
- 予算: 45 分
- 大きさ: M
- playbook: bug-fix
- 想定する脅威: 事故だけ（agent が知らせや報告で自分を承認し直すこと）。印は Claude Code を起動した側だけが立てられ、agent が意図して記録や mtime を書き換えることは閉じない（user_prompt.py の docstring のとおり）

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
