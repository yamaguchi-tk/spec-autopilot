# 役ごとのモデルの既定を手元の設定で上書きする setup

- ADR: docs/adr/2026-11-27-role-model-setup.md

## 目的
人は「役ごとの既定を手元の設定で上書きできるようにしたい」「セットアップ機能が欲しい」（pstack の `/setup-pstack` のようなもの）と言った。今は実装役・評価役の始めの段を変えるには spec ごとに `## モデル` 節を書くしかなく、毎回同じ段にしたい利用者も spec のたびに書き足している。できあがると、利用者は 1 回 `/spec-autopilot:setup` で役ごとの段を選べば、以後に作る spec の `## モデル` に、その段が最初から入る。

## 要件
- R1: `ladder.py setup --impl <段>` か `--review <段>`（両方でもよい）を実行したとき、ladder.py は `SPEC_AUTOPILOT_HOME`（無ければ `~/.claude/spec-autopilot`）の `models.md` に、渡した役の行を `- 実装: <段>`・`- 評価: <段>` の形で書き（渡していない役の今の行は残す）、書いたファイルのパスと中身を出す。
- R2: setup に受ける段（R3 の show が挙げる段）以外の段（評価役の既定より下の段を含む）を渡したか、役も `--reset` も渡さなかったとき、ladder.py は 0 以外で終わり、役ごとに受ける段を挙げ、`models.md` を変えない。
- R3: `ladder.py show` を実行したとき、ladder.py は役ごとに、受ける段（安い順）・既定の段・手元の設定の段（無ければ「なし」）と、設定のファイルのパスを出す。
- R4: `ladder.py setup --reset` を実行したとき、ladder.py は `models.md` を消し（無くても 0 で終わる）、既定に戻ったと出す。`--reset 実装` か `--reset 評価` のときは、その役の行だけを消し（行が残らなければファイルを消す）、その役が既定に戻ったと出す。
- R5: 手元の設定が読めるとき、`autopilot.py init` は作る spec.md の `## モデル` 節に、設定の行を雛形のコメントの後にそのまま写し、写した行を stderr に NOTE で出す。
- R6: 手元の設定が無いとき、`autopilot.py init` が作る spec.md は今の雛形と同じ中身になる。
- R7: 手元の設定が読めない（読めない行・受けない段・同じ役の 2 行がある、UTF-8 で読めない）とき、`autopilot.py init` は spec を作って 0 で終わり、`## モデル` 節を雛形のまま残し、設定の誤りと直し方（`ladder.py setup` か `ladder.py setup --reset`）を stderr に NOTE で出す。
- R8: `commands/setup.md`（`/spec-autopilot:setup`）は、実装役・評価役ごとに今の段と受ける段を示して人に 1 つ選ばせ（今の段を先頭に、既定に戻す選択も含める）、選んだ段を R1 か R4 で設定に書き、書いた結果をそのまま人に示す手順を持つ。plugin の README に、setup の使い方と、写すのは init の時点だけ（作った後の spec は変わらない）ことを書く。
- R9: plugin.json の `version` を 0.1.14 より上げる。

## 非目標
- 照合役・相談役（autopilot-spec-checker・fable-advisor・advice-checker・opus-advisor）のモデルの上書き（相談役は別のモデルで見ることが役なので）
- `ladder.RUNGS` に無いモデル・effort（Haiku など）を選べるようにすること
- 作った後の spec への設定の反映（直したいときは spec の `## モデル` を直す）
- repo ごとの設定、pstack の budget（large・medium・small）のようなまとめての切り替え
- 足すなら: 設定を写したかを runs.jsonl に残す

## 影響範囲
- 変える: plugins/spec-autopilot/scripts/ladder.py（全体）
  - メモ: 設定の読み書きと setup・show の CLI を足す。梯子の段の計算（climb・impl_agent・review_agent）は変えない
- 変える: plugins/spec-autopilot/scripts/autopilot.py:886-898（cmd_init）
  - メモ: 雛形を写す 895〜896 行だけ。1500 行を超えているので、行を増やさない
- 新規: plugins/spec-autopilot/commands/setup.md
- 変える: plugins/spec-autopilot/README.md（全体）
  - メモ: setup の節を足す
- 変える: plugins/spec-autopilot/.claude-plugin/plugin.json（全体）
  - メモ: version だけ
