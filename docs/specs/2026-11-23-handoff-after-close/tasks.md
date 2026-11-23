# タスク

<!-- `- [x] T1: <やること> [R1, R2]` の形。終えたら [x]。すべての要件をどれかのタスクが受け持つ -->

- [x] T1: Agent の PreToolUse hook（hooks/agent_gate.py）と hooks.json の登録・答えの無い終わりの deny、test_agent_gate.py [R1, R2, R3, R8]
- [x] T2: handoff の閉じた側の道で、閉じた tip と今の HEAD のファイルの中身を比べ、統合先が変えたファイルを除いて拒む [R4, R5, R6]
  - メモ: R4 の統合先が変えたファイルの差分の始点は、閉じた tip とそのブランチの merge-base にした（閉じた tip と今の HEAD の merge-base では、統合先の merge の後に始点が閉じた tip になり、R5 の merge を通せない）。終点と祖先の条件は R4 のまま
- [x] T3: commands/autopilot.md の handoff の項、overnight.py の冒頭の使い方と docstring、README の hook の表を直す [R7]
