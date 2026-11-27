# タスク

<!-- `- [ ] T1: <やること> [R1, R2]` の形。終えたら [x]。すべての要件をどれかのタスクが受け持つ -->

- [x] T1: cmd_done の大きさの判定を size_note.py の関数に移し、cmd_done と cmd_check（stage が pr のとき）から呼ぶ。commands/autopilot.md:102・112 と autopilot.py:582 のコメントの NOTE の出どころを直し、test_size.py に check --stage pr の L・申告 L・M の場合のテストを足す [R1]
- [x] T2: cmd_check の `--stage pr` で、check() が errors を返したときか spec.md が無いときは size_note を呼ばず、base と同じ ERROR だけを出す（評価役の low: spec.md の無い spec で Traceback）。その場合のテストを足す [R1]
