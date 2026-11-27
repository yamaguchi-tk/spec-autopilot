# 依る spec を state.json に名前で書く

## 状況
state.json は commit され、公開の repo に入る。依る spec の絶対パスを書くと手元のパスが漏れる。依る spec は別の worktree にあることがあり、repo の root からの相対パスでは引けない。

## 決定
`after` にはディレクトリ名だけを書き、読む側は、呼び出し元が持つ記録した spec（repo の外のセッションの記録）の組から名前で引き、1 本に決まらなければ block にする。値がパスでも最後の要素で引くので、前の版の値も分岐を足さずに読める。

## 退けた案
- repo の root からの相対パス: 別の worktree にある依る spec を引けない
- commit の前に hook で絶対パスを弾く: 書く側を直せば要らない
