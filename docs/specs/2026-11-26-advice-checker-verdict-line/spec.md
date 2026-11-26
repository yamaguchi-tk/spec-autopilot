# advice-checker の判定の行の形を、定義の中で 1 つにする

- ADR: docs/adr/2026-11-26-advice-checker-verdict-line.md

## 目的
人が「判定の行の括弧が欠ける件を直して」と頼んだ。PR 39 の直していない low の 2（advice-checker の返答のうち 8 本が、判定の行の `（確かめられない <n> / <主張の数>）` を欠いた）を閉じる。夜の承認し直しの門は括弧つきの形だけを通すので、括弧が欠けると夜の承認し直しが通らない。今の定義は、出力の節（34 行目）が括弧つきの形を求める一方で、守ることの節（28 行目）が括弧なしの `判定: 反証なし` を書いていて、形を 2 か所で食い違って書いている。できあがったら、定義が判定の行の形を出力の節の 1 か所だけで決め、その形が門の通す形と合う。

## 要件
- R1: advice-checker.md の出力の節が示す判定の行の形（`判定:` に `反証なし` と `（確かめられない <n> / <主張の数>）` を続けたもの）を、確かめられない 0 で埋めて返答に使うとき、`approve --by-advisor` は通る。加えて、出力の節の外の文には、判定の行の形（`判定: 反証あり` か `判定: 反証なし` で始まる literal）が 1 つも無い。
- R2: advice-checker.md の守ることの節で、反証が見つからないときの判定は、下の出力の節の形で書くよう指す文になり、判定の行の形を自分では書かない。

## 非目標
- 門（plugins/spec-autopilot/scripts/advisor_approval.py）を変えること。括弧の無い `判定: 反証なし` を通すようにはしない
- version を上げること（別の PR で上げる）
- 途中で終わって返答の文が無い起動への手当て（門は止まる側に倒れる）

## 影響範囲
- 変える: plugins/spec-autopilot/agents/advice-checker.md（全体）
  - メモ: 守ることの節の、反証が見つからないときの 1 行だけ
- 呼び出し元: plugins/spec-autopilot/scripts/advisor_approval.py:132-140
  - メモ: 定義を読むのではなく、定義に従った返答の判定の行を読む門
- 手本: plugins/spec-autopilot/tests/test_advisor_approval.py:333-346（fable-advisor.md の出力の欄の形を、コードが読む形と突き合わせるテスト）
- 同じ入力: なし
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_advisor_approval.py plugins/spec-autopilot/tests/test_advisors.py -q -n auto

## 変えない挙動
- 反証あり・確かめられない 1 以上・判定の行が無い返答では、夜の承認し直しが通らない: plugins/spec-autopilot/tests/test_advisor_approval.py::test_approve_by_advisor_refuses_when_a_condition_is_missing
- 相談役 3 本の front matter が決めた値のまま: plugins/spec-autopilot/tests/test_advisors.py::test_agent_front_matter

## 前提
- 目的に届く: 定義の中の食い違いは無くなる。直す前からすでに、定義を直した commit 012c423 の後に起動した 87 本のうち 86 本は括弧つきで、残る 1 本は返答の文が無い途中で終わった起動なので、件数の差は出にくい
- 運用: advice-checker は、SessionStart の相談役の規則と /autopilot の夜の承認し直しから起動され、この定義を読んで返答を書く
- 普通のやり方: なし（agent の定義の文言の直しで、比べる普通の作り方が無い）
- 過去: PR 39 の本文の直していない low の 2 で、手元の advice-checker の返答 66 本のうち 8 本が括弧を欠いたと記録した。括弧を足した定義の変更は commit 012c423（2026-11-24 01:16 UTC）
- 前提: 括弧の欠けた返答は、すべて 2026-11-24T02:06 UTC 以前に起動したもので、それより後に起動した 87 本のうち括弧の欠けは 0 本
  - コマンド: `~/.claude/projects/*/*/subagents/ の advice-checker の meta.json と transcript を読み、最後の返答の判定の行を数える python3 の 1 回限りのスクリプト` → 95 本のうち括弧なし 8 本（最初の行の時刻が 2026-11-23T12:17〜2026-11-24T02:06）と返答の文なし 1 本（2026-11-25T14:25）
- 前提: advice-checker.md の 28 行目は括弧の無い `判定: 反証なし` を書き、34 行目は括弧つきの形を求める
  - path: plugins/spec-autopilot/agents/advice-checker.md:28
  - path: plugins/spec-autopilot/agents/advice-checker.md:34
- 前提: 門は `判定: 反証なし（確かめられない 0 / <n>）` の形だけを通す
  - path: plugins/spec-autopilot/scripts/advisor_approval.py:132-140

## 作り方
この spec の ADR のとおり。advice-checker.md の 28 行目を「反証が見つからなければ、下の出力の形で `反証なし` と判定し、主張ごとの結果は書く。同意の理由は足さない」のように、判定の行の literal を外して出力の節を指す文にする（形の正本を 34 行目の 1 か所にする）。test_advisor_approval.py の「文書の形とコードが読む形の突き合わせ」に、fable-advisor.md の突き合わせと同じ形のテストを足す。advice-checker.md を `\n## 出力` で前後に分け、出力の節から `判定:`・`反証なし`・`（確かめられない <n> / <主張の数>）` を読み出し（読み出せなければ落とす）、`<n>` を 0・`<主張の数>` を 3 で埋めた行を返答にして approve を打つ。前の部分では、バッククォートで囲んだ `判定: 反証あり` か `判定: 反証なし` で始まる literal を数え、0 であることを確かめる。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | 足したテストを base（28 行目を戻した定義）と tip で回す。テストは出力の節から `判定:`・`反証なし`・括弧の形の 3 つが読み出せることを確かめてから、それで組んだ行で approve を打ち、出力の節の外に判定の literal があるかを数える | base で落ち（出力の節の外に literal が 1 つある）、tip で通る（読み出しが 3 つとも当たり、approve が通り、出力の節の外の literal が 0） |
| R2 | 手元で実物 | tip の advice-checker.md の守ることの節を読み、反証が見つからないときの文が出力の節を指していて、判定の行の literal を持たないことを確かめる。回帰テストを回す | 文が出力の節を指し、回帰テストが通る |

## 制約
- 予算: 30 分
- 大きさ: S
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
