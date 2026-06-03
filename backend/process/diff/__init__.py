"""Three-layer hybrid bill diff (structural → line → word).

Public surface is intentionally small: callers should depend on
``compute_bill_difference`` and ``PARSER_VERSION`` only. Helpers in
``pipeline``, ``structural``, ``line``, and ``word`` are implementation
details and may change between parser versions.
"""

from backend.process.diff.pipeline import PARSER_VERSION, compute_bill_difference

__all__ = ["PARSER_VERSION", "compute_bill_difference"]