- 変える: plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py:67（test_version_is_raised_past_0_1_13）
- 変える: plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py:42-47（test_referenced_files_exist）
  - メモ: 全部の command に references/ を 1 つ以上指すよう求める assert を、autopilot.md だけに求める形にする（setup.md は references/ を読まない。指すファイルが実在するかは全部の command で見続ける）
- 呼び出し元: plugins/spec-autopilot/scripts/autopilot.py:1482
- 手本: plugins/spec-autopilot/tests/test_autopilot.py:196（test_init_creates_artifacts_in_discovery）
- 手本: plugins/spec-autopilot/tests/test_ladder.py:169（test_the_spec_can_start_a_role_higher）
- 同じ入力: なし
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_ladder.py plugins/spec-autopilot/tests/test_autopilot.py plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py -q -n auto

## 変えない挙動
- spec の `## モデル` に書いた段から梯子が始まる: plugins/spec-autopilot/tests/test_ladder.py::test_the_spec_can_start_a_role_higher
- 節が空なら既定の実装役・評価役になる: plugins/spec-autopilot/tests/test_ladder.py::test_the_default_agents_are_the_measured_pair
- lint が知らない段と評価役の既定より下の段を断る: plugins/spec-autopilot/tests/test_ladder.py::test_lint_refuses_an_unknown_rung_or_a_reviewer_below_the_default
- init が discovery の spec を作る: plugins/spec-autopilot/tests/test_autopilot.py::test_init_creates_artifacts_in_discovery

## 前提
- 目的に届く: 届くのは、設定の後に init する spec だけ。設定の前に作った spec と、init を通らない spec には効かない。選べるのは梯子の段だけで、pstack のように任意のモデル名は選べない
- 運用: 利用者が plugin を入れた後か、既定を変えたいときに 1 回 `/spec-autopilot:setup` を回す。設定は `SPEC_AUTOPILOT_HOME` の下に残り、plugin の更新では消えない。段の名前が変わったら、init の NOTE が直し方を示す
- 普通のやり方: pstack は `/setup-pstack` で使えるモデルを調べて役ごとに選ばせ、Claude Code では `~/.claude/rules/pstack-models.md` に書き出し、行を消すと既定に戻る（https://github.com/backnotprop/pstack/blob/main/skills/setup-pstack/SKILL.md）。手順との対応: 使えるモデルを調べる → 扱わない（選べるのは梯子の段だけで、R3 が段の一覧を出す）。今の設定を読む → R3。budget を選ぶ → 扱わない（非目標）。役ごとに選んで確かめる → R8。書く前に検証する → R2。書き出す → R1。行を消すと既定に戻る → R4。検証の skill を勧める → 扱わない（/autopilot の 0 の 4 が verify skill を扱う）
- 過去: 実装役の既定は、5 本の spec の計測で Sonnet 5.5 の effort high に変えた（docs/adr/2026-11-25-implementer-default-high.md、`git log -- plugins/spec-autopilot/scripts/ladder.py` の dd51265）。手元で既定を変える道はこれまで無かった
- 前提: 梯子は spec.md の `## モデル` 節だけを読み、ほかの設定を読まない
  - path: plugins/spec-autopilot/scripts/ladder.py:61-66（climb）
  - path: plugins/spec-autopilot/scripts/overnight.py:1255-1256（model_section）
  - path: plugins/spec-autopilot/scripts/autopilot.py:1230
- 前提: init は雛形の spec.md をそのまま写す
  - path: plugins/spec-autopilot/scripts/autopilot.py:895-896
- 前提: lint は `## モデル` 節を `ladder.lint` で検査する
  - path: plugins/spec-autopilot/scripts/autopilot.py:643
  - path: plugins/spec-autopilot/scripts/ladder.py:47-58
- 前提: 手元の記録の置き場は `SPEC_AUTOPILOT_HOME`、無ければ `~/.claude/spec-autopilot` で、ほかのスクリプトも同じ決め方をしている
  - path: plugins/spec-autopilot/scripts/autopilot.py:310
  - path: plugins/spec-autopilot/scripts/runlog.py:12
- 前提: Agent の起動の model は別名しか受けないので、段ごとに agent の定義を分けている
  - path: plugins/spec-autopilot/scripts/ladder.py:1-3
