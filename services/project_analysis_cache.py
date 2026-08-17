from pathlib import Path
from functools import lru_cache


def _file_signature(file_path):
    """
    Return a lightweight signature used to detect file changes.
    """

    path = Path(file_path)

    try:
        stat = path.stat()
    except OSError:
        return None

    return (
        str(path.resolve()),
        stat.st_mtime_ns,
        stat.st_size,
    )


@lru_cache(maxsize=256)
def get_cached_file_content(
    file_path,
    signature,
):
    """
    Cache raw Python source content.

    The signature invalidates the cache automatically when
    the file changes.
    """

    path = Path(file_path)

    try:
        return path.read_text(
            encoding="utf-8",
            errors="ignore",
        )
    except OSError:
        return None


def get_file_content(file_path):
    """
    Return cached file content.
    """

    signature = _file_signature(file_path)

    if signature is None:
        return None

    return get_cached_file_content(
        str(Path(file_path).resolve()),
        signature,
    )


@lru_cache(maxsize=256)
def get_cached_source_tree(
    file_path,
    signature,
):
    """
    Parse and cache a Python file's AST.
    """

    import ast

    content = get_cached_file_content(
        file_path,
        signature,
    )

    if content is None:
        return None

    try:
        return ast.parse(content)
    except SyntaxError:
        return None


def get_source_tree(file_path):
    """
    Return a cached AST for a Python file.
    """

    signature = _file_signature(file_path)

    if signature is None:
        return None

    normalized_path = str(
        Path(file_path).resolve()
    )

    return get_cached_source_tree(
        normalized_path,
        signature,
    )


def clear_analysis_cache():
    """
    Clear all cached project-analysis data.
    """

    get_cached_file_content.cache_clear()
    get_cached_source_tree.cache_clear()


def get_analysis_cache_info():
    """
    Return cache statistics.
    """

    return {
        "file_content": get_cached_file_content.cache_info(),
        "source_tree": get_cached_source_tree.cache_info(),
    }