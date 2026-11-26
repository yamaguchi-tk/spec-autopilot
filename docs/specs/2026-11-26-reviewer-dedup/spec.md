# 評価役のテストの重複と、テストの遅さを減らす

- ADR: docs/adr/2026-11-26-test-time.md

## 目的
人は「評価役を短くする方策」を求め、評価の深さ（要件ごとの確かめ・変異）は減らさないと決めた。今夜の 2 本の spec で、テスト全体を実装役・評価役・CI の 3 か所で回し、CI は 1 本で 7 分 44 秒かかった。check の時間を測るテストは負荷で 1 回落ちた。調べると、評価役の定義は spec の `- 回帰テスト:` を回すだけで、重複の原因は、今夜の 2 本がそこにテスト全体を書いたことだった（関係するテストだけを書く規則は plugin にすでにある）。できあがったら、回帰テストに全体を書いた spec は承認の前に照合役が止め、CI の待ちが短くなり、時間を測るテストが負荷で落ちにくくなる。

## 要件
- R1: PR の CI（`.github/workflows/test.yml`）が動くとき、CI はテストを並列で回して全件を通し、入れる道具の版はどれも固定する。
- R2: tasks.md の行を `autopilot.TASK` で照合するとき、照合の結果（タスクと読むか、印・番号・最後の括弧の中身）は今の正規表現と同じになり、`[` が 3980 個続く行を 49 行足した tasks.md で `autopilot.py check` を回すと、子プロセスの CPU 時間 1 秒未満で終わる。
- R3: spec の `- 回帰テスト:` がテストの置き場そのもの（テスト全体）を回すコマンドのとき、autopilot-spec-checker は影響範囲の照合の項目を ng にし、変えるモジュールを参照するテストのファイルを並べるよう直し方を書く。
- R4: repo の CLAUDE.md は、テストを回すコマンドを `-n auto` 付きで書き、手元に道具を入れるときは workflow の pip install の行を回すと書く（版は workflow の 1 か所にだけ書く）。
- R5: `plugin.json` の version を 0.1.10 より上げる。

## 非目標
- 評価役・実装役の定義（agents/autopilot-reviewer*.md・autopilot-implementer*.md）を変えること
- テストが CLI を subprocess で呼ぶ形を変えること
- autopilot.py の外の正規表現と、ほかのテストの時間を直すこと（負荷で落ちた test_overnight.py::test_the_wait_is_not_counted_in_the_budget は、再現手順を添えて Issue にする）

## 影響範囲
- 変える: .github/workflows/test.yml（全体）
  - メモ: 28〜31 行の pip install と pytest の行だけ
- 変える: plugins/spec-autopilot/scripts/autopilot.py:90（TASK）
- 変える: plugins/spec-autopilot/scripts/autopilot.py:630（MAX_ARTIFACT_LINE）
  - メモ: TASK が 2 乗と書いたコメントだけ
- 変える: plugins/spec-autopilot/tests/test_qa_evidence.py:115-185（quick、LONG、WORST）
  - メモ: 2 乗と書いたコメントと、時間の確かめ
- 変える: plugins/spec-autopilot/agents/autopilot-spec-checker.md（全体）
  - メモ: 12 行目の影響範囲の照合の項目だけ
- 変える: plugins/spec-autopilot/.claude-plugin/plugin.json（全体）
  - メモ: version だけ
- 変える: CLAUDE.md（全体）
  - メモ: 5 行目のテストを回すコマンドの行だけ
- 呼び出し元: plugins/spec-autopilot/scripts/autopilot.py:673
- 呼び出し元: plugins/spec-autopilot/scripts/overnight.py:1039
- 呼び出し元: plugins/spec-autopilot/scripts/overnight.py:1258
- 手本: plugins/spec-autopilot/tests/test_qa_evidence.py:170-186（WORST と test_check_ends_quickly_on_the_worst_lines_within_the_limits）
- 同じ入力: なし
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_qa_evidence.py plugins/spec-autopilot/tests/test_ladder.py plugins/spec-autopilot/tests/test_autopilot.py plugins/spec-autopilot/tests/test_overnight.py plugins/spec-autopilot/tests/test_agent_gate.py plugins/spec-autopilot/tests/test_prototype_gate.py plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py -q -n auto

## 変えない挙動
- 長い行の最悪の形でも check が上限の内に落ちる側で終わる: plugins/spec-autopilot/tests/test_qa_evidence.py::test_check_ends_quickly_on_the_worst_lines_within_the_limits
- check が受けるタスクの行を、梯子も同じに読む: plugins/spec-autopilot/tests/test_ladder.py::test_a_task_line_that_check_accepts_is_read_the_same_by_the_ladder

