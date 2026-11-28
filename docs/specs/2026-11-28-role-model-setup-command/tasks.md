# タスク

<!-- `- [ ] T1: <やること> [R1, R2]` の形。終えたら [x]。すべての要件をどれかのタスクが受け持つ -->
- [x] T1: 段の表に照合の役と検証の fable-high を足し、定義 2 つを足す [R1, R2, R3, R4]
- [x] T2: commands/setup.md と README を 5 つの役に広げる [R5]
  - メモ: bf79965 の上で再確認。setup.md・README・test（test_setup_command_writes_every_role_with_a_flag_ladder_setup_takes_and_resets_every_role ほか）は ladder.py show の 5 つの役・setup の旗・reset と合い、main 側に setup.md・README・ladder.py の変更は無く直しは不要。回帰テスト 663 件 pass。
