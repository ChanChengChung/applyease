"""Architecture guardrails for the API -> CRUD/service boundary."""

import ast
from pathlib import Path


API_DIR = Path(__file__).parents[1] / "app" / "api" / "v1"
DB_METHODS = {
    "get",
    "query",
    "add",
    "add_all",
    "delete",
    "commit",
    "flush",
    "refresh",
    "rollback",
    "scalar",
    "scalars",
    "execute",
}


def test_api_modules_do_not_import_orm_models_or_query_the_database_directly():
    violations: list[str] = []

    for path in API_DIR.glob("*.py"):
        tree = ast.parse(path.read_text())

        for node in ast.walk(tree):

            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("app.models"):
                violations.append(f"{path.name}:{node.lineno} imports {node.module}")

            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                owner = node.func.value

                if (
                    isinstance(owner, ast.Name)
                    and owner.id == "db"
                    and node.func.attr in DB_METHODS
                ):
                    violations.append(f"{path.name}:{node.lineno} calls db.{node.func.attr}()")
    assert not violations, "API layer bypasses CRUD boundary:\n" + "\n".join(violations)
