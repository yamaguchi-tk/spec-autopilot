# 実装役の起動は入口で止め、閉じた後のコードの変更はファイルの中身で見分ける

- 状態: 採用
- 日付: 2026-11-23

## 背景
`overnight.py handoff` は、dispatch が開いている間だけ実装役の起動の記録と増分を確かめる。閉じた後に HEAD が動いたときは、マージの前の rebase を通すために何も見ない。このため、閉じた後に dispatch を打たずに起動した実装役と、閉じた後に main が書いたコードを見分けない（Issue #2）。過去に試した 2 つの形（閉じた tip の上の commit を履歴で数える・閉じた後の起動をセッションで数える）は、amend・adopt・lineup の形で抜けるか、誤って拒んだ。

## 決定
- dispatch を打たない起動は、事後に数えず、起動の入口で止める。Agent の PreToolUse hook が、実装役（`autopilot-implementer` で始まる agent）の起動のときに、prompt に書かれた spec の state.json を読み、開いた dispatch が無いか、dispatch の agent の名前と違えば deny する。判定は spec ごとの state だけで決め、セッションを見ないので、adopt・lineup の別の spec で誤って拒まない。hook が答えを出さずに落ちたときは、hooks.json の command が deny を出す（落ちた hook が起動を通さないため）
- 閉じた後に main が書いたコードは、commit の数え方ではなく、ファイルの中身で見分ける。閉じた tip と今の HEAD で中身が違う spec の外のファイルから、統合先（手元と remote のブランチのうち、今のブランチ・その upstream・同じ名前の remote のブランチ・閉じた tip か今の HEAD を含むブランチを除いたもの）が分岐の後に変えたファイルを除き、残れば拒む。この spec 自身の変更を持つブランチを統合先に数えると、その変更のファイルへの main の書き込みを見落とすので除く。rebase・統合先の merge は統合先が変えたファイルしか動かさず、spec のファイルだけの amend は spec の外を動かさないので、どれも拒まない

## 退けた案
- 閉じた後の commit を履歴で数える: rebase で commit が作り直され、amend で数が変わるので、抜けるか誤って拒む（過去の試みで分かった）
- 閉じた後の起動をセッションで数える: adopt で別のセッションに移り、lineup で同じセッションが別の spec を進めるので、誤って拒む（過去の試みで分かった）
- main の `git commit` を Bash の PreToolUse で止める: shell のコマンドを解析することになり、`git -C`・alias・スクリプトの中の commit で抜ける

## 結果
- 統合先も変えたファイルに main が書いたコードは見分けない（rebase の衝突の解消と区別できない）
- この spec の変更を載せ替えた写しを持つ、ほかの名前のブランチがあると、そのファイルへの main の書き込みを見分けない
- 実装役の prompt に spec のディレクトリを書かないと起動できなくなる（/autopilot の手順は既に書いている）
