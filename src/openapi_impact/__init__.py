"""Public package interface for OpenAPI Impact."""

from .compare import compare_specs
from .models import Change, ComparisonResult, Severity

__all__ = ["Change", "ComparisonResult", "Severity", "compare_specs"]
__version__ = "1.1.0"
