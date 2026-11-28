# ADR: 相談役・検証役・照合役も段ごとの agent の定義から setup で選ぶ

- 日付: 2026-11-28
- 状態: Accepted
- spec: docs/specs/2026-11-28-role-model-setup-advisors

## Context
人は「相談役含めて　modelとeffortをセットアップで選択可能にして」と言った。agent の定義は frontmatter で model・effort を固定し、起動で model を渡さない（別名しか受けず、effort は起動ごとに固定できない）。実装役・評価役は段ごとに定義を分けて setup で選べるが、相談役・検証役・照合役は 1 つの定義しかない。相談役は spec ごとでなくセッションの規則（SessionStart）から起動される。

## 選択肢
1. 段ごとに agent の定義を足し、setup が models.md に段を書き、SessionStart が使う名前を 1 行で示し、承認し直しの門は段の名前の集まりを数える: 実装・評価と同じ仕組みで、起動に model を渡さない規則を保つ。組は表にある段だけ
2. setup の設定から起動のときに model と effort を渡す: 任意の組を選べるが、別名の解決（sonnet が Sonnet 5 になる）と「model を渡さない」規則を崩す
3. setup が plugin の agent の定義を書き換える、または user の agents に定義を生成する: plugin の更新で消えるか、名前空間が変わって門・規則が名指しする名前と合わない

## Decision
1 を選ぶ。opus-advisor は本文と `承認:` の欄が違うので、相談の opus の段は fable-advisor の本文を写した定義にする。前の spec の ADR と同じ理由で、段の定義を選ぶ形なら model・effort が定義で決まり、門と規則が名前で数えられる。ADVISE の文は並行の spec が直しているので変えず、読み替えの 1 行を足す。相談・検証はセッションで使うので、spec の `## モデル` に写さず、SessionStart が models.md を直接読む。

- 直し方: 設計を変える
- 退けた: 要らなくする（既存の setup と spec の `## モデル` は実装・評価しか受けず、相談役の model・effort を変える道が無い）
- 退けた: 入力の約束を変える（起動に model を渡す約束にすると、別名の解決と effort の固定ができない）

## Consequences
- 段を足すたびに agent の定義の写しが増える（本文の同一はテストで見る）
- main が読み替えずに既定の agent を起動しても機械では止めない
