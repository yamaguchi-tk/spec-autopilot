"""qa.md の pass の証拠の欄を、テストの並びに区切る（autopilot.py の行の予算のため分けた。EVIDENCE_SEP は autopilot.py にある）。"""


def items(root, tests, sep):
    """区切りの候補の後ろの `::` の前が空か repo のファイルのときだけ区切る（名前の中の ・、 は前の名前に戻す）。"""
    out, start = [], 0
    for m in sep.finditer(tests):
        head = tests[m.end():].split("::", 1)[0].strip().strip("`")
        try:
            if head and not (root / head).is_file():
                continue
        except OSError:
            continue
        out.append(tests[start:m.start()])
        start = m.end()
    return out + [tests[start:]]
