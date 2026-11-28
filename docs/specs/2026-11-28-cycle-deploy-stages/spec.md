# deploy.py と stages.py を autopilot.py から外し、import の輪を 8 モジュールから 6 モジュールに縮める

- ADR: docs/adr/2026-11-28-cycle-deploy-stages.md

## 目的
人の発言:「結合度　凝集度　複雑さ 等々の必要なソフトウェアメトリクスを指標にして欲しい」「リファクタの spec」「承認する」。親の spec（2026-11-28-metrics-refactor-goal）の R4・R5 のうち、最初の 1 本を受け持つ。

観測: 今の scripts は 8 モジュール（autopilot・deploy・goal・light・lineup・overnight・preflight・runlog）が 1 つの import の輪で、道具が数える循環の組は 28。deploy.py は autopilot.py の補助（section・COMMENT_BLOCK・repo_root・git_lines・BUDGET・QA_ROW・TEST_PATH・NOT_CODE・MAX_REWORKS）を借り、さらに autopilot のモジュールごとを stages.py の関数に引数で渡している。preflight.py は deploy.py だけを import するので、deploy.py が輪を出れば一緒に出る。lint は 1 本の spec が 6 つ以上のコードのファイルを変えると L として止めるので、輪を 0 にする親の R4 は、5 ファイル以内の子に分けて順に回す。この子はその 1 本目。

できあがったら、deploy.py・preflight.py・stages.py は autopilot.py に依らず、下の層のモジュールだけに依る。輪は autopilot・goal・light・lineup・overnight・runlog の 6 つに縮む。

## 要件
- R1: plugins/spec-autopilot/scripts を測ったとき、deploy.py・preflight.py・stages.py は import の輪に入らず、輪は autopilot.py・goal.py・light.py・lineup.py・overnight.py・runlog.py の 6 つの 1 つだけで、循環の組は 28 から 15 に減る。
- R2: deploy.py と stages.py を読んだとき、どちらも autopilot を import せず（関数の中の import と `__import__` を含む）、stages.py の関数は autopilot のモジュールを引数に受けず、deploy.py と autopilot.py は stages.py の関数にモジュールを渡さない。輪を `importlib`・変数で名前を渡す `__import__`・`sys.modules` に替えて道具に見えなくする形も無い。
- R3: この spec で足す下の層のモジュール（spectext.py と repo.py）は、scripts のほかのモジュールを import せず、測ったときの LCOM4 が 2 以下になる。
- R4: テストの全量を回したとき全部が通り、CLI の lint・check・status を、変える前と後で同じ spec に回した出力が同じで、指標の前後の比べ方（変える前の着手の commit を前にする）で悪化が無く、「移しただけ」と出ない。テストは名前の向け先だけを変え、期待は変えない。

## 非目標
- goal・light・lineup・overnight・runlog・watch・hooks を autopilot.py から外すこと（後の子で扱う。この子の後も、それらは移した名前を autopilot.py を通して使い続け、後の子が向け直す）
- premises.py・rootcause.py・size_note.py が受ける `sys.modules[__name__]` を直すこと（後の子で扱う）
- 複雑度・凝集度を目標にすること（親の R2・R3 の子で扱う。悪化だけを止める）
- 挙動・CLI の出力・エラー文を変えること
- 版数を上げること

## 影響範囲
- 変える: plugins/spec-autopilot/scripts/autopilot.py（全体）
  - メモ: 83 の TEST_PATH・85 の NOT_CODE・89 の REQ・91 の BUDGET・97 の COMMENT・98 の COMMENT_BLOCK・99 の MAX_REWORKS・104 の QA_ROW と、115 の repo_root・376 の section・381 の classify・398 の requirement_lines・404 の requirements・408 の git_lines を下の層に出し、autopilot.py はそこから import して使う。650 の stages.lint にモジュールを渡さない
- 変える: plugins/spec-autopilot/scripts/deploy.py（全体）
  - メモ: 9 の `import autopilot` を下の層の import に替え、127・131・184・232・306・309・338・436 で stages にモジュールを渡さない
- 変える: plugins/spec-autopilot/scripts/stages.py（全体）
  - メモ: 28 の plan・38 の lint・57 の deployed_reqs・92 の approved・154 の check が引数の autopilot を受けず、下の層を直接 import する
- 新規: plugins/spec-autopilot/scripts/spectext.py
  - メモ: spec と qa.md の文の読み取り（section・classify・requirement_lines・requirements と、その正規表現）
- 新規: plugins/spec-autopilot/scripts/repo.py
  - メモ: repo の場所と git の出力の読み取り（repo_root・git_lines と、パスの分け方の正規表現）
- 呼び出し元: plugins/spec-autopilot/scripts/preflight.py:53
  - メモ: deploy を関数の中で import する（ほかに 132）。preflight.py は変えない
- 呼び出し元: plugins/spec-autopilot/scripts/lineup.py:40
  - メモ: deploy を関数の中で import する。lineup.py は変えない
- 呼び出し元: plugins/spec-autopilot/scripts/watch.py:250
  - メモ: tick_one が deploy を引数で受ける。watch.py は変えない
- 呼び出し元: plugins/spec-autopilot/hooks/stop.py:73
  - メモ: autopilot と deploy を import する。hooks は変えない
- 手本: plugins/spec-autopilot/scripts/carry.py:1-21（ほかの scripts を import しない小さいモジュール）
- 同じ入力: なし
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/ -q -n auto
  - メモ: autopilot・deploy・stages は tests/ のほとんどが参照するので、全量を回す

