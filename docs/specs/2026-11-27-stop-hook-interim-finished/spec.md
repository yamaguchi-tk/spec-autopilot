# Stop hook が subagent の途中の完了を終わりと読まないようにする

- ADR: docs/adr/2026-11-27-stop-hook-interim-finished.md

## 目的
人の言葉:「停止のHookの挙動がおかしいので直近のセッションを調査して」「原因が特定できたら修正して　マージしてPULLまで実施して」。

観測した失敗: background の subagent が、自分で background に回した作業（全量テストなど）を待って turn を終えると、Claude Code は main に「completed（waiting on its own background work。途中の結果）」の通知を送る。このとき Stop hook は、起こし直しの timer が生きていても、timer を求める短い文ではなく、完了の検査の不足の一覧で止め続ける。直近 3 日のセッションの transcript で、この通知の直後の判定は、止めたのが 20 件、放したのが 8 件だった（放した 8 件には、building の spec が無かったときも入る）。止められた main は、手順で禁じた poll（`sleep 15` のループ）で待ち始めた。

できあがったら、途中の完了の後も Stop hook は subagent を待ち中に数え、timer が生きていれば放す。最終の報告が届いた後は、今までどおり完了の検査で止める。

## 要件
- R1: background の subagent が自分の background の作業を待って turn を終え、host がその途中の完了を main に知らせたとき、Stop hook はその subagent を待ち中に数える（subagent の transcript が 15 分以内に書かれていることは今までどおり求める）。生きている起こし直しの timer があれば放し、無ければ timer を求める文で止める。
- R2: subagent が最終の報告を返したとき（途中の完了の後に再開して返したときと、報告の道具を使わずに text で終えたときを含む）、Stop hook はその subagent を終わったとみなし、timer が生きていても完了の検査の不足で止める。
- R3: plugins/spec-autopilot/.claude-plugin/plugin.json の version を 0.1.20 から 0.1.21 に上げ、版数のテストが 0.1.20 を超えたことを確かめ、.claude-plugin/marketplace.json の description は plugin.json と同じに保つ。

## 非目標
- CI を background の `gh pr checks --watch` で待ったときに止める動き（設計どおり。手順は `overnight.py await` を使う）。止める理由の文に await を案内する直しは、別の Issue にする
- 実装役が全量テストを background に回すことを減らす直し
- 途中の完了の後、subagent の background の作業が 15 分を超えて transcript が書かれないときの扱い（今までどおり終わったとみなす）
- 手元の plugin の checkout の pull（人の依頼なので、マージの後に docs/pull-checkout.md の手順で別に行う。自走の範囲に入れない）

## 影響範囲
- 変える: plugins/spec-autopilot/hooks/stop.py:186-238（scan）
- 変える: plugins/spec-autopilot/hooks/stop.py:297-306（_running）
- 変える: plugins/spec-autopilot/hooks/stop.py:309-331（wait_state）
  - メモ: 冒頭の docstring の待ち中の段落（19〜21 行）も直す
- 変える: plugins/spec-autopilot/tests/test_autopilot.py:1802-1825（notified、queued、alive、finished）
  - メモ: finished を書いた agent を終わったとみなす既存のテスト（1959・2021・2076・2087・2104 行）は、最終の形のまま通ることを確かめ、途中の完了の形のテストを足す
- 変える: plugins/spec-autopilot/tests/test_stop_bounds.py:95-101（test_scan_reads_lines_with_u2028_and_carriage_returns_inside）
  - メモ: stop.scan の戻り値を受ける行
- 変える: plugins/spec-autopilot/.claude-plugin/plugin.json（全体）
  - メモ: version の行だけ
- 変える: plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py:68-70（test_version_is_raised_past_0_1_18）
- 呼び出し元: plugins/spec-autopilot/hooks/stop.py:365
  - メモ: decide が wait_state を呼ぶ。wait_state は 317 行で scan、319 行で _running を呼ぶ
- 別の実装: plugins/spec-autopilot/scripts/advisor_approval.py:58-67
  - メモ: 相談役の返答を読むために SubagentHandback の input.message を読む。終わりの判定には使わないので変えない
- 手本: plugins/spec-autopilot/tests/test_autopilot.py:2087-2101（test_stop_hook_ignores_a_finished_meta_written_before_the_resume）
- 同じ入力: SubagentHandback
- 回帰テスト: python3 -m pytest plugins/spec-autopilot/tests/test_autopilot.py plugins/spec-autopilot/tests/test_stop_bounds.py plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py -q -n auto -k "stop_hook or wait_state or scan or version or marketplace or bounds or budget"

## 変えない挙動
- 走っている agent と生きている timer があれば放す: plugins/spec-autopilot/tests/test_autopilot.py::test_stop_hook_releases_while_a_background_agent_runs
- 待ち中の agent があり timer が無ければ timer を求める: plugins/spec-autopilot/tests/test_autopilot.py::test_stop_hook_asks_for_a_timer_while_an_agent_runs
- host の meta.json が無い agent は待ち中に数えない: plugins/spec-autopilot/tests/test_autopilot.py::test_stop_hook_blocks_without_the_host_meta
- 切れた・上限を超える timer では放さない: plugins/spec-autopilot/tests/test_autopilot.py::test_stop_hook_blocks_without_a_live_timer
- host が finished を書いた agent（途中の完了の知らせが無い）は待たない: plugins/spec-autopilot/tests/test_autopilot.py::test_stop_hook_blocks_when_the_host_marked_the_agent_finished
- marketplace の description が plugin.json と同じ: plugins/spec-autopilot/tests/test_spec_autopilot_wiring.py::test_marketplace_entry_matches_manifest

