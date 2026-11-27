# 依る spec を state.json に名前で書く

- ADR: docs/adr/2026-11-27-lineup-relative-after.md

## 目的
人の言葉:「spec にする」（lineup.py の絶対パスの再発防止）。

観測（2026-11-27）: `lineup.py` の enqueue が、依る spec のディレクトリを絶対パスで state.json の `after` に書き、docs/specs/2026-11-27-s-prototype-tests/state.json が commit されて、公開の main に手元のパスが入った。履歴の書き換えで消したが、直さないと次の依る spec でまた入る。

できあがったら、state.json に入るのは依る spec のディレクトリ名だけになり、手元のパスは commit されない。

## 要件
- R1: 依る spec のある spec を `approve --queue` で承認したとき、lineup.py は state.json の `after` に依る spec のディレクトリ名だけを書き、絶対パスと手元のパスを書かない。
- R2: `lineup.py next` と Stop hook が依る spec を探すとき、lineup.py は `after` の名前と同じ名前の、このセッションで承認した spec を依る spec とし、依る spec が別の worktree にあっても今と同じく着手・block を決める。
- R3: 依る spec を名前で 1 本に決められない（同じ名前が無い・2 本以上ある）とき、`lineup.py next` はその spec を block にし、黙って着手しない。Stop hook はその spec を着手できるものに数えない。

## 非目標
- すでに commit された state.json の書き換え
- セッションの記録（repo の外）に入る絶対パスを変えること

## 影響範囲
- 変える: plugins/spec-autopilot/scripts/lineup.py:64-70（enqueue）
- 変える: plugins/spec-autopilot/scripts/lineup.py:137-142（dependency）
  - メモ: 呼び出しの 150・177・231 行に、呼び出し元が持つ rows（記録した spec と state の組）を渡す
- 変える: plugins/spec-autopilot/scripts/lineup.py:145-187（start、startable、demand）
  - メモ: demand は rows を持つので、hooks/stop.py:375-382 の lineup_demand と watch.py は引数が変わらず、変えない
- 変える: plugins/spec-autopilot/tests/test_lineup.py（全体）
- 呼び出し元: plugins/spec-autopilot/hooks/stop.py:382
- 手本: plugins/spec-autopilot/scripts/lineup.py:56（名前でセッションの記録を引く書き方）
- 同じ入力: なし
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_lineup.py -q

## 変えない挙動
- 別の worktree にある依る spec の先端に載せ替えて着手する: plugins/spec-autopilot/tests/test_lineup.py

## 前提
- 目的に届く: 届く。lineup.py が state.json に書くパスは `after` だけ
- 前提: lineup.py が state.json に書くパスは enqueue の `after` だけ
  - path: plugins/spec-autopilot/scripts/lineup.py:66
- 運用: 変更が効くのは、マージの後に人が plugin の checkout を pull してから
- 普通のやり方: なし（この plugin だけの記録）
- 過去: 2026-11-27 の履歴の書き換えで、s-prototype-tests の state.json の絶対パスを相対に直した
- 前提: 依る spec は、承認の時点でこのセッションの記録にある（無ければ承認が止まる）
  - path: plugins/spec-autopilot/scripts/lineup.py:56-57
- 前提: セッションの記録は repo の外に置かれる
  - path: plugins/spec-autopilot/scripts/autopilot.py:306-322
- 前提: next は CLAUDE_CODE_SESSION_ID、Stop hook は payload の session_id で記録を引き、どちらも記録した spec と state の組を lineup に渡す
  - path: plugins/spec-autopilot/scripts/lineup.py:217-218
  - path: plugins/spec-autopilot/hooks/stop.py:380-382
- 前提: 今は `after` のパスが無いと load_state が例外で落ちる
  - path: plugins/spec-autopilot/scripts/lineup.py:141-142

## 作り方
この spec の ADR のとおり、`after` には名前だけを書く。読む側（dependency）は、呼び出し元が持つ記録した spec の組から名前で引く（値がパスなら最後の要素で引くので、前の版の値も読める）。1 本に決まらなければ依る spec が無いとはせず、block の側に倒す。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | 依る spec を queue で承認するテストで state.json を読む | `after` がディレクトリ名と一致し、`/` を含まない |
| R2 | 手元で実物 | 回帰テストを回す（別の worktree の依る spec と、古い絶対パスの値を含む） | 全部通る |
| R3 | 手元で実物 | 依る spec の名前が記録に無い・2 本ある state で next と demand を呼ぶテスト | next が block にし、demand が着手できるものに数えない |

## 制約
- 予算: 30 分
- 大きさ: M
- playbook: bug-fix
- 脅威: 事故だけ（手元のパスの漏れ）。着手の判定は、依る spec が引けないときに block へ倒す向きだけ変える

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
