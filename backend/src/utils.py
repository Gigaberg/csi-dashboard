"""
src.utils
=========
Miscellaneous utility helpers used across the CSI backend.

Contents
--------
sanitize(obj)   — recursively replace NaN / ±Inf floats before JSON serialization
"""


def sanitize(obj):
    """
    Recursively walk a JSON-serializable structure and replace ``NaN`` /
    ``±Infinity`` float values with ``0.0`` so that ``json.dumps`` (and
    FastAPI's built-in serializer) never raises ``ValueError``.

    Parameters
    ----------
    obj:
        Any Python value that will be serialized to JSON.  Supported types:
        ``float``, ``int``, ``str``, ``bool``, ``None``, ``dict``, ``list``.

    Returns
    -------
    A deep copy of *obj* with all non-finite floats replaced by ``0.0``.

    Examples
    --------
    >>> from src.utils import sanitize
    >>> sanitize({"a": float("nan"), "b": [float("inf"), 1.0]})
    {'a': 0.0, 'b': [0.0, 1.0]}
    """
    if isinstance(obj, float):
        if obj != obj or obj == float("inf") or obj == float("-inf"):
            return 0.0
        return obj
    if isinstance(obj, dict):
        return {k: sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize(v) for v in obj]
    return obj
