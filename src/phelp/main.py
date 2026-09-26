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
    cutoff=0.6,
):
    """
    Locate a function, class, or async function.

    If the exact name is not found, optionally return
    similar names as suggestions.

    Example:

        locate("sklearn", "LogisticRegression")

        locate("sklearn", "LogisticRegresion")

    Args:
        package_name: Package to search.
        name: Function/class name to find.
        suggestions: Whether to provide suggestions.
        n: Maximum number of suggestions.
        cutoff: Similarity threshold from 0 to 1.
    """

    symbols = _scan_package(package_name)

    # ---------------------------------------------------------
    # Exact match
    # ---------------------------------------------------------

    if name in symbols:
        return {
            "found": True,
            "result": symbols[name],
            "suggestions": [],
        }

    # ---------------------------------------------------------
    # Try public package API
    # ---------------------------------------------------------

    try:
        package = importlib.import_module(package_name)

        if hasattr(package, name):

            obj = getattr(package, name)

            try:
                source_file = inspect.getsourcefile(obj)
                source_lines = inspect.getsourcelines(obj)
                line = source_lines[1]
            except (TypeError, OSError):
                source_file = None
                line = None

            result = {
                "name": name,
                "package": package_name,
                "module": getattr(obj, "__module__", None),
                "file": source_file,
                "line": line,
                "type": (
                    "class"
                    if inspect.isclass(obj)
                    else "function"
                    if inspect.isfunction(obj)
                    else type(obj).__name__
                ),
            }

            return {
                "found": True,
                "result": result,
                "suggestions": [],
            }

    except Exception:
        pass

    # ---------------------------------------------------------
    # No exact match → suggestions
    # ---------------------------------------------------------

    suggestions_list = []

    if suggestions:
        matches = get_close_matches(
            name,
            symbols.keys(),
            n=n,
            cutoff=cutoff,
        )

        for match in matches:
            suggestions_list.append(symbols[match])

    return {
        "found": False,
        "result": None,
        "suggestions": suggestions_list,
    }


def find_function(package_name, name):
    """Backward-compatible alias."""
    return locate(package_name, name)