## 前提
- 目的に届く: 回帰テストに全体を書いた spec は承認の前に止まる。ただし、ほぼ全部のテストが読むファイル（autopilot.py は 28 ファイル中 17 ファイルが読む）を変える spec では、絞った回帰テストも全体に近くなり、効くのは速さの側だけになる。今夜の 2 本が全体を書いた理由は測っていない。CI の時間がどこまで縮むかは、PR の CI を見るまで分からない（pytest 9.1.1 と pytest-xdist 3.8.0 の組み合わせが CI の Python 3.14 で動くかも）
- 運用: /autopilot の main が spec を書いた後に照合役を回し（commands/autopilot.md の B の 3）、回帰テストの ng を直す。CI は PR のたびに動く。手元では CLAUDE.md の行で道具を入れる
- 普通のやり方: pytest のテストを並列で回すのは pytest-xdist の `-n auto` が普通（https://pytest-xdist.readthedocs.io/en/stable/）
- 過去: 過去の spec 12 本のうち、`- 回帰テスト:` にテスト全体を書いたのは 2026-11-26-advisor-reapproval と 2026-11-26-goal-split の 2 本だけで、ほかの 10 本は関係するテストのファイルを並べていた（docs/specs/*/spec.md の `- 回帰テスト:` の行を grep で数えた）
- 前提: 回帰テストを絞ると、評価役が回すテストの時間はおよそ半分になる
  - コマンド: `この spec の回帰テスト（6 ファイル）と tests/ 全体を -n auto で続けて回した（load average 41〜48）` → 6 ファイルが 146 秒（2 件落ち）、全体が 321 秒
- 前提: 関係するテストだけを回帰テストに書く規則はすでにあり、照合役は回帰テストが変えるモジュールを参照するテストを含むかだけを見る（全体を指しても含むので通る）
  - path: plugins/spec-autopilot/references/existing-repo.md:12
  - path: plugins/spec-autopilot/agents/autopilot-spec-checker.md:12
- 前提: pytest-xdist 3.8.0 は execnet を連れて入る（手元は execnet 2.1.2）
  - コマンド: `python3 -c "import execnet,xdist;print(execnet.__version__, xdist.__version__)"` → 2.1.2 3.8.0
- 前提: CI は pytest-xdist を入れず、テストを 1 本で回す
  - path: .github/workflows/test.yml:28-31
  - コマンド: `gh pr checks 48` → spec-autopilot pass 7m44s
- 前提: 既存の repo の spec は `- 回帰テスト:` が必須で、評価役はそれがあればそのコマンドと足したテストを回す
  - path: plugins/spec-autopilot/scripts/autopilot.py:600-601（lint の ERROR）
  - path: plugins/spec-autopilot/agents/autopilot-reviewer.md:18（評価役の 2）
- 前提: `TASK` は `.*?\[([^\]]*)\]` の形で、`[` が続く行で行の長さの 2 乗の時間を使う
  - path: plugins/spec-autopilot/scripts/autopilot.py:90
  - コマンド: `子プロセスの CPU 時間を測る pytest plugin を付けて tests/test_qa_evidence.py -k ends_quickly を回す` → tasks-brackets の check が CPU 3.29 秒、ほかの形は 0.33 秒以下
- 前提: 時間を測るテストは、check の子プロセスに壁時計で 5 秒の上限を掛ける
  - path: plugins/spec-autopilot/tests/test_qa_evidence.py:115-117（quick）
  - path: plugins/spec-autopilot/tests/test_qa_evidence.py:178-185

## 作り方
この spec の ADR のとおり。CI の workflow の pip install の行で、テストの道具をどれも `==` で版を固定して入れ（pytest 9.1.1・pytest-xdist 3.8.0・execnet 2.1.2）、pytest に `-n auto` を足す。版を書くのは workflow だけにし、CLAUDE.md はその行を回すと書く。`TASK` は、呼び出し元が使う `.match(line)` と `group(1)`〜`group(3)` を持つ形のまま、最後の `]` の前の括弧の中身が今と同じになる、行の長さに比例する照合にする（先に 1 行の正規表現 `^- \[( |x|X)\] (T\d+):(?:.*\])?[^\[\]]*\[([^\]]*)\]\s*$` を試す。同じにならなければ `.match` を持つ小さな読み手にする）。今と同じかは、短い文字（`[`・`]`・空白・全角空白・`x`・`R`）を並べた行の総当たりで、今の正規表現と比べるテストで確かめる。CPU 時間は `resource.getrusage(RUSAGE_CHILDREN)` の差で測る（壁時計で測ると `-n auto` の負荷で揺れる）。照合役の定義は、12 行目の影響範囲の照合に、回帰テストがテストの置き場そのものを回すなら ng にする文を足す。CLAUDE.md の 5 行目を直す。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | workflow を読み、pip install と pytest の行を手元でそのまま回す。CI の時間は main がマージの前に PR の CI で見て PR 本文に書く | pip install の道具がどれも `==` で、並列の指定が付き、手元で全件通り、PR の CI が 7 分 44 秒より短い |
| R2 | 手元で実物 | 総当たりの行と、ふつうの行・`[` の連なり・`- [x] T1: a] [R1]`・`[]`・末尾の全角空白の行で、今の正規表現と新しい照合を比べる repo のテストを回す。手本の WORST の tasks-brackets の形で check を回し、子プロセスの CPU 時間を getrusage で base と tip で測る | 全部の行で結果が同じで、tip の CPU 時間が 1 秒未満（base は約 3.3 秒） |
| R3 | 手元で実物 | 評価役が照合役の定義を読み、docs/specs/2026-11-26-goal-split/spec.md の `- 回帰テスト:` の行に当てたときに ng になるかを読む | 影響範囲の照合の項目に、テストの置き場そのものを回すなら ng とする文があり、goal-split の行が ng に当たる |
| R4 | 手元で実物 | 評価役が CLAUDE.md を読み、書かれたコマンドを手元で回す | テストのコマンドに `-n auto` があり、道具の入れ方が workflow の pip install の行を指し、CLAUDE.md に版の数字が無く、テストのコマンドが通る |
| R5 | 手元で実物 | plugin.json と marketplace.json を読み、test_spec_autopilot_wiring.py を回す | version が 0.1.10 より上で、テストが通る |

## 制約
- 予算: 75 分
- 大きさ: M
- playbook: bug-fix
- autopilot.py は 1500 行を超えない（今 1500 行。照合を足すなら、挙動を変えない別の commit で行を減らすか、別のモジュールに置く）

## モデル

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
