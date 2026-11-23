# spec-autopilot を既存の repo で測る

新規の小さい題（テトリスなど）では測ったが、既存の大きい repo ではまだ一度も測っていない。この台本は、既存の repo の過去の変更を課題にして、spec-autopilot（腕 H）と素の Claude Code（腕 P0）を同じ模擬ユーザーで比べる。

## 安全のための作り

`drive.sh` は、元の repo を触らずに次のように動かす。

- 元の repo を `git clone --no-hardlinks` で出力ディレクトリに複製し、課題の `base:` の commit に戻す。remote をすべて外し、`bench` 以外の branch と tag を消し、reflog とたどれない object も消す（答えになる commit と元の repo のパスを残さない）
- git が追っている認証の設定（`.envrc`・`.env`・`.env.*`・`.aws-config`。`.example`・`.sample`・`.template` は残す）は、複製で消して commit する。差分も回帰の基準も、この commit（`log.txt` の `start`）から数える
- claude と模擬ユーザーは `env -i` の許可リストの環境で起動する。渡すのは次だけで、ほかの環境変数（AWS・GitHub の token、`SSH_AUTH_SOCK` など）は名前を問わず渡らない
  - HOME は空のディレクトリ（`~/.netrc`・`~/.ssh`・`~/.aws`・gh の設定は見えない）
  - PATH・USER・LANG・TERM・SHELL・TMPDIR、claude の認証の `CLAUDE_CODE_OAUTH_TOKEN`、あれば uv のキャッシュの場所
  - AWS の設定と認証のファイルは `/dev/null`、EC2 のメタデータは切る
  - git は global と system の設定を読まない（credential helper も効かない）。転送は https だけで、元の repo のパスへの転送と ssh は通らない
- 起動の前に、同じ環境で次を試し、1 つでも通れば止める: credential helper の設定、元の repo への `git ls-remote`、`gh auth token`、`aws sts get-caller-identity`
- `aws` の CLI の呼び出しは `--disallowedTools` でも拒む
- 出力ディレクトリが元の repo の中なら、何も作らずに止まる
- 始める前と終わった後に、元の repo の ref・stash・local の config・worktree・`git status` を、出力ディレクトリの外の一時ディレクトリに写して比べる。結果は `log.txt` に書き、違えば写しを残して場所を知らせる（写しには元の repo のパスと ref が入るので、agent の届く場所に置かない）

HOME を空にするので、claude はキーチェーンのログインを使えない。先に `claude setup-token` で token を作り、`CLAUDE_CODE_OAUTH_TOKEN` に入れて回す（無ければ台本は止まる）。

残る穴: `claude -p` は `bypassPermissions` で動くので、agent が自分で元の repo の絶対パスに `cd` したり書いたりすること、`security` でキーチェーンを読むことは止めていない。どれも手順に無い形である。元の repo への変更のうち、ref・stash・config・worktree・`git status` に出るものは終わった後の比較で見えるが、ignore されたファイルや `.git/hooks` の書き換えは見えない。ほかにも次が残る
  - 一覧に無い名前の、git が追っている認証のファイル（`.npmrc`・`*.pem` など）は複製に残る。消したファイルも、親の commit を読めば見える
  - `CLAUDE_CODE_OAUTH_TOKEN` は、agent の Bash からも読める

## 課題ファイル

1 課題 1 ファイル。非公開の repo の課題はその repo の情報を含むので、この repo には置かず、手元に置く。

```
base: <課題を始める commit（過去の PR の base）>
依頼: <その PR を頼んだときの 1 文。PR の題や Issue から書く>
隠れた要望:
1. <PR の差分やレビューで分かる、依頼に書かれていなかった条件>
2. ...
```

課題の選び方:

- 過去にマージした PR から 5〜10 本を選ぶ（公開の評価の記事は、実際の変更から 20〜50 件で始めることを勧めている。最初の 5 本で読み、続けるか決める）
- 大きさを散らす（S: 1 か所の修正、M: 数ファイル、L: 400 行を超える）
- 外部サービス（AWS・Slack・LLM の API）を呼ぶコードを触る課題を、少なくとも 1 本入れる

## 回し方

```bash
CLAUDE_CODE_OAUTH_TOKEN=<token> bash docs/experiments/spec-autopilot-existing-repo/drive.sh <元の repo> <課題ファイル> H 1 <出力ディレクトリ>
```

腕は `H`（spec-autopilot）か `P0`（素の Claude Code）。回は 1 本ずつ順に回す（並べると、各回が repo の全テストを同時に回して CPU を取り合い、時間を比べられない）。`claude -p` はターンが終わると裏の処理の結果を受け取れないので、台本は裏の処理を切って起動する（切らないと、agent が「裏でテストを回して、終わったら知らせる」と言ったまま進まない）。どちらの腕も、HOME が空なので利用者の CLAUDE.md は読まず、既存の repo の CLAUDE.md は同じように読む。同じ課題を各腕 3 回回す（1 回 75% で成功しても、3 回とも成功するのは約 42% になるので、ぶれを見る）。

## 読むもの

| 指標 | 読み方 |
|---|---|
| 承認から完了まで | 腕 H は spec の `state.json`（出力ディレクトリのどこにあっても拾う）。腕 P0 は `log.txt` の turn の時刻 |
| 回帰 | 複製の結果で repo の全テストを回し、`start` の commit で回したときと比べて新しく落ちたテストの数（台本が消した `.envrc` などを読むテストは、`start` でも落ちる） |
| 隠れた要望の充足 | `dialog.txt` と差分を読み、課題ファイルの要望ごとに満たしたかを付ける |
| 変更の大きさ | `diffstat.txt`。worktree ごとの、commit していない変更を含めた差分と、docs/specs・docs/adr を除いた行数。元の PR の差分の行数と比べる |
| 費用 | `cost.log` の turn ごとの `total_cost_usd`（Sonnet の指定は Opus の単価で数えられるので、公称の単価で数え直す）。claude が失敗した turn は `True` になり、台本はそこで止まる |

## マージがそのまま本番へのデプロイになる repo で回すときの注意

- 外部サービスを呼ぶ統合テストは回さず、unit テストだけを回す
- 複製の外で push しない
