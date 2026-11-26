# テストの時間の spec の low を直す

- ADR: docs/adr/2026-11-26-test-time-lows.md

## 目的
人が「low の 2 件も直して」と頼んだ。PR 49（2026-11-26-reviewer-dedup）の評価役が挙げた low 2 件を直す。できあがったら、テストのコメントが今の TASK と合い、CLAUDE.md の手順どおりに手元に道具を入れられる。

## 要件
- R1: test_qa_evidence.py の LONG と WORST の前のコメントは、今の TASK が行の長さに比例する時間で読むことと合い、ファイルの中で「2 乗」と書くのは、旧い TASK（OLD_TASK）の説明だけになる。
- R2: PEP 668 で守られた手元の python3 しか無い機械で、CLAUDE.md のテストの行に書いた手順を書いたとおりに（場所もコマンドも読み替えずに）repo の root で回すとき、道具は拒まれずに入り、続けてテストのコマンドが回り、作った venv は `git status` に出ない。行に版の数字は書かない。

## 非目標
- workflow・plugin のコード・agents を変えること
- version を上げること（plugin の中身は変えない）

## 影響範囲
- 変える: CLAUDE.md（全体）
  - メモ: 5 行目のテストの行だけ
- 変える: .gitignore（全体）
  - メモ: `.venv/` の 1 行を足すだけ
- 変える: plugins/spec-autopilot/tests/test_qa_evidence.py:129-180（LONG、WORST）
  - メモ: 2 つのコメントだけ
- 呼び出し元: なし
- 手本: plugins/spec-autopilot/tests/test_ci_workflow.py:33-40（CLAUDE.md の行を読むテスト）
- 同じ入力: なし
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_ci_workflow.py plugins/spec-autopilot/tests/test_qa_evidence.py -q -n auto

## 変えない挙動
- CLAUDE.md のテストのコマンドは `-n auto` 付きで workflow の pip install の行を指す: plugins/spec-autopilot/tests/test_ci_workflow.py::test_claude_md_test_command_uses_n_auto_and_points_to_the_workflow_install_line
- CLAUDE.md に版の数字が無い: plugins/spec-autopilot/tests/test_ci_workflow.py::test_claude_md_has_no_tool_version_numbers

## 前提
- 目的に届く: low の 2 件は無くなる。venv は repo の root の `.venv/` に置く。activate は POSIX のシェルの書き方で、fish や Windows では読み替えが要る
- 運用: この repo を手元で開発する人が CLAUDE.md の行に従って道具を入れる
- 普通のやり方: PEP 668 の環境では、venv を作ってその中で pip install する（https://peps.python.org/pep-0668/）
- 過去: PR 49 の評価役の low（docs/specs/2026-11-26-reviewer-dedup の評価の 1 巡目）で、venv の外の pip install が externally-managed-environment で拒まれた
- 前提: 手元の python3 は PEP 668 で守られ、venv の外の pip install を拒む
  - コマンド: `python3 -m pip install pytest==9.1.1 pytest-xdist==3.8.0 execnet==2.1.2` → error: externally-managed-environment（PR 49 の評価役が回した）
- 前提: test_qa_evidence.py の 129 行と 180 行のコメントが TASK を「2 乗」と書き、215 行の OLD_TASK の説明も「2 乗」と書く
  - path: plugins/spec-autopilot/tests/test_qa_evidence.py:129
  - path: plugins/spec-autopilot/tests/test_qa_evidence.py:180
  - path: plugins/spec-autopilot/tests/test_qa_evidence.py:215
- 前提: repo の .gitignore は `.venv/` を外しておらず、git の info/exclude が外すのは `.autopilot-qa/` だけ
  - path: .gitignore:1-5
  - path: plugins/spec-autopilot/scripts/autopilot.py:914-924（exclude_check_scripts）
- 前提: CLAUDE.md の行は、テストのコマンドに `-n auto` と `pip install` と workflow のパスがあり、版の数字が無いことを test_ci_workflow.py が読む
  - path: plugins/spec-autopilot/tests/test_ci_workflow.py:33-40

## 作り方
この spec の ADR のとおり。CLAUDE.md の 5 行目の「手元に道具を入れるときは、その workflow の `pip install` の行を回す」を、repo の root で venv を作って有効にし（`python3 -m venv .venv` と `source .venv/bin/activate`）、その中で workflow の `pip install` の行とテストのコマンドをそのまま回す形にする（有効にすれば `python3` が venv の python を指すので、行を読み替えなくてよい）。手順は、test_ci_workflow.py が読む 5 行目（`python3 -m pytest` を含む行）の中に書く（行を分けるとそのテストが落ちる）。.gitignore に `.venv/` を足す。コメントは、長すぎる行を正規表現に通さない理由と、WORST の tasks-brackets の形の説明を、今の TASK に合わせる。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | `git grep -n '2 乗' -- plugins/spec-autopilot/tests/test_qa_evidence.py` を base と tip で回し、2 つのコメントを読む | base は 3 か所に当たり、tip は OLD_TASK の説明の 1 か所だけで、2 つのコメントが今の TASK と合う |
| R2 | 手元で実物 | repo の写し（`.autopilot-qa/` の下の `git worktree` か clone）の root で、CLAUDE.md の 5 行目の手順を読み替えずに 1 本の Bash でつないで回す（`python3 -m venv .venv && source .venv/bin/activate && <workflow の pip install の行> && <回帰テストのコマンド>`）。base の手順（venv の外の pip install）も回す。続けて `git status --porcelain` を見る | base は externally-managed-environment で拒まれ、tip は pip install が終わり、回帰テストが通り、`.venv/` が git status に出ない |

## 制約
- 予算: 30 分
- 大きさ: M
- playbook: bug-fix
- 手戻り元: 2026-11-26-reviewer-dedup

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
