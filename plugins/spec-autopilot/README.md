# spec-autopilot

要件を人と壁打ちで詰め、要件・作り方・QA の方向性・制約・予算を 1 つの spec で 1 回合意したら、TDD 実装→レビュー→QA→PR→マージ→デプロイ→実環境の QA まで人に聞かずに進めるハーネスです（どこまで進めるかは spec の「## 自走の範囲」。既定は「マージ・デプロイ・QA まで」）。1 つの要件だけが進められないときは、その要件を積んで（park）残りを進め、朝の報告に出します。人に戻るのは、どの要件も進められないときだけです。

## 使い方

```
/autopilot ブラウザで遊べる落ち物パズルを作りたい
```

1. **壁打ち**: なぜ欲しいのかを聞き、問いを 1 回に 1 つにして要件を詰めます。小さい依頼（S）と、新しく作る repo の M では、spec の草案と一緒に動く試作を出します
2. **合意**: `docs/specs/<日付>-<slug>/spec.md` と ADR（`docs/adr/`）を書き、1 回だけ承認を求めます
3. **自走**: Sonnet 5.5 の実装者が TDD で実装し、経緯を知らない Opus の評価役が要件ごとに自分で動かして確かめます（QA とレビューを兼ね、high none まで回し直す）。評価の結果を `qa.md` に写し、PR を作ります。範囲がマージ以上なら、CI とデプロイを `scripts/overnight.py await` で待ち（待つ間は Stop hook が止めない）、マージ・実環境の QA まで進めます（`references/after-pr.md`）

## 軽量フロー（合意を省く）

受入条件が Issue に書いてあるか、依頼文だけで要件・範囲・完了が決まる小さい修正は、`scripts/light.py approve` で人との spec 合意を省いて自走できる（spec は自動で作って repo に残す）。自走の範囲は合意ありと同じく spec の `- 範囲:` で決まり、マージ・QA まで進む。ただし人が spec を見ないので、`- デプロイの起動:` と `- ロールバック:` をコマンドにした spec は approve が断る（マージで自動に動く workflow と revert の PR だけ。`## 自走の範囲` の見出しは 1 つだけ。spec のほかの所や節の中の閉じたコメントに書いたコマンドは機械では拾わず、agent に打たないよう指示するだけ）。デプロイの workflow が無い repo は、`- デプロイの起動: なし（マージした commit で QA）` にすると、マージの記録を起点にマージの後の QA へ進む（合意ありでも同じ）。保護された path（既定の一覧は `scripts/light.py` の `DEFAULT_PROTECTED`。IaC の主な拡張子とディレクトリ、名前に guardrails を含むもの、エージェントの規則と設定、`.github`、設定そのものの `.spec-autopilot`。起点の commit の `.spec-autopilot/protected-paths` で足せる。普通のファイルでないか読めないと止まる。Git LFS などの filter を掛けた設定は効かない）に触れたら、変更ファイルの path で機械的に止まり、人に戻る。判定するのは init の時点から PR に入りうる変更（HEAD・index・作業ツリーの差と追っていないファイル）だけで、init より前の commit・git が無視するファイル・途中の commit で触れて戻したもの・spec の置き場の中の `/` を含む pattern は見ないので、手元の設定の書き換えは防がない。手順は `commands/autopilot.md` の「L. 軽量フロー」。

## かっちりさの作り方

LLM の多段レビューや人への中間確認ではなく、成果物の型と機械の検査で固めます。

