# spec-autopilot の開発ルール

- 1 PR 1 課題にする。追加が +1,000 行を超えそうなら、先に分割を相談する
- 実装は TDD で進める（テストを先に書き、失敗を確かめてから実装する）
- テストは、repo の root で `python3 -m venv .venv` を回し、`source .venv/bin/activate` で有効にし（POSIX のシェルの書き方。fish や Windows では読み替える）、`.github/workflows/test.yml` の `pip install` の行を回して道具を入れてから、`python3 -m pytest plugins/spec-autopilot/tests/ -q -n auto` で回す。CI は venv を作らず、同じ `pip install` の行とテストのコマンドを回す。venv の外の `pip install` は、PEP 668 で守られた python3 では拒まれる（版は workflow の 1 か所にだけ書く）。このコマンドは全量で、締め（PR を作る前）に回し、落ちたら直して回し直す（`/autopilot` では手元で回さず、CI が回す。commands/autopilot.md の C の 5）。実装の途中は全量を回さず、spec の `- 回帰テスト:` のコマンド（spec の無い直しでは、変えるファイルを読むテスト）と、足したテストと、レビューや CI が名指ししたテストを回す
- 文書（command・reference・agent 定義・README など）に語や文があるかだけを assert するテストは書かない。コードが読む値と文書を突き合わせるテストは書いてよい
- 実装中に見つけた別の問題は、この PR が変えたファイルの中なら直す（要るリファクタリングは、挙動を変えずに別の commit にする）。変えていないファイルの問題は、再現手順を添えて Issue にする
- 版数は `plugins/spec-autopilot/.claude-plugin/plugin.json` の `version` で上げる。`.claude-plugin/marketplace.json` の `description` は plugin.json と同じにする（テストが突き合わせる）。spec の要件・前提・影響範囲には、版数と版数のテストの名前を書かない（ほかの PR が先に版を上げると、影響範囲に書いたテストの名前は依る spec の先端への着手で lint に止められ、要件・前提の版数は spec の直しと承認し直しが要る）。版数は、機能の PR のマージの後に、下の 1 段目で上げる
- この repo は公開している。社外に出せない情報（勤め先の repo 名・社内の計測値・個人のパスやメールアドレス・トークン）を、コード・文書・commit・PR に書かない

## この plugin 自身を直すときの進め方

- 直しは、変える中身で次の 3 つに振り分ける。迷ったら下の段（重い方）にする
  1. 版数だけを上げる（plugin.json の `version` と、`tests/test_spec_autopilot_wiring.py` の版数のテストだけを変える）: spec もレビューも回さず、テストを全部回して PR にする（テストが版数の形と前の版を超えたこと、marketplace.json との name・description の一致を確かめる。版数の 1 行に /autopilot を回すと、spec を作ってから終わるまで 21 分〔承認からは 10 分〕かかった）
  2. やる内容が依頼文か Issue で決まっていて、リスクが少ない直し。当たるのは次の場所だけで、ファイルを足す・消す・改名するものは含めない: (a) 全部 `.md` で、root の README.md・CLAUDE.md・`docs/`（スクリプトとそれが読むファイルを除く）・`plugins/spec-autopilot/README.md`・`plugins/spec-autopilot/commands/`・`plugins/spec-autopilot/references/` に入る文書、(b) `agents/` の本文の文言（frontmatter と出力の節を除く）、(c) `scripts/`・`hooks/` の 1 か所の不具合で、hook・lint・check・approve の判定（通す・止める）を変えないもの。(a)・(b) の直しが、照合役・評価役・hook・lint・check・approve の判定、main に人へ聞かせる・自走で回させない操作を決める文、またはほかのファイルやスクリプトが名指しする・読む文字列（見出し・書式の例・観点の名前と番号）を変えるなら、その会話で人が変える中身を言ったか、人が Issue を番号で名指しして直すよう頼んだとき（Issue を書いたのが agent でもよい）だけ 2 段目にし、写しと名指しする側を同じ PR で直し、PR 本文の先頭に、その人の発言（社外に出せない語は上の規則どおり伏せる）、変える文の前と後、写しと名指しする側を探した語・範囲・件数を書く。人の発言が無いときと、写しか名指しする側のどれかが (a)・(b) に入らない場所（agents の frontmatter と出力の節、`scripts/`・`hooks/`・`templates/`・`tests/`、repo の外の記録など）にあるときは 3 段目にする。`/autopilot` を回さず、コードを変えるなら TDD で直し、テストを全部回してから debug-and-review の pre-pr-review で PR にする
  3. それ以外（hook・判定を変える〔2 段目の条件に当たるものを除く〕、新しい仕組み、複数の部品にまたがる〔(a)・(b) の中の写しと名指しする側を同じ PR で直すものを除く〕、やる内容を人と決める必要がある）: `/autopilot` で、人と spec を合意して回す
- `/autopilot` が壊れていて回せないときも pre-pr-review で回し、回せなかった理由（コマンドと件数。手元のパスは伏せる）を PR 本文に書く。pre-pr-review を使えない環境では、差分と規則だけを渡した独立レビューを 1 回回す（マージの扱いは pre-pr-review と同じ）
- 自走の範囲は spec ごとに `## 自走の範囲` の `- 範囲:` で決める。草案は「マージまで」で出し、承認のときに先頭に示す。main へのマージは、marketplace から新しく入れる人に届き、版数を上げたものは入れた人にも届く（デプロイの workflow は無いので「マージ・デプロイ・QA まで」は使わない）。`/autopilot` の check を通して自走の範囲でマージする PR のほかは、マージは人の指示を待つ
- 手元の plugin は GitHub の marketplace から入れた版ごとの写しを読む。更新は自走の範囲に入れず、人が頼んだときに `claude plugin update spec-autopilot@spec-autopilot` で行い、更新の後に、走っているセッションで `/reload-plugins` を回し、見回り役の plist を新しい版の `watch.py plist` で出し直す（plist は作った時点の watch.py の実パスを書くため）。開発中の版は `claude --plugin-dir <worktree>/plugins/spec-autopilot` で試す
- `/autopilot` で回すときは pre-pr-review を重ねない。hook か判定を変える spec では、`## 制約` に想定する脅威を 1 行書く（lint は検査せず、評価役にも専用の観点は無い。範囲と直す要否を決めるときの目安）
- 新しい仕組みや改善を agent が自分で思いついたときは、実際のタスクで観測した失敗（state.json の blocked、見回りの報告、transcript の件数）があるものだけを出す。測っていなければ、先に測る手順を出す。人が頼んだ機能は、この条件で削らない。変えたファイルの中で見つけた不具合は、上の「実装中に見つけた別の問題」に従う
- この進め方は、`/autopilot` で回した最初の 5 本で、`SPEC_AUTOPILOT_HOME`（無ければ `~/.claude/spec-autopilot`）の `runs.jsonl` を読んで決める（承認からの分数、blocked の回数と理由、マージ後の手戻りの PR の数）。予算を超えるのが 5 本中 3 本以上なら、ここに規則を足さず、`/autopilot` の欠陥として直す
