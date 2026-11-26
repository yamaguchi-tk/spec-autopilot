# 外部サービスの最新の情報を調べ、出典を前提に残す playbook

- ADR: docs/adr/2026-11-26-playbook-latest-sources.md

## 目的
人は「AWS上でサービスを使うときは、最新情報と事例を調べてからにして欲しい」「動きが速いサービスはそうしてもらわないと困る」と言った。/autopilot の spec を書く main は playbook を読むが、今の playbook は最新の情報を調べることも、その出典を残すことも求めていない。できあがったら、外部サービスと IaC の spec の前提に、調べた出典と確認日が残り、人は承認のときに、どの時点の情報で書いた spec かを読める。

## 要件
- R1: playbook の external-service を読むとき、「spec を書くとき」は、使う機能ごとに今の公式の文書・変更の履歴（What's New・リリースノート・API の changelog）・事例を調べてから要件と前提を書くよう求め、結果を「## 前提」に `- 前提: <確かめた振る舞い>（確認日 YYYY-MM-DD）` と `  - URL: <出典>` の形で、事例を `- 普通のやり方:` の出典に残すよう求める。
- R2: playbook の iac を読むとき、「spec を書くとき」は、使う資源・引数が入った provider の版を provider の CHANGELOG で調べ、repo が固定する版（`.terraform.lock.hcl` など）と比べた結果を、R1 と同じ形で前提に残すよう求める。
- R3: R1・R2 の文が示す前提の書き方を spec の「## 前提」に写して `autopilot.py lint` を回すとき、lint はその行で ERROR を出さない。
- R4: R1・R2 の文は、利用者の手元に最新を調べる skill があればそれに従ってよいと書き、特定の skill の名前を書かない。
- R5: `plugin.json` の version を 0.1.11 より上げる。

## 非目標
- lint で確認日や出典の行を求めること
- spec の雛形（templates/spec.md）と commands/autopilot.md を変えること
- 手元の skill と hook（この repo の外）を変えること

## 影響範囲
- 変える: plugins/spec-autopilot/references/playbooks/external-service.md（全体）
  - メモ: 「spec を書くとき」の箇条に 1 つ足す
- 変える: plugins/spec-autopilot/references/playbooks/iac.md（全体）
  - メモ: 「spec を書くとき」の箇条に 1 つ足す
- 変える: plugins/spec-autopilot/.claude-plugin/plugin.json（全体）
  - メモ: version だけ
- 呼び出し元: plugins/spec-autopilot/commands/autopilot.md:69
- 呼び出し元: plugins/spec-autopilot/commands/autopilot.md:71
- 同じ入力: なし
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_playbooks.py plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py plugins/spec-autopilot/tests/test_goal_command.py -q

## 変えない挙動
- playbook の名前は references/playbooks/ のファイルで閉じる: plugins/spec-autopilot/tests/test_playbooks.py::test_the_playbooks_are_the_files_in_the_folder
- marketplace の記載は plugin.json と同じ: plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py::test_marketplace_entry_matches_manifest

## 前提
- 目的に届く: 届くのは /autopilot で spec を書く作業だけで、spec を書かない作業には届かない（そちらは利用者の手元の skill と hook が受け持つ）。軽量フロー（L）は B の 1 を通らないので、この 2 つの箇条は届かない（commands/autopilot.md を変えないので範囲の外にする）。lint は検査しないので、守られるかは承認のときに人が前提を読んで確かめる
- 運用: /autopilot の main が A の 0 で playbook を読み、B の 1 で前提を書くときに従う。人は承認のときに前提の出典と確認日を読む
- 普通のやり方: Terraform の AWS provider は、版ごとの新しい資源・引数を CHANGELOG に書く（https://github.com/hashicorp/terraform-provider-aws/blob/main/CHANGELOG.md）。AWS の新しい機能は What's New に出る（https://aws.amazon.com/new/）
- 過去: playbook の 2 つのファイルは、private repo から切り出した後に変わっていない（`git log -- plugins/spec-autopilot/references/playbooks/` で e4afa9c だけ）
- 前提: external-service の「spec を書くとき」は、本物で確かめる手順・代役・エラーコードの区別・Slack の表示を求め、最新の情報を調べることと出典を残すことは求めていない
  - path: plugins/spec-autopilot/references/playbooks/external-service.md:5-10
- 前提: iac は道具の版を repo の固定に合わせるとだけ書き、使う引数が入った provider の版との突き合わせは求めていない
  - path: plugins/spec-autopilot/references/playbooks/iac.md:12
- 前提: lint は前提の URL の行に URL だけを受け、後ろに文字を書けない。前提の文の行には括弧の注記を書ける
  - path: plugins/spec-autopilot/scripts/autopilot.py:71（前提の行）、plugins/spec-autopilot/scripts/autopilot.py:75（URL の行）
- 前提: main は、外部サービスと IaC の要件で、playbook の選びによらずこの 2 つの「spec を書くとき」に従う
  - path: plugins/spec-autopilot/commands/autopilot.md:69、plugins/spec-autopilot/commands/autopilot.md:71

## 作り方
この spec の ADR のとおり。external-service.md と iac.md の「spec を書くとき」に箇条を 1 つずつ足し、前提の書き方の例を 1 つずつ示す。plugin.json の version を 0.1.12 にする（description は変えないので marketplace.json は変えない）。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | 評価役が external-service.md の「spec を書くとき」を読む | 公式の文書・変更の履歴・事例を調べてから書く文と、確認日つきの前提の行・URL の行・普通のやり方の出典の形がある |
| R2 | 手元で実物 | 評価役が iac.md の「spec を書くとき」を読む | provider の CHANGELOG で入った版を調べ、repo が固定する版と比べて前提に残す文がある |
| R3 | 手元で実物 | 2 つの playbook の例を、`autopilot.py init` で作った一時の spec の「## 前提」に写し、`autopilot.py lint` を回す | 写した行で前提の形の ERROR が出ない |
| R4 | 手元で実物 | 評価役が 2 つの playbook の足した文を読む | 手元の skill に従ってよいとあり、特定の skill の名前が無い |
| R5 | 手元で実物 | plugin.json を読み、回帰テストを回す | version が 0.1.11 より上で、回帰テストが通る |

## 制約
- 予算: 45 分
- 大きさ: M
- playbook: なし（playbook の文書を足すだけで、当たる種類が無い）

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
