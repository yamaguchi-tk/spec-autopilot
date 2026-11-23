# spec-autopilot の開発ルール

- 1 PR 1 課題にする。追加が +1,000 行を超えそうなら、先に分割を相談する
- 実装は TDD で進める（テストを先に書き、失敗を確かめてから実装する）
- テストは `python3 -m pytest plugins/spec-autopilot/tests/ -q` で回す。CI（`.github/workflows/test.yml`）も同じものを回す
- 文書（command・reference・agent 定義・README など）に語や文があるかだけを assert するテストは書かない。コードが読む値と文書を突き合わせるテストは書いてよい
- 実装中に見つけた別の問題は、この PR が変えたファイルの中なら直す（要るリファクタリングは、挙動を変えずに別の commit にする）。変えていないファイルの問題は、再現手順を添えて Issue にする
- 版数は `plugins/spec-autopilot/.claude-plugin/plugin.json` の `version` で上げる。`.claude-plugin/marketplace.json` の `description` は plugin.json と同じにする（テストが突き合わせる）
- この repo は公開している。社外に出せない情報（勤め先の repo 名・社内の計測値・個人のパスやメールアドレス・トークン）を、コード・文書・commit・PR に書かない