## 変えない挙動
- テストの全量: plugins/spec-autopilot/tests/
- マージ・デプロイ・QA の段の判定: plugins/spec-autopilot/tests/test_merge_qa.py
- QA の段の判定: plugins/spec-autopilot/tests/test_stages.py

## 前提
- 目的に届く: 輪は 8 から 6 モジュールに縮むが、0 にはならない。残りの goal・light・lineup・overnight・runlog と、premises・rootcause・size_note の `sys.modules[__name__]` と hooks は、後の子で向け直す。この子の間は、移した名前をほかのモジュールが autopilot.py を通して使い続ける（autopilot.py 自身もその名前を使うので、出し直しのためだけの import にはならない）
- 運用: 指標は repo の外の測る道具（refactor-metrics の skill）で測る。評価役は、手元の道具で着手の commit と tip を比べる
- 普通のやり方: import の輪は、共通の部分を下の層に出し、依存の向きを 1 つにそろえて切る。モジュールを引数で渡す形は、依存を道具から隠すだけなので直接の import に替える
  - メモ: 親の spec の普通のやり方の項と、この spec の ADR
- 過去: 2026-11-26-split-modules は deploy.py を autopilot.py から行数で切り出し、deploy.py が autopilot を import する向きを残したので輪が増えた
  - メモ: docs/specs/2026-11-26-split-modules/spec.md
- 前提: 今の scripts の import の輪は 8 モジュールの 1 つで、循環の組は 28、deploy.py の LCOM4 は 5、stages.py は 1、autopilot.py は 4、fan-out は autopilot.py が 16
  - コマンド: `uv run --with lizard python <refactor-metrics の skill>/scripts/measure.py plugins/spec-autopilot/scripts` → 循環の組 28（main の d344a42 で測った）
- 前提: deploy.py が autopilot から使う名前は section・COMMENT_BLOCK・BUDGET・git_lines・TEST_PATH・NOT_CODE・repo_root・QA_ROW・MAX_REWORKS と、stages にモジュールを渡す 8 か所だけ
  - コマンド: `grep -nE '\bautopilot\b' plugins/spec-autopilot/scripts/deploy.py` → 9 の import と上の名前（36・46・49・55・56・109・127・131・167・170・178・184・232・306・309・338・411・431・436・437）
- 前提: stages.py が引数の autopilot から使うのは COMMENT_BLOCK・section・requirements・repo_root だけ
  - path: plugins/spec-autopilot/scripts/stages.py:28（ほかに 38・57・92・154）
- 前提: preflight.py が import する scripts のモジュールは deploy.py だけ
  - path: plugins/spec-autopilot/scripts/preflight.py:53（ほかに 132）
- 前提: 道具の LCOM4 は、同じトップレベルの名前（関数を除く）を使うか呼び合う関数をつなぎ、import した名前はつなぎに数えない
  - コマンド: `grep -n "def lcom4" -A10 <refactor-metrics の skill>/scripts/measure.py` → used はトップレベルの名前との積だけ

## 作り方
この spec の ADR のとおり、deploy.py と stages.py が autopilot.py から借りている補助を、役ごとの下の層の 2 つのモジュールに出す。spectext.py には spec と qa.md の文の読み取り（section・classify・requirement_lines・requirements と REQ・COMMENT・COMMENT_BLOCK・BUDGET・QA_ROW）、repo.py には repo の場所と git の出力の読み取り（repo_root・git_lines と TEST_PATH・NOT_CODE）を置く。MAX_REWORKS は、行ごと置き場を 1 つに決めて deploy.py と autopilot.py がそこから import する（置き場はこの 2 つのモジュールか stages.py。メモに残す）。autopilot.py は自分が使う名前をそこから import する。deploy.py と stages.py は下の層を直接 import し、stages.py の関数の引数の autopilot を外す。ほかのモジュール・hooks・テストが autopilot.<名前> で使う移した名前は、この子では向け直さない（テストは向け直してよい）。下の層の 2 つのモジュールの LCOM4 が 2 を超えるなら、役ごとにさらに分ける（そのときは 5 ファイルを超えないよう、ほかの名前を移さない）。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | 着手の commit を前、tip を後にして、指標の前後の比べ方を回し、輪と循環の組を読む | 輪が 6 モジュールの 1 つで、deploy・preflight・stages が入らず、循環の組が 15 |
| R2 | 手元で実物 | deploy.py・stages.py を `autopilot`・`importlib`・`sys.modules`・`__import__` で grep し、stages.py の関数の引数を読む | grep が 0 件で、引数に autopilot が無い |
| R3 | 手元で実物 | spectext.py と repo.py の import を読み、指標の前後の比べ方の LCOM4 を読む | scripts のモジュールを import せず、LCOM4 が 2 以下 |
| R4 | 手元で実物 | テストの全量を回し、着手の commit と tip で同じ spec に CLI の lint・check・status を回して出力を突き合わせ、指標の前後の比べ方を回す | 全部通り、出力が同じで、悪化 0、「移しただけ」と出ない |

## 制約
- 予算: 60 分
- 大きさ: M
- playbook: なし（refactor の playbook は手元の plugin を更新するまで lint が読めない）
- 親 spec: 2026-11-28-metrics-refactor-goal
- 親の要件: R4、R5
- 想定する脅威: なし（hook と判定の結果を変えない。判定の関数の import 先だけを変えるので、テストの全量で守る）

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
- 合意した要件を満たす方法が無いと分かったとき（park に積む。どの要件も進められないときだけ block）
- 承認した自走の範囲の外の操作が要るとき（実行せずに park に積む）
- 指標の前後の比べ方で悪化が出て、直すと別の指標が悪化するとき（その要件を park に積み、朝の報告に書く）
