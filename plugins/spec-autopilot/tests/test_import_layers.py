"""scripts の import の向き（deploy.py・stages.py が autopilot.py に依らない下の層になっている）を、ast で確かめる。
輪を importlib・変数の `__import__`・`sys.modules` に替えて道具に見えなくする形も落とす。"""
import ast
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
MODULES = {p.stem for p in SCRIPTS.glob("*.py")}
BELOW = ("deploy.py", "stages.py")


def tree(name):
    return ast.parse((SCRIPTS / name).read_text(encoding="utf-8"))


def imported(t):
    """関数の中の import と、名前が文字列の `__import__("x")` を含む、import する scripts のモジュール。"""
    out = set()
    for n in ast.walk(t):
        if isinstance(n, ast.Import):
            out |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module and not n.level:
            out.add(n.module.split(".")[0])
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "__import__" and n.args:
            a = n.args[0]
            out.add(a.value.split(".")[0] if isinstance(a, ast.Constant) and isinstance(a.value, str) else "<dynamic>")
    return out


def in_cycle():
    """import の輪（2 つ以上のモジュールが互いに届く）に入る scripts のモジュール。"""
    graph = {m: imported(tree(f"{m}.py")) & MODULES - {m} for m in MODULES}
    reach = {}
    for m in graph:
        seen, todo = set(), list(graph[m])
        while todo:
            x = todo.pop()
            if x not in seen:
                seen.add(x)
                todo += graph[x]
        reach[m] = seen
    return {m for m in graph if any(m in reach[o] for o in reach[m])}


def test_deploy_and_stages_do_not_import_autopilot_even_inside_functions():
    for name in BELOW:
        t = tree(name)
        assert "autopilot" not in imported(t), name
        assert not {"importlib", "<dynamic>"} & imported(t), name


def test_deploy_and_stages_have_no_autopilot_reference_or_sys_modules():
    for name in BELOW:
        for n in ast.walk(tree(name)):
            assert not (isinstance(n, ast.Name) and n.id == "autopilot"), f"{name}:{n.lineno}"
            assert not (isinstance(n, ast.Attribute) and n.attr == "modules" and isinstance(n.value, ast.Name) and n.value.id == "sys"), f"{name}:{n.lineno}"


def test_stages_functions_take_no_module_and_nobody_passes_one():
    for n in ast.walk(tree("stages.py")):
        if isinstance(n, ast.FunctionDef):
            assert not {a.arg for a in n.args.args} & {"autopilot", "ap"}, f"stages.{n.name}"
    for name in ("deploy.py", "autopilot.py"):
        for n in ast.walk(tree(name)):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name) and n.func.value.id == "stages":
                for a in n.args:
                    assert not (isinstance(a, ast.Name) and a.id in ("autopilot", "ap")), f"{name}:{n.lineno}"
                    assert "modules" not in ast.dump(a), f"{name}:{n.lineno}"


def test_stages_imports_only_carry_among_scripts():
    assert imported(tree("stages.py")) & MODULES == {"carry"}


def test_deploy_preflight_and_stages_are_outside_the_import_cycle():
    assert not {"deploy", "preflight", "stages"} & in_cycle()


def test_autopilot_uses_stages_for_the_moved_helpers():
    names = {"section", "classify", "requirement_lines", "requirements", "repo_root", "git_lines", "stated_size"}
    top = {"REQ", "COMMENT", "COMMENT_BLOCK", "BUDGET", "QA_ROW", "TEST_PATH", "NOT_CODE", "MAX_REWORKS", "SIZE_LINE", "SIZE_ANY"}
    in_stages = tree("stages.py").body
    assert names <= {n.name for n in in_stages if isinstance(n, ast.FunctionDef)}
    assert top <= {t.id for n in in_stages if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)}
    for n in tree("autopilot.py").body:  # 移した名前を autopilot.py の中で定義し直さない
        defined = {n.name} if isinstance(n, ast.FunctionDef) else {t.id for t in getattr(n, "targets", []) if isinstance(t, ast.Name)}
        assert not defined & (names | top), defined


def test_diff_size_calls_a_top_level_grep_instead_of_a_nested_function():
    t = tree("autopilot.py")
    diff_size = next(n for n in t.body if isinstance(n, ast.FunctionDef) and n.name == "diff_size")
    assert not [n for n in ast.walk(diff_size) if isinstance(n, ast.FunctionDef) and n is not diff_size]
    assert any(isinstance(n, ast.FunctionDef) and n.name == "grep" for n in t.body)


def test_runlog_does_not_import_autopilot_even_inside_functions():
    t = tree("runlog.py")
    assert "autopilot" not in imported(t)
    assert not {"importlib", "<dynamic>"} & imported(t)
    assert imported(t) & MODULES <= {"stages"}


def test_runlog_has_no_autopilot_reference_or_sys_modules():
    for n in ast.walk(tree("runlog.py")):
        assert not (isinstance(n, ast.Name) and n.id in ("autopilot", "ap")), f"runlog.py:{n.lineno}"
        assert not (isinstance(n, ast.Attribute) and n.attr == "modules" and isinstance(n.value, ast.Name) and n.value.id == "sys"), f"runlog.py:{n.lineno}"


def test_import_cycle_is_exactly_the_five_modules_without_runlog():
    assert in_cycle() == {"autopilot", "goal", "light", "lineup", "overnight"}


def test_stages_repo_root_and_git_lines_call_git_through_one_function():
    funcs = {n.name: n for n in tree("stages.py").body if isinstance(n, ast.FunctionDef)}

    def calls(f, attr=None):
        return [n for n in ast.walk(f) if isinstance(n, ast.Call) and (
            attr is None and isinstance(n.func, ast.Name) or attr and isinstance(n.func, ast.Attribute) and n.func.attr == attr)]

    assert calls(funcs["run_git"], "run")
    for name in ("repo_root", "git_lines"):
        assert not calls(funcs[name], "run"), name
        assert "run_git" in {c.func.id for c in calls(funcs[name])}, name


def module_passes():
    """autopilot.py の `sys.modules[__name__]` の出る場所の数と、それを引数に渡している `__import__("x")` の x。"""
    t = tree("autopilot.py")
    refs = [n for n in ast.walk(t) if isinstance(n, ast.Subscript) and "modules" in ast.dump(n.value) and "__name__" in ast.dump(n.slice)]
    passed = set()
    for n in ast.walk(t):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Call):
            inner = n.func.value
            if isinstance(inner.func, ast.Name) and inner.func.id == "__import__" and any("modules" in ast.dump(a) for a in n.args):
                passed.add(inner.args[0].value)
    return len(refs), passed


def test_evidence_and_size_note_are_folded_into_autopilot():
    assert not {"evidence", "size_note"} & MODULES
    assert not {"evidence", "size_note"} & imported(tree("autopilot.py"))
    assert not (SCRIPTS / "evidence.py").exists() and not (SCRIPTS / "size_note.py").exists()
    names = {n.name for n in tree("autopilot.py").body if isinstance(n, ast.FunctionDef)}
    assert {"evidence_items", "size_notes"} <= names


def test_autopilot_imports_fifteen_scripts_modules():
    assert len(imported(tree("autopilot.py")) & MODULES) == 15


def test_autopilot_passes_sys_modules_only_to_premises_and_rootcause():
    count, passed = module_passes()
    assert count == 2
    assert passed == {"premises", "rootcause"}
