# ADR: subagent の途中の完了は、main の transcript に最後に届いた host の知らせで見分ける

- 日付: 2026-11-27
- 状態: Accepted
- spec: docs/specs/2026-11-27-stop-hook-interim-finished

## Context
Stop hook の `_running` は、host が meta.json に finished を真で書いた subagent を終わったとみなす。再現すると、host は、subagent が自分の background の作業を待って turn を終えた途中の完了でも finished を真で書き、再開で消し、最終の報告の後にまた書いた。途中と最終の meta.json は同じ中身なので、meta.json だけでは見分けられない。そのため途中の完了の後、hook は timer が生きていても完了の検査の不足で止め続けた（直近 3 日で 20 件）。

## 選択肢
1. main の transcript を順に読み、agent ごとに最後に届いた host の知らせが途中の完了（summary が `is waiting on its own background work` の task-notification）なら、finished があっても待ち中に数える。終わりの task-notification・hand-back の行・起動・再開で印を下ろす: 文言は host が変えうるが、拾えなければ今と同じく止める側に倒れる。text で終える subagent も、終わりの通知で終わったと分かる
2. subagent の transcript に起動・再開より後の SubagentHandback の呼び出しがあるときだけ終わったとみなす: 文言に頼らないが、報告の道具を持たない agent・fork は text で終える（直近 36 時間で 1,237 件中 41 件）。それらの終わりを最大 15 分待ち中と取り違え、その間 timer があれば放す（main が起きない時間が延びる）
3. finished を読まず、transcript の新しさだけで決める: 終わった agent を最大 15 分待ち中に数え、その間 timer があれば放し続ける
4. 直さない（main が途中の完了の後に poll しないよう手順で縛る）: 手順は poll を禁じているのに起きているので、止め方が変わらない限り直らない

## Decision
1 を選ぶ。R1 の「host がその途中の完了を main に知らせたとき」を、その知らせで直接読む。R2 の「報告の道具を使わずに text で終えたとき」を、2 は満たせない（終わりを 15 分取り違える）。拾いそこねたときは今の動き（止める）に戻るので、直しが今より悪い方向に働くのは、偽の知らせを書かれたときだけになる。

- 直し方: 局所の継ぎ足し
- 退けた: 要らなくする（finished を読むのをやめると、終わった agent を最大 15 分待ち中に数えて放し続ける。案 3）
- 退けた: 入力の約束を変える（host の meta.json と通知は Claude Code が書くもので、この repo からは変えられない）
- 退けた: 設計を変える（timer と transcript の新しさで待ち中を決める今の設計は、途中の完了の見分けを足せば目的に届く）
- 要件の文で退けた: 局所の継ぎ足しのうち案 2（R2 の「報告の道具を使わずに text で終えたとき」）

## Consequences
- 途中の完了の後、hook は timer が生きていれば放し、無ければ timer を求める
- host が通知の文言を変えると、途中の完了を見分けられなくなり、今と同じく止める動きに戻る（壊れ方は止める側）
- 途中の完了の後、subagent の background の作業が 15 分を超えて transcript が書かれないと、今までどおり終わったとみなす
