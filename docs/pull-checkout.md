# 手元の checkout の pull

plugin を使う手元の checkout（symlink の向け先）を pull するときの手順。pull は自走の範囲に入れず、人が頼んだときに行う。

取り込むと、全セッションの hook・CLI・agent の定義・commands・references・templates がその場で変わる。自走は、記録（`sessions/`）に出ない間にも進む（承認の前の S の試作、目的の spec を子に分ける間、block の後の承認し直し、軽量フローの承認の前）。そこで、自走中のセッションを数えて決めず、いつも走っている run があるものとして、取り込む変更ごとに見分ける。

## 手順

1. `git fetch origin` の後に `git rev-parse origin/main` で取り込む commit の sha を控える。後のコマンドには、その sha の値をそのまま書く（shell の変数は Bash の呼び出しをまたいで残らない。`origin/main` と書くと、途中でほかのセッションが fetch したときに読んでいない commit まで入る）
2. `git diff --name-status --no-renames HEAD <sha>` で取り込むファイルを完全なパスで全部挙げ（`--stat` はパスを縮めるので使わない）、`tests/` と README の外は `git diff HEAD <sha> -- <path>` で中身を読む。出力が切れたら、ファイルに書き出して Read で末尾の行まで読む。一覧に出たのに出力が空だったファイルと、読み切れなかったファイルは、読めていないものとして 3 で言えないとする
3. 差分が `tests/` と README だけか、読んで走っている run の続きを変えない（hook・CLI・agent の判定、state.json などの記録の読み方、run の途中で読む agents・commands・references・templates の文を変えない）と言えるなら、`git merge --ff-only <sha>` で取り込む
4. 言えなければ取り込まず、人に返す。示すのは、控えた sha、変える点、待つ相手の候補（`SPEC_AUTOPILOT_HOME`〔無ければ `~/.claude/spec-autopilot`〕の `sessions/` の、名前のドットが 1 つの `<id>.json` が指す spec のうち phase が discovery・blocked・done でないもの、読めないもの）。候補は記録のあるものだけで、記録に出ない自走（上の段落）は数えられないので、人がほかのセッションで自走を進めていないかを確かめてから決めるよう添える
5. 人が取り込むと言ったら、4 で示した sha を `git merge --ff-only <sha>` で取り込む。その後に 1 からやり直し、控えた sha が HEAD と同じなら終える

`git merge --ff-only` が通らないとき（HEAD が動いた・作業ツリーに変更がある）は、reset・rebase・stash など別の方法で取り込まず、出力を添えて人に返す。
