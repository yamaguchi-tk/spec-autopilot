# spec-autopilot の開発ルール

- 1 PR 1 課題にする。追加が +1,000 行を超えそうなら、先に分割を相談する
- 実装は TDD で進める（テストを先に書き、失敗を確かめてから実装する）
- テストは `python3 -m pytest plugins/spec-autopilot/tests/ -q` で回す。CI（`.github/workflows/test.yml`）も同じものを回す
- 文書（command・reference・agent 定義・README など）に語や文があるかだけを assert するテストは書かない。コードが読む値と文書を突き合わせるテストは書いてよい
- 実装中に見つけた別の問題は、この PR が変えたファイルの中なら直す（要るリファクタリングは、挙動を変えずに別の commit にする）。変えていないファイルの問題は、再現手順を添えて Issue にする
- 版数は `plugins/spec-autopilot/.claude-plugin/plugin.json` の `version` で上げる。`.claude-plugin/marketplace.json` の `description` は plugin.json と同じにする（テストが突き合わせる）
- この repo は公開している。社外に出せない情報（勤め先の repo 名・社内の計測値・個人のパスやメールアドレス・トークン）を、コード・文書・commit・PR に書かない

## この plugin 自身を直すときの進め方

- `plugins/spec-autopilot/` の `scripts/`・`hooks/`・`tests/`・`.claude-plugin/plugin.json` を変える直しは、`/autopilot` で回す。文書だけ（`commands/`・`references/`・`agents/`・`templates/`・README・この CLAUDE.md など）の直しと、`/autopilot` が壊れていて回せないときは、debug-and-review の pre-pr-review で回す。回せなかったときは、その理由（コマンドと出力）を PR 本文に書く
- 自走の範囲は spec ごとに `## 自走の範囲` の `- 範囲:` で決める。この repo にはマージで動くデプロイが無いので、草案は「マージまで」で出し、承認のときに先頭に示す。pre-pr-review で回した PR のマージは、人の指示を待つ
- plugin を使う手元の checkout（symlink の向け先）の pull は、自走の範囲に入れない。pull した時点で全セッションの hook が変わるので、自走中のセッションが無いときに人が行う。開発は別の worktree で行い、その checkout のブランチを切り替えない
- `/autopilot` で回すときは pre-pr-review を重ねない。hook か判定を変える spec では、`## 制約` に想定する脅威を 1 行書く
- agent が自分で思いついた直しは、実際のタスクで観測した失敗（state.json の blocked、見回りの報告、transcript の場所と件数）があるものだけにする。測っていなければ、先に測る手順を出す。人が頼んだ機能は、この条件で削らない
- この進め方は、`/autopilot` で回した最初の 5 本で読む（承認からの分数、blocked の回数と理由、マージ後の手戻りの PR の数）。予算を超えるのが続いたら、ここに規則を足さず、`/autopilot` の欠陥として直す
