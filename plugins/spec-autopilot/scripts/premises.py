"""spec の「## 前提」の lint（autopilot.py の行の予算のため分けた。文法の定数は autopilot.py にある）。"""
import os


def check(ap, root, start, text, commit=True):
    """前提の行を許可リストで読み、ERROR の一覧を返す。確かめ方は直前の `- 前提:` に結びつけ、path は並べたものを全部 init の時点（start）の commit で確かめ、ファイルでないもの（ディレクトリ）も ERROR にする。"""
    rows, bad = ap.classify(text, ap.PREMISE_KINDS)
    errors = [f"前提の行の形が読めない（`- 目的に届く:`・`- 運用:`・`- 普通のやり方:`・`- 過去:` は値か `なし（<理由>）`、`- 前提: <言い切り>` か `- 前提: なし（<理由>）`。なしで始める行は `なし（<理由>）` だけで、理由の中に `）` は書けない。"
              f"確かめ方は `- 前提:` の下に字下げして `  - path: <path>:<行>（<補足>）、…`・`  - コマンド: `<cmd>` → <結果>`・`  - URL: <url>`・`  - 未確認: <理由>` のどれか。補足は `  - メモ:`）: {line}"
              for line in bad]
    kinds = {"前提" if k == "前提なし" else k for k, _ in rows}
    errors += [f"「## 前提」に `- {k}:` の行を書く（当たらないなら `なし（<理由>）`）" for k in ap.PREMISE_ROWS if k not in kinds]
    claim, checked = None, False
    for kind, m in rows + [("終わり", None)]:
        if kind in ap.HOW_ROWS:
            if claim is None:
                errors.append(f"確かめ方の行が `- 前提:` の下に無い（`- 前提: <言い切り>` の下に字下げして書く）: {m.group(0).strip()}")
            checked = True
        elif kind != "メモ":
            if claim is not None and not checked:
                errors.append(f"`- 前提:` に確かめ方の行が無い（下に `  - path:`・`  - コマンド:`・`  - URL:`・`  - 未確認:` を書く）: {claim}")
            claim, checked = (m.group(0).strip(), False) if kind == "前提" else (None, False)
        if kind != "path" or not commit:  # commit が偽なら path の突き合わせを外す（依る spec の承認）
            continue
        for p in ap.HOW_PATH.finditer(m.group("how")):
            path = os.path.normpath(p.group("p"))
            if not start:
                errors.append(f"確かめ方の {path} は、init の時点の commit が無い（新しく作る repo）ので path では確かめられない。コマンドか未確認で書く")
                continue
            try:
                if not ap.at_start(root, start, "cat-file", "-e", f"{start}:{path}"):
                    errors.append(f"`- 前提:` の確かめ方の {path} が init の時点の commit に無い")
                elif ap.at_start(root, start, "cat-file", "-e", f"{start}:{path}/"):  # tree なら、末尾の / でも引ける
                    errors.append(f"`- 前提:` の確かめ方の {path} がファイルでない（読んだファイルと行を書く）")
            except (OSError, RuntimeError, ValueError) as e:
                errors.append(f"`- 前提:` の確かめ方の {path} を確かめられない（git が失敗した: {e}）")
    return errors
