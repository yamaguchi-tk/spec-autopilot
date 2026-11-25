# ADR: 実装役の既定を Sonnet の effort high にし、sonnet-low の段を消す

- 日付: 2026-11-25
- 状態: Accepted
- spec: docs/specs/2026-11-25-implementer-default-high

## Context
この repo の 5 本の spec で、既定の Sonnet low の実装の直後のレビューに high が出たのは 16 回中 9 回、sonnet-high では 4 回中 1 回だった。high 1 回で 1 巡（30〜50 分）増え、5 本中 4 本が予算を超えた。Sonnet low を既定にした根拠は、S の小さい spec での計測だった。人は既定を high に変えてよいと決めた。（回数の訂正は Consequences の末尾）

## 選択肢
1. **sonnet-low の段を消し、`autopilot-implementer` の effort を high にする。`autopilot-implementer-high` の定義は消す**
   - 得るもの: 既定の agent の名前が変わらないので、hook・handoff・文書の既定の書き方がそのまま正しい。段の並びは「先頭が既定」のまま
   - 失うもの: 安い sonnet-low を spec で選べなくなる。梯子の段が 1 つ減る
2. **段の並びはそのままにし、既定の段を別の定数で sonnet-high にする**
   - 得るもの: spec で sonnet-low を選べる
   - 失うもの: 「先頭が既定」の約束が崩れ、climb と impl_agent に既定の分岐が要る。sonnet-low を選ぶ spec を今は誰も書いていない
3. **既定の agent の名前を `autopilot-implementer-high` に変える**
   - 失うもの: hook・commands・README・small-prototype.md の既定の名前を全部書き換えることになる

## Decision
1 を選ぶ。安い段が要る spec が出てきたら、そのときに段を足す。

## Consequences
- `## モデル` に `- 実装: sonnet-low` と書いた spec は lint が ERROR にする
- 実装の費用は、既定で Sonnet の effort high のぶん増える
- 効き目は、マージの後の spec の runs.jsonl で測る
- 訂正（2026-11-26）: Context の回数は数え違いだった。対象は requirement-how-check・s-prototype-gate・evidence-name-separators・fix-order-park・input-kinds-table の 5 本の state.json で、handoff で閉じた dispatch（`handoffs[].dispatch`）ごとに、その後の最初のレビューの high がその dispatch の要件と重なるかを数えた。Sonnet low は 17 回中 10 回、sonnet-high は 4 回中 2 回、opus-medium は 2 回中 0 回だった。1 回のレビューを、その前の複数の dispatch で数えている（レビューごとに数えると low は 9 回中 8 回、sonnet-high は 4 回中 2 回）。sonnet-high と opus-medium は、この 5 本では原因調査の後の直しの巡でしか使っていない。差は小さくなるが、Decision は変えない
- 効き目の測り方（2026-11-26 に書き分けた）: high の率は、マージの後の spec の state.json の dispatches・handoffs・reviews を上と同じ数え方で数える。分数は runs.jsonl の active_min で測る（runs.jsonl には high の欄が無い）
