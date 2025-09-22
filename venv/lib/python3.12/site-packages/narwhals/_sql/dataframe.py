from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from narwhals._compliant.dataframe import CompliantLazyFrame
from narwhals._compliant.typing import CompliantExprT_contra, NativeExprT, NativeFrameT
from narwhals._translate import ToNarwhalsT_co

if TYPE_CHECKING:
    from typing_extensions import Self, TypeAlias

    from narwhals._compliant.window import WindowInputs
    from narwhals._sql.expr import SQLExpr

    Incomplete: TypeAlias = Any


class SQLLazyFrame(
    CompliantLazyFrame[CompliantExprT_contra, NativeFrameT, ToNarwhalsT_co],
    Protocol[CompliantExprT_contra, NativeFrameT, ToNarwhalsT_co],
):
    def _evaluate_window_expr(
        self,
        expr: SQLExpr[Self, NativeExprT],
        /,
        window_inputs: WindowInputs[NativeExprT],
    ) -> NativeExprT:
        result = expr.window_function(self, window_inputs)
        assert len(result) == 1  # debug assertion  # noqa: S101
        return result[0]