- 前提: plugin の `commands/<名前>.md` は `/<plugin 名>:<名前>` の command になる
  - URL: https://code.claude.com/docs/en/plugins-reference
- 前提: ladder.py には今 CLI の入口が無い
  - コマンド: `grep -n "__main__\|argparse" plugins/spec-autopilot/scripts/ladder.py` → 出力なし

## 作り方
この spec の ADR のとおり。受ける段は `ladder.RUNGS` の段で、設定の検査は spec の節と同じ `ladder.lint` を使う。`ladder.py` に、設定のパス（`SPEC_AUTOPILOT_HOME` の `models.md`）・読み（`parse` と `lint` を使う）・書き、雛形の `## モデル` 節に行を写す関数、`setup`・`show` の CLI を足す。`autopilot.py` の init は、雛形を写す行を、spec.md だけその関数を通して書く形に置き換え、行を増やさない。command の `setup.md` は、`ladder.py show` を読んで役ごとに AskUserQuestion で選ばせ、`ladder.py setup` を打つ。版数のテストは、0.1.14 を超えたことを見るものに置き換える。`test_referenced_files_exist` は、references/ を 1 つ以上指す求めを autopilot.md だけにする。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | 一時ディレクトリを `SPEC_AUTOPILOT_HOME` にして `ladder.py setup --impl opus-medium` → `--review opus-xhigh` の順に打ち、models.md を読む | 2 行とも残り、出力にパスと中身が出る |
| R2 | 手元で実物 | 同じ置き場で `--impl haiku`・`--review sonnet-high`・引数なしを打つ | どれも 0 以外で、受ける段が出て、models.md が打つ前と同じ |
| R3 | 手元で実物 | 設定のある置き場と無い置き場で `ladder.py show` を打つ | 役ごとに段の一覧・既定・設定（無ければ「なし」）・パスが出る |
| R4 | 手元で実物 | 2 行の設定で `--reset 実装` を打ち、続けて `--reset` を設定のある置き場と無い置き場で打つ | `--reset 実装` の後は評価の行だけが残り、`--reset` はどちらも 0 で、models.md が無くなる |
| R5 | 手元で実物 | 設定のある置き場で、一時の git repo で `autopilot.py init` を打ち、spec.md の `## モデル` 節を読み、`autopilot.py lint` を回す | 設定の行が節にあり、NOTE が出て、lint がモデルの節の誤りを出さない |
| R6 | 手元で実物 | 設定の無い置き場で init を打ち、spec.md を雛形と比べる | 中身が同じ |
| R7 | 手元で実物 | models.md に `- 実装: haiku` と、UTF-8 でないバイト列を置いて、それぞれ init を打つ | どちらも 0 で終わり、節は雛形のまま、NOTE に誤りと直し方が出る |
| R8 | 手元で実物 | 評価役が commands/setup.md の手順に書かれたコマンドを、一時の置き場でそのとおりに打ち、README の節を読む | 手順のコマンドが通り、手順が show の出力から選択肢を作って setup を打ち、README に使い方と写すのが init の時点だけだと書いてある |
| R9 | 手元で実物 | plugin.json を読み、test_spec_autopilot_wiring.py を回す | version が 0.1.14 より上で、テストが通る |

## 制約
- 予算: 90 分
- 大きさ: M
- playbook: feature
- autopilot.py は今の 1526 行から増やさない（足す処理は ladder.py に置く）
- 変えるのは設定を写す道だけで、hook と承認・check の判定は変えない

## モデル
<!-- 書かなければ既定（実装 sonnet-high・評価 opus-high）。始めから上げる役だけ書く。実装: sonnet-high・opus-medium・opus-xhigh・fable、評価: opus-high・opus-xhigh・fable（評価は既定より下げない） -->

## 自走の範囲
- 範囲: マージまで
- QA の環境:
- QA の書き込み先:
- デプロイの起動:
- デプロイの確かめ:
- ロールバック: revert の PR をマージし、デプロイの完了を確かめる
- 通知: デスクトップ
- AWS の profile: なし

## 止まる条件
- 合意した要件のどれかを満たす方法が無いと分かったとき（その要件だけを park に積み、ほかを進める。どの要件も進められないときだけ block）
- 承認した自走の範囲の外の操作が要るとき（実行せずに park に積む）
