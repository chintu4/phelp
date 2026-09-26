import ast
import importlib
import importlib.util
import inspect
from difflib import get_close_matches
from pathlib import Path


def _get_package_path(package_name):
    """Return the filesystem path of an installed package."""
    spec = importlib.util.find_spec(package_name)

    if spec is None:
        raise ImportError(f"Package '{package_name}' not found")

    if spec.submodule_search_locations:
        return Path(next(iter(spec.submodule_search_locations)))

    if spec.origin:
        return Path(spec.origin).parent

    raise ImportError(f"Could not determine location of '{package_name}'")


def _module_name(package_name, package_path, file_path):
    """Convert a Python file path into a module name."""
    relative = file_path.relative_to(package_path)

    if relative.name == "__init__.py":
        relative = relative.parent
    else:
        relative = relative.with_suffix("")

    if not relative.parts:
        return package_name

    return package_name + "." + ".".join(relative.parts)


def _scan_package(package_name):
    """
    Scan a package without importing all of its submodules.

    Returns:
        dict:
            {
                "name": {
                    "type": ...,
                    "module": ...,
                    "file": ...,
                    "line": ...
                }
            }
    """

    package_path = _get_package_path(package_name)

    symbols = {}

    for file_path in package_path.rglob("*.py"):

        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue

        module = _module_name(
            package_name,
            package_path,
            file_path,
        )

        for node in ast.walk(tree):

            if isinstance(node, ast.ClassDef):
                symbol_type = "class"

            elif isinstance(node, ast.AsyncFunctionDef):
                symbol_type = "async_function"

            elif isinstance(node, ast.FunctionDef):
                symbol_type = "function"

            else:
                continue

            # Keep the first definition we find
            if node.name not in symbols:
                symbols[node.name] = {
                    "name": node.name,
                    "type": symbol_type,
                    "package": package_name,
                    "module": module,
                    "file": str(file_path),
                    "line": node.lineno,
                    "end_line": getattr(
                        node,
                        "end_lineno",
                        node.lineno,
                    ),
                }

    return symbols


def locate(
    package_name,
    name,
    suggestions=True,
    n=5,
):
    """
    Locate a function or class inside a package.

    If the exact name isn't found, return similar symbols.
    """

    symbols = _scan_package(package_name)

    # Exact source definition
    if name in symbols:
        return {
            "found": True,
            "result": symbols[name],
            "suggestions": [],
        }

    # No exact match -> suggestions
    suggestion_list = []

    if suggestions:
        suggestion_list = _get_suggestions(
            name,
            symbols,
            n=n,
        )

    return {
        "found": False,
        "result": None,
        "suggestions": suggestion_list,
    }


def find_function(package_name, name):
    """Backward-compatible alias."""
    return locate(package_name, name)
