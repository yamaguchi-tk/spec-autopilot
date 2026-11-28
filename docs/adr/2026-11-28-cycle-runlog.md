# ADR: runlog.py が借りる stated_size を stages.py に移し、git の呼び出しをまとめて stages.py の凝集度を保つ

- 日付: 2026-11-28
- 状態: Accepted
- spec: docs/specs/2026-11-28-cycle-runlog

## Context
import の輪は、1 本目の子の後に 6 モジュール（autopilot・goal・light・lineup・overnight・runlog）になった。runlog.py が autopilot.py から借りる名前のうち、stated_size だけがまだ autopilot.py にある。親の R5 は子ごとに指標の悪化を禁じる。autopilot.py の fan-out は 16 で、目安の高（15）を超えているので、新しいモジュールを足すと悪化になる。stages.py の LCOM4 は 2 で、stated_size をそのまま足すと 3 になって悪化になる。

## 選択肢
1. stated_size を stages.py に移し、stages.py の repo_root と git_lines が同じ形で書く git の呼び出しを 1 つの関数にまとめる: git_lines が repo_root とつながるので、stated_size を足しても LCOM4 は 2 に収まる。変えるファイルは 3
2. stated_size を新しいモジュールに出す: stages.py の役は増えないが、autopilot.py の fan-out が 17 になって悪化になる
3. runlog.record の呼び出し元が大きさを引数で渡す: runlog.py は何も import しなくなるが、呼び出し元の autopilot.py・goal.py・lineup.py などを変えるので、変えるファイルが増え、呼び出し元ごとに大きさを読む重複ができる

## Decision
1 を選ぶ。git を呼ぶ関数は、今の 2 か所と同じ引数・capture_output・text・cwd で git を呼び、repo_root の OSError の扱いと git_lines の終了コードの扱いは呼ぶ側に残す。

- 直し方: 設計を変える
- 退けた: 要らなくする（stated_size は lint・runs.jsonl の記録・大きさの検査がこれからも使う。消せない）
- 退けた: 入力の約束を変える（runs.jsonl の行の形や spec の大きさの行の書式を変えても、runlog.py が大きさを読むための依存は残る）

## Consequences
- runlog.py は stages.py だけに依る。輪は 5 モジュールになる
- stages.py は、QA の段の判定・spec の文の読み取り・git の補助に加え、大きさの行の読み取りも持つ。役ごとに分け直すかは、R4 の最後の子で決める
