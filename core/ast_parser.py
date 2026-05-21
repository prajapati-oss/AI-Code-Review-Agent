
from __future__ import annotations

import ast
import textwrap


def _extract_source(source_code: str, node: ast.AST) -> str:
    """Return the dedented source lines for a given AST node."""
    lines = source_code.splitlines()
    start = node.lineno - 1
    end = getattr(node, "end_lineno", node.lineno)
    return textwrap.dedent("\n".join(lines[start:end]))


def parse_python_file(file_path: str) -> dict:
    """
    Parse a Python file and extract structural metadata.

    Returns:
        {
            "functions" : [{name, line_number, end_line_number, code, is_async}],
            "classes"   : [{name, line_number, end_line_number, methods}],
            "imports"   : [str],
            "error"     : str  # only present on SyntaxError
        }
    """
    with open(file_path, "r", encoding="utf-8") as fh:
        source = fh.read()

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return {
            "functions": [],
            "classes": [],
            "imports": [],
            "error": f"SyntaxError at line {e.lineno}: {e.msg}",
        }

    result: dict = {"functions": [], "classes": [], "imports": []}

    for node in ast.walk(tree):

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result["functions"].append({
                "name": node.name,
                "line_number": node.lineno,
                "end_line_number": getattr(node, "end_lineno", node.lineno),
                "code": _extract_source(source, node),
                "is_async": isinstance(node, ast.AsyncFunctionDef),
            })

        elif isinstance(node, ast.ClassDef):
            methods = [
                n.name for n in ast.walk(node)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            result["classes"].append({
                "name": node.name,
                "line_number": node.lineno,
                "end_line_number": getattr(node, "end_lineno", node.lineno),
                "methods": methods,
            })

        elif isinstance(node, ast.Import):
            for alias in node.names:
                result["imports"].append(alias.name)

        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                result["imports"].append(f"{module}.{alias.name}")

    
    seen: set = set()
    result["imports"] = [
        i for i in result["imports"]
        if not (i in seen or seen.add(i))
    ]

    return result
