import ast
import importlib.util
from pathlib import Path


def find_function(package_name, function_name):
    # Find where the package is installed
    spec = importlib.util.find_spec(package_name)

    if spec is None:
        raise ImportError(f"Package '{package_name}' not found")

    # Get package directory
    if spec.submodule_search_locations:
        package_path = Path(list(spec.submodule_search_locations)[0])
    else:
        package_path = Path(spec.origin).parent

    # Search all .py files
    for file in package_path.rglob("*.py"):

        try:
            source = file.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue

        for node in ast.walk(tree):

            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == function_name:

                    relative_path = file.relative_to(package_path)

                    return {
                        "package": package_name,
                        "function": function_name,
                        "module": (
                            package_name
                            + "."
                            + str(relative_path.with_suffix(""))
                            .replace("/", ".")
                        ),
                        "file": str(file),
                        "line": node.lineno,
                    }

    return None