## 前提
- 目的に届く: 届くのは、途中の完了の後に hook が timer で放すところまで。main が止められた後に poll を選ぶかどうかは agent の手順の側の問題で、この spec では直さない
- 運用: /autopilot の main が background の agent を待つとき、Stop hook が判定する（今の手順のまま）。手元の checkout を symlink で使う人には pull の後に、marketplace から入れた人には版数の更新で届く
- 普通のやり方: なし（Claude Code の subagent の記録の読み方に、決まった作り方は無い）
- 過去: plugins/spec-autopilot/tests/test_autopilot.py:2087-2101（再開より前に書かれた finished を数えない直しの前例。起動・再開と比べる形）
- 前提: host は、subagent が自分の background の作業を待って turn を終えた途中の完了でも meta.json に finished を真で書き、再開で消し、最終の報告の後にまた真で書く。途中と最終の meta.json は同じ中身になる
  - コマンド: `python3 で subagents/agent-<id>.meta.json を 0.5 秒ごとに読み、中身の変化を時刻つきで書く（subagent に sleep 90 を background で待たせて turn を終えさせる）` → 途中の完了の通知と同じ時刻に finished が真、再開で消え、最終の報告の後に再び真。2 回の真の中身は同じ。観測はこの再現の 1 本と、調べたセッションの 1 本
- 前提: host は main の transcript に、途中の完了では summary が `is waiting on its own background work` の task-notification を、最終では summary が `finished` の task-notification を書く。SubagentHandback で返したときは、その前に `<agent-message from="<agent の id>">` で始まる hand-back の行も書く
  - コマンド: `上の再現のセッションの main の transcript を python3 で読み、agent の id を含む行を時刻順に並べる` → 途中の完了の task-notification（waiting on its own background work）、hand-back の行（agent-message from）、終わりの task-notification（finished）の順
- 前提: 終わった subagent のすべてが SubagentHandback で返すわけではない。報告の道具を持たない agent・fork は text で終える
  - コマンド: `直近 36 時間の subagents/agent-*.meta.json のうち finished が真のものについて、transcript の末尾 1 MiB に SubagentHandback の呼び出しがあるかを数える` → あり 1,196 件、無し 41 件（independent-reviewer・document-writer・fork）
- 前提: 今の _running は、finished が真で meta.json の mtime が起動・再開より後なら、終わったとみなす
  - path: plugins/spec-autopilot/hooks/stop.py:297-306
- 前提: 走っている agent が無いと wait_state は None を返し、decide は timer を見ずに完了の検査の不足で止める
  - path: plugins/spec-autopilot/hooks/stop.py:319-320、plugins/spec-autopilot/hooks/stop.py:365-371

## 作り方
この spec の ADR のとおり、scan が main の transcript を順に読むとき、agent ごとに「途中の完了の知らせが最後に届いたか」を持つ。host の task-notification（user の行の文字列と、queued_command の attachment）で、task-id がその agent で、summary に `is waiting on its own background work` があれば立て、ほかの summary の task-notification・その agent からの hand-back の行（`<agent-message from="<id>">`）・起動と再開で下ろす。_running は、meta.json の finished が真でも、この印が立っている agent は終わったとみなさず、今までどおり transcript の新しさで待ち中を決める。tool の結果の本文の中にある文言は数えない（scan が今も tool の結果の本文を起動の記録に数えないのと同じ）。文言が変わって拾えないときは、今と同じく終わったとみなす（止める側）。

## QA の方向性
| 要件 | 段 | 確かめ方 | 合格基準 |
|---|---|---|---|
| R1 | 手元で実物 | 途中の完了の形（meta.json に finished が真、main の transcript の最後の知らせが途中の完了の task-notification）の fixture で Stop hook を動かす単体テスト。生きている timer の有無と、知らせが user の行か queued_command かで分ける。tool の結果の本文に同じ文言を入れた fixture も足す | base で落ち、tip で通る。timer があれば放し、無ければ timer を求める文で止める。tool の結果の本文の文言では待ち中に数えない |
| R2 | 手元で実物 | 途中の完了の後に hand-back の行だけが届いた形、終わりの task-notification が届いた形、途中の完了の知らせが無く finished だけがある形の fixture で Stop hook を動かす単体テスト | どれも timer が生きていても止める（完了の検査の不足の文） |
| R3 | 手元で実物 | plugin.json の version を読み、回帰テストのコマンドを回す | version が 0.1.21 で、版数のテストが 0.1.20 を超えたことを見て、テストが通る |

## 制約
- 予算: 45 分
- 大きさ: M
- playbook: bug-fix
- 脅威: main の transcript に偽の途中の完了の知らせを書かれると、終わった agent を、transcript が 15 分書かれなくなるまで待ち中に数える（その間に放すのは生きている timer があるときだけ）。知らせを読みそこねると、今と同じく止める側に倒れる

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
