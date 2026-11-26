# ADR: 手元の道具の入れ方は、CLAUDE.md に venv の中で入れると書く

## 状況
PR 49 で、CLAUDE.md は「手元に道具を入れるときは、workflow の `pip install` の行を回す」と書いた。PEP 668 で守られた手元の python3（Homebrew の python など）では、その行は venv の外で `externally-managed-environment` で拒まれる。評価役が low として挙げた。同じ PR で、test_qa_evidence.py の 2 つのコメントに TASK が「2 乗」と残った。

## 決定
CLAUDE.md の行に、repo の root に `.venv` を作って有効にし、その中で workflow の `pip install` の行とテストのコマンドを回すと書き、.gitignore に `.venv/` を足す。版の数字は今までどおり workflow の 1 か所にだけ置く。コメントは今の TASK に合わせて書き直す。

## 退けた案
- `--break-system-packages` を付けて回すと書く: 手元の python の管理を壊しうる
- `pip install --user` と書く: PEP 668 の環境では `--user` も拒まれる
