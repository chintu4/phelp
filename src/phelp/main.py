import ast
import importlib
import importlib.util
import inspect
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
    """Convert a Python file path into its module name."""
    relative = file_path.relative_to(package_path)

    if relative.name == "__init__.py":
        relative = relative.parent
    else:
        relative = relative.with_suffix("")

    parts = list(relative.parts)

    if parts:
        return package_name + "." + ".".join(parts)

    return package_name


def _find_in_source(file_path, name):
    """Find a function/class definition in a Python source file."""
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (OSError, UnicodeDecodeError, SyntaxError):
        return None

    for node in ast.walk(tree):
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
                ast.ClassDef,
            ),
        ):
            if node.name == name:
                if isinstance(node, ast.ClassDef):
                    object_type = "class"
                elif isinstance(node, ast.AsyncFunctionDef):
                    object_type = "async_function"
                else:
                    object_type = "function"

                return {
                    "type": object_type,
                    "line": node.lineno,
                    "end_line": getattr(node, "end_lineno", node.lineno),
                }

    return None


def locate(package_name, name):
    """
    Locate a function, class, or async function inside a Python package.

    Example:
        locate("sklearn", "train_test_split")
        locate("sklearn", "LogisticRegression")
    """

    package_path = _get_package_path(package_name)

    # ---------------------------------------------------------
    # 1. Search Python source files
    # ---------------------------------------------------------

    for file_path in package_path.rglob("*.py"):

        result = _find_in_source(file_path, name)

        if result:
            module = _module_name(
                package_name,
                package_path,
                file_path,
            )

            return {
                "name": name,
                "package": package_name,
                "module": module,
                "file": str(file_path),
                **result,
            }

    # ---------------------------------------------------------
    # 2. If not found, try imported/public API
    # ---------------------------------------------------------

    try:
        package = importlib.import_module(package_name)
    except Exception:
        return None

    if hasattr(package, name):
        obj = getattr(package, name)

        try:
            source_file = inspect.getsourcefile(obj)
            source_lines = inspect.getsourcelines(obj)
            line = source_lines[1]
        except (TypeError, OSError):
            source_file = None
            line = None

        return {
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

    return None


def find_function(package_name, name):
    """
    Backwards-compatible alias for locate().

    Example:
        find_function("sklearn", "train_test_split")
    """
    return locate(package_name, name)
