from __future__ import annotations

from typing import TYPE_CHECKING

from narwhals._compliant import LazyExprNamespace
from narwhals._compliant.any_namespace import ListNamespace
from narwhals._duckdb.utils import F

if TYPE_CHECKING:
    from narwhals._duckdb.expr import DuckDBExpr


class DuckDBExprListNamespace(
    LazyExprNamespace["DuckDBExpr"], ListNamespace["DuckDBExpr"]
):
    def len(self) -> DuckDBExpr:
        return self.compliant._with_elementwise(lambda expr: F("len", expr))
