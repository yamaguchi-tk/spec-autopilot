# 相談役の description の起動の場面の例を、規則の 4 つの場面に合わせる

- 状態: 採用
- spec: docs/specs/2026-11-28-advisor-description-scenes/spec.md
- 直し方: 局所の継ぎ足し
- 退けた: 要らなくする（例を消しても、description の残りの文「人に案を選んでもらう前の相談」などの読み方が規則と食い違う元は残らないが、main が agent を選ぶときの手がかりの description から承認の門の場面が消え、門で fable-advisor を名指しする規則と description が結び付かなくなる。目的の「description と規則を食い違わせない」は、規則の場面を description に持つことで満たす）
- 退けた: 入力の約束を変える（起動の場面は規則が決めていて、description は写しなので、約束は変わらない）
- 退けた: 設計を変える（description は agent 定義の frontmatter で、Claude Code が plugin を読む時点で固定の文として読む。規則（hooks/session_start.py の文字列）から生成するには、ビルドの段か読み込みの hook が要り、この plugin にはどちらも無いので、この段では今の読み込み方のまま目的に届かない）

## 背景
PR #112 で、1 段目の相談役を回す場面を 4 つ（目的の spec の子の承認・block の後の承認し直し・人の名指し・IaC の初回の apply を含む spec）にした。fable-advisor・opus-advisor の description は、名指しの場面の例として「人に案を選んでもらう前の相談、設計判断、レビュー指摘の直し方など」を挙げたまま残った（PR #112 の評価役の low）。

## 決定
両方の description の例を「目的の spec の子の承認、block の後の承認し直し、IaC の初回の apply を含む spec の相談など」にする。人の名指しは、description の次の文が別に書いているので例に入れない。

## 結果
- description の例が、SessionStart の規則と README の表と食い違わなくなる
