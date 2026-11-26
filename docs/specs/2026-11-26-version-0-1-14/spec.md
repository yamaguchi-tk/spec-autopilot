# plugin の版数を 0.1.14 に上げる

- ADR: docs/adr/2026-11-26-version-0-1-14.md

## 目的
人が「0.1.14 に上げる」と頼んだ。PR 51・63・57・58・66（短い run の夜の NOTE、/autopilot の文書、入力の表の文言、実装役の定義、信頼の印）は、版数を 0.1.13 にした commit 8a038fa の後に main に入ったので、marketplace から plugin を入れた人には届かない。版数を上げると、入れた人の更新でこれらの直しが届く。明日の体験会の参加者にも、新しく入れる時点で届く。

## 要件
- R1: main の plugin.json の版数が 0.1.13 のとき、この PR の後の plugin.json の版数は 0.1.14 になり、marketplace.json の spec-autopilot の項目の name・description は plugin.json と同じままである。

## 非目標
- plugin.json の description やほかの欄を変えること
- marketplace.json を変えること（版数の欄を持たない）

## 影響範囲
- 変える: plugins/spec-autopilot/.claude-plugin/plugin.json（全体）
  - メモ: version の 1 行だけ
- 変える: plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py:67-69（test_version_is_raised_past_0_1_12）
  - メモ: 版数が 0.1.13 を超えたことを確かめるテストに置き換えるだけ（0.1.12 を超えたことはこれに含まれる）
- 呼び出し元: plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py:23-36
  - メモ: plugin.json を読む既存のテスト（semver と、marketplace.json との name・description の一致）
- 手本: plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py:67-69（版数が前の版を超えたことを確かめるテスト）
- 同じ入力: なし
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py plugins/spec-autopilot/tests/test_goal_command.py -q

## 変えない挙動
- plugin.json は semver の版数と name を持つ: plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py::test_manifest_has_semver_and_name
- marketplace.json の項目は plugin.json と name・description がそろう: plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py::test_marketplace_entry_matches_manifest

## 前提
- 目的に届く: 版数を上げると、marketplace から入れた人の更新で 5 本の PR の直しが届く。手元の checkout を symlink で使う人には、版数によらず pull で届く
- 運用: main へのマージで marketplace から新しく入れる人に届き、版数を上げたものは入れた人の更新にも届く（CLAUDE.md の自走の範囲の説明）
- 普通のやり方: なし（この repo の版数の上げ方に従うだけで、比べる普通の作り方が無い）
- 過去: 版数は別の PR で 1 つずつ上げてきた（PR 64 で 0.1.12 から 0.1.13。spec は docs/specs/2026-11-26-version-0-1-13）
- 前提: main の plugin.json の版数は 0.1.13 で、0.1.13 にした commit 8a038fa の後に plugin の中身（テストを除く）が 10 ファイル変わった
  - path: plugins/spec-autopilot/.claude-plugin/plugin.json:3
  - コマンド: `git diff --stat 8a038fa origin/main -- plugins/ ':!plugins/spec-autopilot/tests'` → README.md・agents の実装役 4 つ・commands/autopilot.md・hooks/user_prompt.py・scripts の autopilot.py・overnight.py・preflight.py の 10 ファイル
- 前提: marketplace.json は版数の欄を持たない
  - コマンド: `grep -n version .claude-plugin/marketplace.json` → 当たりなし
- 前提: 開いている PR に plugin.json を変えるものは無い
  - コマンド: `gh pr list --state open --json number,files` → plugin.json を含む PR なし

## 作り方
この spec の ADR のとおり。plugin.json の version を 0.1.14 にする。test_spec_autopilot_wiring.py の test_version_is_raised_past_0_1_12 を、版数が 0.1.13 を超えたことを確かめるテスト（test_version_is_raised_past_0_1_13）に置き換える。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | 置き換えたテストと回帰テストを base と tip で回し、tip の plugin.json の version と、marketplace.json の項目との name・description の一致を読む | base で置き換えたテストが落ち、tip で通る。tip の version が 0.1.14 で、name・description が一致する |

## 制約
- 予算: 30 分
- 大きさ: S
- playbook: なし（版数を上げるだけで、種類に当たる playbook が無い）

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
