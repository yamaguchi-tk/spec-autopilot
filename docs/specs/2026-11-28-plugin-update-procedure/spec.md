# 手元の plugin の更新の規則を、marketplace から入れた形に合わせる

- ADR: docs/adr/2026-11-28-plugin-update-procedure.md

## 目的
人の問い「ローカルをプライベートリポジトリからのInstallにして、こっちは開発のみにするのがいいのでは？　もしくは最適な形がある？」に対して、手元の plugin を GitHub の marketplace から版ごとの写しで入れる形（案 A）に移すと人が決め（「A に移す」）、移し替えは済んだ。ところが CLAUDE.md は、まだ symlink の向け先の checkout を pull する規則と、その手順の docs/pull-checkout.md を正本として持っている。これを今の形の規則に置き換え、対象の無くなった手順を消す。できあがると、agent が読む規則が実際の入れ方と合い、checkout の pull や reset を求める古い手順に従ってしまうことが無くなる。

## 要件
- R1: CLAUDE.md の「この plugin 自身を直すときの進め方」の節を読んだとき、手元の plugin の扱いを定めた行は、手元の plugin の更新を自走の範囲に入れず、人が頼んだときに `claude plugin update spec-autopilot@spec-autopilot` で行うこと、更新の後に走っているセッションで `/reload-plugins` を回し、見回り役の plist を新しい版の `watch.py plist` で出し直すこと、開発中の版は `claude --plugin-dir <worktree>/plugins/spec-autopilot` で試すことの 3 つを書き、symlink の向け先の checkout の pull と `docs/pull-checkout.md` を書かない。
- R2: tip で `git grep -n pull-checkout -- ':(exclude)docs/specs' ':(exclude)docs/adr'` を回したとき、出力は 0 行で、`docs/pull-checkout.md` は無い。

## 非目標
- 過去の spec・ADR の中の `pull-checkout` の言及は、当時の記録なので直さない
- 版の更新の後に、見回り役の plist が古い版の watch.py を指したままになるのを preflight で知らせる直しは、別の spec にする
- 手元の ~/.claude と launchd の設定の移し替え（済んでいる）

## 影響範囲
- 変える: CLAUDE.md:19（全体）
- 変える: docs/pull-checkout.md:1-25（全体）
- 呼び出し元: なし
- 同じ入力: なし
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_ci_workflow.py -q

## 変えない挙動
- CLAUDE.md のテストのコマンドの行（`-n auto` と workflow の pip install の行を指す）: plugins/spec-autopilot/tests/test_ci_workflow.py::test_claude_md_test_command_uses_n_auto_and_points_to_the_workflow_install_line

## 前提
- 目的に届く: 規則の文を置き換えるだけで、守られているかは機械で確かめない（agent が CLAUDE.md を読んで従う）
- 運用: 人が版数を上げた PR のマージの後に `claude plugin update spec-autopilot@spec-autopilot` を回し、走っているセッションで `/reload-plugins`、見回り役の plist を出し直す
- 普通のやり方: plugin の開発中の版は `--plugin-dir` で試し、入れた版は marketplace から更新する（出典は公式の文書 code.claude.com の plugins/install.md と plugins/loading.md）。文書の手順のうち、この spec が規則に書くのは更新の後に毎回回す update・/reload-plugins・--plugin-dir で、1 回だけの marketplace add・install・uninstall は済んでいるので書かない
- 過去: docs/pull-checkout.md は、symlink の向け先の checkout を pull すると全セッションの hook がその場で変わることを抑えるために作った（git log -- docs/pull-checkout.md の 8b69b0e・8396e73・5ee66e8）。今回の pull では手元の main が origin と分かれていて、手順が禁じる reset --hard で合わせることになった
- 前提: 手元の plugin は GitHub の marketplace から入れてあり、版ごとの写しを読む
  - コマンド: `grep -n -A3 'spec-autopilot@' ~/.claude/plugins/installed_plugins.json` → installPath が `cache/spec-autopilot/spec-autopilot/0.1.21` の実ディレクトリ
- 前提: `pull-checkout` を名指しするのは、docs/specs・docs/adr の外では CLAUDE.md と docs/pull-checkout.md だけ
  - path: CLAUDE.md:19、docs/pull-checkout.md:1
  - コマンド: `grep -rln 'pull-checkout' . --exclude-dir=.git --exclude-dir=specs --exclude-dir=adr` → CLAUDE.md、docs/pull-checkout.md
- 前提: watch.py の plist は、作った時点の watch.py の実パスを書く
  - path: plugins/spec-autopilot/scripts/watch.py:29（HERE = Path(__file__).resolve()）、plugins/spec-autopilot/scripts/watch.py:313（ProgramArguments）

## 作り方
CLAUDE.md:19 の 1 行を、R1 の 3 つを書いた行に置き換え、docs/pull-checkout.md を消す。CLAUDE.md:18 の「版数を上げたものは入れた人にも届く」はそのまま残す。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | tip の CLAUDE.md の該当の行を読み、`claude plugin update spec-autopilot@spec-autopilot`・`/reload-plugins`・`watch.py plist`・`--plugin-dir` があり、`symlink`・`pull-checkout` が無いかを `grep -n` で確かめる | 4 つの語が該当の行にあり、2 つの語が CLAUDE.md に 0 件 |
| R2 | 手元で実物 | tip で `git grep -n pull-checkout -- ':(exclude)docs/specs' ':(exclude)docs/adr'` と `test -e docs/pull-checkout.md` を回す | grep の出力が 0 行で、test が 1 を返す |

## 制約
- 予算: 30 分
- 大きさ: S
- playbook: なし（文書の規則の置き換えで、機能・不具合・IaC・外部サービスのどれにも当たらない）

## モデル

## 自走の範囲
- 範囲: マージまで
- QA の環境:
- QA の書き込み先:
- デプロイの起動: なし（マージした commit で QA）
- デプロイの確かめ:
- ロールバック: revert の PR をマージし、デプロイの完了を確かめる
- 通知: デスクトップ
- AWS の profile: なし

## 止まる条件
- 合意した要件のどれかを満たす方法が無いと分かったとき（その要件だけを park に積み、ほかを進める。どの要件も進められないときだけ block）
- 承認した自走の範囲の外の操作が要るとき（実行せずに park に積む）
