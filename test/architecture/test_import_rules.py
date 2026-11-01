import ast
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
PACKAGES = {p.name for p in (ROOT / "packages").iterdir() if p.is_dir() and p.name != "__pycache__"}
ALLOWED = {"contracts": set(), "storage": {"contracts"}, "integrations": {"contracts"}, "documents": {"contracts"}, "code_intelligence": {"contracts"}, "access": {"contracts"}, "knowledge": {"contracts", "storage"}, "retrieval": {"contracts", "storage", "access", "knowledge"}, "answering": {"contracts"}}
def imports(path: Path):
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module: yield node.module
        if isinstance(node, ast.Import):
            for name in node.names: yield name.name
def test_package_dependencies_follow_map():
    assert PACKAGES >= set(ALLOWED)
    for module, allowed in ALLOWED.items():
        for file in (ROOT / "packages" / module).rglob("*.py"):
            for imported in imports(file):
                root = imported.split(".")[0]
                if root == "apps": raise AssertionError(f"{file} imports app {imported}")
                if root == "packages":
                    target = imported.split(".")[1]
                    assert target in allowed or target == module, f"{file} imports {target}"