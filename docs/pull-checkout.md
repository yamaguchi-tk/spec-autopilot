# 手元の checkout の pull

plugin を使う手元の checkout（symlink の向け先）を pull するときの手順。pull は自走の範囲に入れず、人が頼んだときに行う。

取り込むと、全セッションの hook・CLI・agent の定義・commands・references・templates がその場で変わる。並列で回していると、自走中のセッションが無い時間は来ないので、自走中かどうかで止めず、取り込む変更ごとに見分ける。

## 手順

1. `git fetch origin` の後に `git rev-parse origin/main` で取り込む commit の sha を控える。後のコマンドには、その sha の値をそのまま書く（shell の変数は Bash の呼び出しをまたいで残らない。`origin/main` と書くと、途中でほかのセッションが fetch したときに読んでいない commit まで入る）
2. `git diff --stat HEAD <sha>` で取り込むファイルを全部挙げ、`git diff HEAD <sha> -- plugins/spec-autopilot` を読む
3. 自走中のセッションを挙げる（下の「自走中の見分け方」）。無ければ 5 に進む
4. 差分が `tests/` と README だけか、読んで走っている run の続きを変えない（hook・CLI・agent の判定、state.json などの記録の読み方、run の途中で読む agents・commands・references・templates の文を変えない）と言えるなら 5 に進む。言えなければ、そのセッションが自走中でなくなるまで待ち、3 からやり直す
5. 取り込む直前に 3 をもう一度回し、増えたセッションがあれば 4 の判定をし直す。通ったら `git merge --ff-only <sha>` で取り込む

## 自走中の見分け方

- `SPEC_AUTOPILOT_HOME`（無ければ `~/.claude/spec-autopilot`）の `sessions/` の、名前のドットが 1 つの `<id>.json`（中身は spec のディレクトリの list）を全部読む。`.host.json`・`.prompt.json` などは spec を指さない
- それが指す spec の phase が queued・building・wait なら自走中とする。記録か state.json が読めない spec と、phase が discovery・blocked・done のどれでもない spec も、自走中として扱う
- 承認の前に S の試作を走らせている壁打ちのセッションは `sessions/` に出ない。人がそのセッションにいるかを別に確かめる
