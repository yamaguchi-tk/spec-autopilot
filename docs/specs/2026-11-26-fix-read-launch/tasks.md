# タスク

- [x] T1: 再現の手順を、落ちる自動テストにして先に commit する [R1, R2, R3]
  - メモ: base で落ちることを確かめてから commit する。U+2028 などはエスケープで書く
- [x] T2: 根本の原因を直す [R1, R2, R3]
  - メモ: 否定された仮説から足したコードは戻す
- [x] T3: 同じ種類の箇所を洗い出し、同じ直しを当てる（当てないなら理由をメモに書く） [R1, R2, R4]
  - メモ: scripts と hooks の splitlines を全部見た。subagent の transcript を読むのは read_launch と advisor_approval.launches の 2 か所だけ。JSONL を読む awaits.jsonl（overnight.py の _awaits）も同じ型で、独立レビューの high（読めない行を飛ばすので、デプロイの失敗を数え漏らす）。人に確かめて範囲に入れ、同じ直しを当てた（R4）。2 巡目の high（切れた行が次の記録を巻き込んで飛ぶ）は再設計にし、人が「源で止める」を選んだ（書き手が改行を足し、_awaits は読めない行で止める）。ほかの splitlines は JSONL を読まない（spec・qa・tasks の markdown、git の出力、hooks/stop.py の ps の出力〔割れると ps が読めず止める側に倒れる〕、hooks/agent_gate.py の Agent の prompt、autopilot.py の .git/info/exclude）ので、この spec では当てない