| 仕組み | 中身 |
|---|---|
| 成果物の型 | spec.md（要件は `- R1: ...`、QA の方向性の表、`- 予算: <分> 分`）・tasks.md（`- [x] T1: ... [R1]`）・qa.md（`\| R1 \| pass \| <証拠> \|`。要件ごとに 1 行）・state.json |
| `scripts/autopilot.py lint` | 節の欠け・要件の確かめ方の欠け・予算の欠け・「## 前提」の行の欠けと形の誤り（確かめ方の無い前提、init の時点の commit に無い path を含む）を誤りに、曖昧な語を警告にします |
| `scripts/autopilot.py approve` | lint が通ったときだけ承認を記録し、spec のハッシュと予算を残します。done の後に人が直しを頼んだときも、これで自走に戻ります |
| `scripts/autopilot.py check` | 要件→タスク→QA の証拠の対応、証拠のテスト名の実在、承認後の spec の変更、最後のレビューが high none であること、作り方を変える段の要件が残っていないことを検査します |
| `scripts/autopilot.py fail`・`review`・`rework` | 行き詰まりの梯子（`references/dead-end.md`）を要件ごとに数えます。QA の fail・実装の満たせなかった報告・最後のレビューの high がある巡が、同じ要件で累計 3 巡になると（high も失敗も無い巡では戻さず、作り直しで 0 に戻ります）、新しい ADR で作り方を変えるまで check が落ちます。作り直しは要件ごとに 2 回まで |
| Stop hook | 自走中は check が通るか、`block` で満たせない要件を記録するまで turn を終えさせません。予算の 2 倍で放します。止めるのは自走を引き受けたセッション（approve・resume・adopt を実行したセッション）だけで、fork や同じ repo の別のセッションは止めません。background の agent を待つ間は、起こし直しの timer が生きていれば止めません。生きているかは、その timer の `sleep` がこの Claude Code のプロセスの下で今も動いているかを `ps` で確かめて決めます（`ps` が使えないときは、その turn に張った直後の timer だけを数えます）。done・block の後は、そのセッションの記録から spec を外します。1 回の判定は 20 秒までで、過ぎたら判定し終えていない spec を、判定の途中で落ちたときと同じく、最初の停止では止め、続けて止められた停止では放します。判定が答えを出さずに終わったとき（シグナル・終了コード 0 以外）も、`hooks/stop.sh` が同じように答えます（`sh` が要ります） |
| PreToolUse hook（Agent・Task） | 実装役（`autopilot-implementer`）を起動するとき、prompt の spec のディレクトリに、phase が building で、最後の dispatch を閉じた handoff が無く、その agent が起動する名前と同じものが無ければ deny し、`overnight.py dispatch` を打つよう伝えます。spec のディレクトリが無い・読めない・判定が答えを出さずに終わったときも deny します。実装役でない agent は見ません。plugin を入れ直した後に始めたセッションで効きます |
| SessionStart hook と `scripts/autopilot.py status` | 中断・compaction の後に、続きのある spec の状態（phase・予算・梯子・残り）を文脈に入れます。自走を引き受けていないセッション（fork・別のセッション・/clear の後）には、spec の場所と phase だけを出し、続ける指示を出しません |
| 自走の異常と `scripts/autopilot.py anomalies` | 承認の後に手順の約束から外れた動き（tool を呼ばない turn が続けて 3 回止められた・前景のはずの agent が裏で走った・人に聞いた・`sleep` で待った）を、Stop hook が transcript から型ごとに数え、増えた型を知らせます（止め方は変えません）。件数は state.json に残り、`done` が done の時点までの transcript で数え直して出します。`anomalies <transcript>...` は過去の transcript を同じ型で数えます |
| `scripts/autopilot.py adopt` | 同じ PC の別アカウントで同じ worktree を開いたときや /clear の後に、人が引き継ぐと言ったら実行して、そのセッションに自走を引き継ぎます |
| `scripts/watch.py`（見回り役） | Claude アプリの再起動などで止まった自走のセッションを、launchd から 15 分ごとに見て、同じ session id で起こし直します。起こせないとき（権限の mode が合わない、3 回起こしても進まない、セッションは開いたまま 30 分動いていない、host の記録が無い、claude を起動できない）は spec のディレクトリの `watch-report.md` とデスクトップ通知で知らせます。launchd の plist は `watch.py plist` が出し、入れるのは人です |

## 判断の相談役（同梱の agent）

判断の相談役の agent を 2 種類と、その推奨を検証する agent を 1 種類同梱しています。1 段目の相談役（`fable-advisor`）を回すのは、目的の spec の子の承認、block の後の承認し直し、人が相談役を名指ししたとき、IaC の初回の apply を含む spec の 4 つだけで、`advice-checker` で反証を探す 2 段で回します。人が `opus-advisor` を名指ししたときは、`fable-advisor` の代わりに 1 段目に使い、`advice-checker` は同じく回します。このほか、SessionStart の hook が全セッションに入れる相談役の規則が、ほかの迷いを次のように決めさせます。価値観で案が 1 つに絞れたときは、相談役も検証役も回さずに進みます。価値観で案が 2 つ以上残るとき（人に戻るときの選択肢・レビュー指摘の直し方を含む）は、相談役を回さず、main が選んだ案を、根拠に repo の事実（path:行・コード・引いた決定）があるときだけ `advice-checker` 1 本で確かめ、無ければ回さずに進みます。人に問うのは、答えを人しか持たない事実、1 操作ごとの許可、目的を変える決定の 3 つだけで、`advice-checker` が反証なしなら問わずに進みます（反証ありなら、自走中は当たる要件だけ park に積み、自走していないときは反証を添えて人に問います）。利用する repo の規則に別の相談の規定があれば、そちらに従います。

