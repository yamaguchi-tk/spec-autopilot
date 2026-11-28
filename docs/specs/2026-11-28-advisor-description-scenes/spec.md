# 相談役の description の起動の場面の例を、規則の 4 つの場面に合わせる

- ADR: docs/adr/2026-11-28-advisor-description-scenes.md

## 目的
人の発言:「ここで直す」（PR #112 の後、相談役の description に残った場面の例を直すかの問いへの答え）。PR #112 で 1 段目の相談役を回す場面を 4 つにしたが、fable-advisor・opus-advisor の description は「レビュー指摘の直し方など」を例に挙げたまま残った。直すと、description と SessionStart の規則が食い違わなくなる。

## 要件
- R1: agents/fable-advisor.md と agents/opus-advisor.md の description が名指しの場面の例を挙げるとき、例は目的の spec の子の承認・block の後の承認し直し・IaC の初回の apply を含む spec の相談であり、「レビュー指摘の直し方」「設計判断」を含まない。
- R2: 2 つの agent の model・effort・tools の frontmatter と、description のほかの文は変わらない。

## 非目標
- 本文（frontmatter の外）と README を変えること
- 版数を上げること

## 影響範囲
- 変える: plugins/spec-autopilot/agents/fable-advisor.md:8（description）
- 変える: plugins/spec-autopilot/agents/opus-advisor.md:8（description）
- 呼び出し元: なし
- 手本: plugins/spec-autopilot/README.md:43
- 同じ入力: なし
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_advisors.py plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py -q

## 変えない挙動
- 相談役の model と effort の固定: plugins/spec-autopilot/tests/test_advisors.py

## 前提
- 目的に届く: description は main が agent を選ぶ手がかりで、起動の場面を決めるのは SessionStart の規則なので、直すのは写しだけ
- 運用: なし（文の直しで、運用は変わらない）
- 普通のやり方: なし（この plugin に固有の agent 定義の文）
- 過去: PR #112 の評価役が、description の例が 4 つの場面と食い違うと low で挙げた
- 前提: README の表は fable-advisor の 1 段目を 4 つの場面と書いている
  - path: plugins/spec-autopilot/README.md:43

## 作り方
この spec の ADR のとおり。2 つの description の括弧の中の例を置き換える。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | 2 つのファイルの 8 行目（description）を `sed -n 8p` で読んで grep する（本文の 24 行目は、人が名指ししたときに受ける判断の種類の文で、非目標のとおり変えない） | 「レビュー指摘の直し方」「設計判断」が当たらず、3 つの場面の例が当たる |
| R2 | 手元で実物 | git diff と test_advisors.py を回す | 差分が description の括弧の中だけで、テストが通る |

## 制約
- 予算: 45 分
- 大きさ: M
- playbook: なし（agent 定義の文の直しで、当たる種類が無い）

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
- 合意した要件を満たす方法が無いと分かったとき
