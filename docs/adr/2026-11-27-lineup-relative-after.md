# 依る spec を state.json に名前で書く

## 状況
state.json は commit され、公開の repo に入る。依る spec の絶対パスを書くと手元のパスが漏れる。依る spec は別の worktree にあることがあり、repo の root からの相対パスでは引けない。

## 決定
`after` にはディレクトリ名だけを書き、読む側は、呼び出し元が持つ記録した spec（repo の外のセッションの記録）の組から名前で引き、1 本に決まらなければ block にする。値がパスでも最後の要素で引くので、前の版の値も分岐を足さずに読める。

## 退けた案
- repo の root からの相対パス: 別の worktree にある依る spec を引けない
- commit の前に hook で絶対パスを弾く: 書く側を直せば要らない

## 実装中に変えた決定（2026-11-27）
done・block の `release` が依る spec をセッションの記録から外すので、記録だけから名前で引くと、依る spec の done の後に後の spec が必ず block になった。そこで、enqueue のときに「後の spec の絶対パス → 依る spec の絶対パス」の対を repo の外（`SPEC_AUTOPILOT_HOME` の下）に書き、読む側はまず記録から名前で引き、無ければその対から引く（対の先の名前が `after` と同じときだけ使う）。どちらでも 1 本に決まらなければ block にする。
退けた案: 各 worktree の `docs/specs/<名前>` を探す（後の spec の worktree には、枝分かれした時点の古い state の写しがあり、取り違える）。release で外さない（Stop hook の記録の意味が変わる）。