| agent | 使う場面 |
|---|---|
| `fable-advisor` | 承認の門（目的の spec の子の承認・承認し直し）、人の名指し、IaC の初回の apply を含む spec のときの相談の 1 段目（Fable・medium）。main が価値観で選んだ案が人の選びと同じかを確かめる役（main の代わりに選ぶ役ではない）として、main の案を見る前に推奨を出します |
| `advice-checker` | 相談の検証役（Opus・high）。1 段目の推奨か、main が価値観で選んだ案の根拠を repo の事実に当てて反証を探します。新しい案は出しません |
| `opus-advisor` | 同じ相談を Opus・high で行います。人が名指ししたときに、1 段目として使います（main が Opus で動くとき、Opus の相談役を重ねても見方はあまり増えません） |

- どれも read-only（Read・Grep・Glob だけ）で、model と effort を定義で固定しています。起動するときに `model` を渡しません
- 材料は要約せず、ファイルのパスや `file:line` で渡します
- 規則に書くときの例（repo 側で 2 段を回す場面を決める場合）: 「人に案を選んでもらう前に、`spec-autopilot:fable-advisor` に材料を場所で渡して 1 本相談する。返った推奨の `推奨:`・`理由:`・`引いた決定:` の欄と、依頼の原文と材料の場所だけを `spec-autopilot:advice-checker` に渡して反証を探させ、`反証あり` なら、最初の材料の場所・最初の推奨・成り立たない主張を渡して fable-advisor に 1 回だけ直させる。最初の推奨と反証の結果、直した推奨（検証していないと書く）、自分の案との食い違いを確認の本文に載せる」
- opus-advisor と fable-advisor は、工程管理つきの開発ハーネス [gate-driven-development](https://github.com/yamaguchi-tk/gate-driven-development)（GDD）の相談役から、その工程に結びついた起動条件を外して作ったものです。今はこの plugin の定義が正本で、GDD の側とは同期しません

## 役ごとのモデルの既定を変える（setup）

役ごとの model と effort の段は、既定が実装 `sonnet-high`・評価 `opus-high`・相談 `fable-medium`・検証 `opus-high`・照合 `sonnet-high` です。毎回同じ段にしたいときは、1 回だけ次を回します。

```
/spec-autopilot:setup
```

今の段と受ける段が役ごとに出るので、1 つ選びます（既定に戻す選択もあります）。選べる役は、実装・評価・相談（fable-advisor・opus-advisor の役）・検証（advice-checker の役）・照合（autopilot-spec-checker の役）の 5 つです。選んだ段は `SPEC_AUTOPILOT_HOME`（無ければ `~/.claude/spec-autopilot`）の `models.md` に `- 実装: <段>`・`- 評価: <段>`・`- 相談: <段>`・`- 検証: <段>`・`- 照合: <段>` の形で残り、plugin を更新しても消えません。command を使わず、次のように直接打つこともできます（`scripts/ladder.py`）。

- `ladder.py show`: 役ごとの受ける段・既定・手元の設定と、設定のファイルのパスを出す
- `ladder.py setup --impl <段>` / `--review <段>` / `--advisor <段>` / `--checker <段>` / `--spec-checker <段>`: その役の行を書く（受けない段は断り、ファイルを変えない）
- `ladder.py setup --reset`: 設定を消して既定に戻す。`--reset 実装`・`--reset 評価`・`--reset 相談`・`--reset 検証`・`--reset 照合` なら、その役の行だけを消す

実装・評価の段が spec に写るのは、`autopilot.py init` が spec.md を作る時点だけです。作った後の spec は変わらないので、直したいときはその spec の `## モデル` を直します。相談・検証・照合の段は spec には写らず、**次に始めたセッションから**効きます（SessionStart が、main に既定の agent の代わりに選んだ段の agent を使わせます。走っているセッションは変わりません）。照合役の読み替えは指示だけで効き、main が既定の照合役を起動しても機械では止めません。設定が読めないとき（段の名前が変わった、同じ役の行が 2 つある、など）は、init が誤りのある層（手元の設定 `models.md` かセッションの上書き）を spec に写さず（ほかの層の行は写ります）、直し方を NOTE で出します。

### このセッションだけ変える（setup --session）

既定を残したまま、今のセッションだけ役の段を変えられます。`/spec-autopilot:setup` は最初に「既定に書く」か「このセッションだけ」かを聞きます。直接打つなら次のとおりです。

- `ladder.py setup --session --impl <段>` / `--review <段>` / `--advisor <段>` / `--checker <段>` / `--spec-checker <段>`: 今のセッションの上書きを `SPEC_AUTOPILOT_HOME`（無ければ `~/.claude/spec-autopilot`）の `sessions/<セッション id>.models.md` に書く（渡していない役の行は残り、`models.md` は変わらない）。相談・検証・照合は、使う agent の読み替えの行も出す
- `ladder.py setup --session --reset`: このセッションの上書きを消す。`--session --reset 相談` のように役を渡せば、その役の行だけを消す
- 今のセッションが分からない（`CLAUDE_CODE_SESSION_ID` が無い、またはセッション id の形に合わない）ときは 0 以外で終わり、どのファイルも変えません

役ごとの段は、**セッションの上書き → 手元の既定（`models.md`）→ 同梱の既定**の順で決まります。`ladder.py show` は役ごとに、既定の設定の段に加えて「このセッション」の段（無ければ なし、上書きに誤りがあれば 使わない（誤りがある））を出します。誤りのある上書きの読めた行は、ほかの役で `setup --session` を打つと書き直したファイルに残って効き始めるので、先に `setup --session --reset` で消します。相談・検証・照合の上書きは、compaction や resume で始まり直したセッションでも、SessionStart の読み替えの指示に同じ段で入ります（上書きのファイルが読めないときは既定の段で作り、直し方を 1 行出します）。実装・評価の上書きは、そのセッションで後から `autopilot.py init` が作る spec の `## モデル` に、既定より優先して写ります（作った後の spec は変わりません）。/clear と fork は新しいセッション id になるので、上書きは切れて既定に戻ります。既定（`models.md`）を変えても、走っているセッションには効きません。

注意: 相談と検証を同じ model にすると、検証が相談と同じ見方になり、別の目で見る効きが減ります。相談を `fable-*` にするなら検証は `opus-high`（既定）のまま、検証を `fable-high` にするなら相談は `opus-high` にするなど、model を分けるのがお勧めです。

## 前提と制限

- Python 3 が要ります（標準ライブラリだけ）
- GDD（gate-driven-development）が active な repo では、GDD の hook がこの流れを止めます。`/autopilot` は始める前に検出して知らせます。GDD の plugin を外した後に `.claude/gdd-dev.local.md` の `active:` が false 以外のまま残っていても、止めずに NOTE で知らせます（plugin が有効かは、Claude Code の user・project・local の settings.json の `enabledPlugins` で決めます。読めない設定は有効とみなします。この判定は user・project・local の settings.json だけを読みます。それ以外の経路〔`--plugin-dir`・`--setting-sources`・`--settings` など〕で GDD が読み込まれていれば、GDD の hook が止めえます）
- 承認（approve）と再開（resume）は、transcript の人の発言の行（origin が human）で確かめます。headless の `claude -p` は origin を書かないので、そのままでは通りません。人の役を別の agent が演じる実験（`docs/experiments/spec-autopilot-existing-repo/drive.sh`）だけ、Claude Code を起動する環境に `SPEC_AUTOPILOT_TRUST_PROMPT_RECORD=1` を立て、hook の記録による確認を選びます。印は、origin のある transcript でも、origin の無い発言の行（subagent の報告の行にだけ origin がある場合の人の役の発言）で効きます。origin の付いた知らせ・subagent の報告だけでは通りません。hook が自分の環境で読んで記録に印を書くので、agent が Bash で立てても効きません。agent が記録ファイルや settings を意図して書けば通るのは、ほかの記録と同じです
- 設計の文書と ADR の判断は `docs/adr/2026-11-15-switch-harness-to-spec-autopilot.md` にあります
