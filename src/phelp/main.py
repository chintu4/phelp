import ast
import importlib.util
from difflib import SequenceMatcher
from pathlib import Path


# ============================================================
# Package utilities
# ============================================================

def _get_package_path(package_name):
    """
    Find the filesystem location of an installed package.
    """

    spec = importlib.util.find_spec(package_name)

    if spec is None:
        raise ImportError(
            f"Package '{package_name}' is not installed."
        )

    if spec.submodule_search_locations:
        return Path(
            next(iter(spec.submodule_search_locations))
        )

    if spec.origin:
        return Path(spec.origin).parent

    raise ImportError(
        f"Could not determine location of '{package_name}'."
    )


def _module_name(package_name, package_path, file_path):
    """
    Convert a Python file path into a module name.

    Example:

        sklearn/ensemble/_forest.py

    becomes:

        sklearn.ensemble._forest
    """

    relative = file_path.relative_to(package_path)

    # package/__init__.py
    if relative.name == "__init__.py":
        relative = relative.parent

    # something.py -> something
    else:
        relative = relative.with_suffix("")

    if not relative.parts:
        return package_name

    return (
        package_name
        + "."
        + ".".join(relative.parts)
    )


# ============================================================
# Name normalization
# ============================================================

def _normalize_name(name):
    """
    Normalize a name for searching.

    Examples:

        RandomForest
        random_forest
        random forest
        RANDOMFOREST

    all become approximately:

        randomforest
    """

    return (
        name
        .lower()
        .replace("_", "")
        .replace("-", "")
        .replace(" ", "")
    )


# ============================================================
# Source scanning
# ============================================================

def _scan_package(package_name):
    """
    Scan all Python files inside a package.

    This does NOT import all submodules.

    Returns:

        {
            "RandomForestClassifier": {...},
            "LogisticRegression": {...},
            ...
        }
    """

    package_path = _get_package_path(package_name)

    symbols = {}

    for file_path in package_path.rglob("*.py"):

        # ----------------------------------------------------
        # Ignore obvious test directories
        # ----------------------------------------------------

        if any(
            part in {
                "tests",
                "test",
                "__pycache__",
            }
            for part in file_path.parts
        ):
            continue

        # ----------------------------------------------------
        # Read source
        # ----------------------------------------------------

        try:
            source = file_path.read_text(
                encoding="utf-8"
            )

            tree = ast.parse(source)

        except (
            OSError,
            UnicodeDecodeError,
            SyntaxError,
        ):
            continue

        module = _module_name(
            package_name,
            package_path,
            file_path,
        )

        # ----------------------------------------------------
        # Find definitions
        # ----------------------------------------------------

        for node in ast.walk(tree):

            if isinstance(node, ast.ClassDef):

                symbol_type = "class"

            elif isinstance(
                node,
                ast.AsyncFunctionDef,
            ):

                symbol_type = "async_function"

            elif isinstance(
                node,
                ast.FunctionDef,
            ):

                symbol_type = "function"

            else:
                continue

            # Don't overwrite the first definition.
            if node.name not in symbols:

                symbols[node.name] = {
                    "name": node.name,
                    "package": package_name,
                    "module": module,
                    "file": str(file_path),
                    "line": node.lineno,
                    "end_line": getattr(
                        node,
                        "end_lineno",
                        node.lineno,
                    ),
                    "type": symbol_type,
                }

    return symbols


# ============================================================
# Suggestion engine
# ============================================================

def _get_suggestions(
    query,
    symbols,
    n=5,
):
    """
    Find useful suggestions for a query.

    Examples:

        randomforest
            ->
        RandomForestClassifier
        RandomForestRegressor
    """

    query_normalized = _normalize_name(query)

    results = []

    for symbol_name, info in symbols.items():

        symbol_normalized = _normalize_name(
            symbol_name
        )

        score = 0

        # ----------------------------------------------------
        # Exact normalized match
        # ----------------------------------------------------

        if symbol_normalized == query_normalized:

            score = 100

        # ----------------------------------------------------
        # Query occurs inside symbol
        # ----------------------------------------------------

        elif query_normalized in symbol_normalized:

            score = 90

        # ----------------------------------------------------
        # Symbol occurs inside query
        # ----------------------------------------------------

        elif symbol_normalized in query_normalized:

            score = 85

        # ----------------------------------------------------
        # Same prefix
        # ----------------------------------------------------

        elif (
            len(query_normalized) >= 3
            and symbol_normalized.startswith(
                query_normalized[:3]
            )
        ):

            score = 75

        # ----------------------------------------------------
        # Fuzzy similarity
        # ----------------------------------------------------

        else:

            similarity = SequenceMatcher(
                None,
                query_normalized,
                symbol_normalized,
            ).ratio()

            score = similarity * 70

        # ----------------------------------------------------
        # Only keep reasonable matches
        # ----------------------------------------------------

        if score >= 45:

            results.append(
                (score, info)
            )

    # Highest score first
    results.sort(
        key=lambda item: (
            -item[0],
            item[1]["name"],
        )
    )

    return [
        info
        for _, info in results[:n]
    ]


# ============================================================
# Main API
# ============================================================

def locate(
    package_name,
    name,
    suggestions=True,
    n=5,
):
    """
    Locate a function or class inside a Python package.

    Parameters
    ----------
    package_name : str
        Package to search.

        Example:
            "sklearn"

    name : str
        Function/class name.

        Example:
            "LogisticRegression"

    suggestions : bool
        Return similar names when exact match
        is not found.

    n : int
        Maximum number of suggestions.

    Examples
    --------

    locate(
        "sklearn",
        "LogisticRegression"
    )

    locate(
        "sklearn",
        "randomforest"
    )

    locate(
        "sklearn",
        "LogisticRegresion"
    )
    """

    # --------------------------------------------------------
    # Scan package
    # --------------------------------------------------------

    symbols = _scan_package(
        package_name
    )

    # --------------------------------------------------------
    # Exact match
    # --------------------------------------------------------

    if name in symbols:

        return {
            "found": True,
            "result": symbols[name],
            "suggestions": [],
        }

    # --------------------------------------------------------
    # Case / underscore-insensitive exact match
    # --------------------------------------------------------

    normalized_query = _normalize_name(name)

    for symbol_name, info in symbols.items():

        if (
            _normalize_name(symbol_name)
            == normalized_query
        ):

            return {
                "found": True,
                "result": info,
                "suggestions": [],
            }

    # --------------------------------------------------------
    # Suggestions
    # --------------------------------------------------------

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


# ============================================================
# Backwards compatibility
# ============================================================

def find_function(
    package_name,
    name,
):
    """
    Backwards-compatible alias for locate().

    Deprecated:
        Use locate() instead.
    """

    return locate(
        package_name,
        name,
    )
