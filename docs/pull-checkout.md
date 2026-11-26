# 手元の checkout の pull

plugin を使う手元の checkout（symlink の向け先）を pull するときの手順。pull は自走の範囲に入れず、人が頼んだときに行う。

取り込むと、全セッションの hook・CLI・agent の定義・commands・references・templates がその場で変わる。自走は、記録（`sessions/`）に出ない間にも進む（承認の前の S の試作、目的の spec を子に分ける間、block の後の承認し直し、軽量フローの承認の前）。そこで、自走中のセッションを数えて決めず、いつも走っている run があるものとして、取り込む変更ごとに見分ける。

## 手順

1. `git fetch origin` の後に `git rev-parse origin/main` で取り込む commit の sha を控える。後のコマンドには、その sha の値をそのまま書く（shell の変数は Bash の呼び出しをまたいで残らない。`origin/main` と書くと、途中でほかのセッションが fetch したときに読んでいない commit まで入る）
2. `git diff --stat HEAD <sha>` で取り込むファイルを全部挙げ、`tests/` と README の外は `git diff HEAD <sha> -- <path>` で中身を最後まで読む（出力が切れたら、ファイルごとに分けて読む）
3. 差分が `tests/` と README だけか、読んで走っている run の続きを変えない（hook・CLI・agent の判定、state.json などの記録の読み方、run の途中で読む agents・commands・references・templates の文を変えない）と言えるなら、`git merge --ff-only <sha>` で取り込む
4. 言えなければ取り込まず、人に返す。示すのは、控えた sha、変える点、待つ相手の候補（`SPEC_AUTOPILOT_HOME`〔無ければ `~/.claude/spec-autopilot`〕の `sessions/` の、名前のドットが 1 つの `<id>.json` が指す spec のうち phase が discovery・blocked・done でないもの、読めないもの）。候補は記録のあるものだけで、記録に出ない自走（上の段落）は数えられないので、人がほかのセッションで自走を進めていないかを確かめてから決めるよう添える
5. 人が取り込むと言ったら、4 で示した sha を `git merge --ff-only <sha>` で取り込む。その後に origin が進んでいたら、新しい分は 1 からやり直す
