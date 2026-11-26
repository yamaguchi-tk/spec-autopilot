# 手元の checkout の pull

plugin を使う手元の checkout（symlink の向け先）を pull するときの手順。pull は自走の範囲に入れず、人が頼んだときに行う。

取り込むと、全セッションの hook・CLI・agent の定義・commands・references・templates（どれも `plugins/spec-autopilot` の下）と、plugin の場所を決める `.claude-plugin/marketplace.json` がその場で変わる。並列で回していると自走中のセッションが無い時間は来ないので、自走中かどうかは数えない。取り込んでよいかは固定のコマンドの終了コードで決め、agent が差分を読んで決めない。

## 手順

`<checkout>` は、plugin の symlink の向け先で `git rev-parse --show-toplevel` を回して得た作業ツリーの root（開発用の worktree ではない）。値を引用符で囲み、そのまま書く。

1. `git -C "<checkout>" fetch origin` を回し、`git -C "<checkout>" rev-parse origin/main` で取り込む commit の sha を控える。後のコマンドには、その sha の値をそのまま書く（shell の変数は Bash の呼び出しをまたいで残らず、`origin/main` と書くと、途中でほかのセッションが fetch したときに確かめていない commit まで入る）。fetch が失敗したら人に返す
2. 次のコマンドを回す（コマンドは変えない。入れる値は `<checkout>` と sha だけ）

   ```
   git -C "<checkout>" diff --quiet --no-renames HEAD <sha> -- plugins/spec-autopilot .claude-plugin ':(exclude)plugins/spec-autopilot/tests' ':(exclude)plugins/spec-autopilot/README.md'
   ```

3. 終了コードが 0（取り込む差分が、plugin と `.claude-plugin` の外か、plugin の tests と README だけ）なら、`git -C "<checkout>" merge --ff-only <sha>` で取り込む
4. 終了コードが 1（plugin の tests と README の外か、`.claude-plugin` の中の差分がある）なら取り込まない。`git -C "<checkout>" diff --no-renames HEAD <sha>` を checkout の外の一時ファイルに書き出し、`git -C "<checkout>" diff --name-status --no-renames HEAD <sha>` の一覧と、控えた sha を、一覧のどれが走っているセッションの何（上の段落のどれ）を変えるかと一緒に人に示す（要約を添えるなら参考と書く）。人が取り込むと言ったら、その sha を `git -C "<checkout>" merge --ff-only <sha>` で取り込む。0 と 1 のほか（git のエラー）は、出力を添えて人に返す

`git merge --ff-only` が通らないときは、reset・rebase・stash など別の方法で取り込まず、出力を添えて人に返す。

## 限界

- plugin と `.claude-plugin` の外（root の CLAUDE.md・`docs/` など）は確かめずに取り込む。開発用の worktree が checkout の下にあり、Claude Code が親の階層の CLAUDE.md も読むなら、root の CLAUDE.md の変更は走っている run に効く（読むかは確かめていない）
