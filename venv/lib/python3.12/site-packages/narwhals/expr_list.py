from __future__ import annotations

from typing import TYPE_CHECKING, Generic, TypeVar

if TYPE_CHECKING:
    from narwhals.expr import Expr

ExprT = TypeVar("ExprT", bound="Expr")


class ExprListNamespace(Generic[ExprT]):
    def __init__(self, expr: ExprT) -> None:
        self._expr = expr

    def len(self) -> ExprT:
        """Return the number of elements in each list.

        Null values count towards the total.

        Returns:
            A new expression.

        Examples:
            >>> import polars as pl
            >>> import narwhals as nw
            >>> df_native = pl.DataFrame({"a": [[1, 2], [3, 4, None], None, []]})
            >>> df = nw.from_native(df_native)
            >>> df.with_columns(a_len=nw.col("a").list.len())
            ┌────────────────────────┐
            |   Narwhals DataFrame   |
            |------------------------|
            |shape: (4, 2)           |
            |┌──────────────┬───────┐|
            |│ a            ┆ a_len │|
            |│ ---          ┆ ---   │|
            |│ list[i64]    ┆ u32   │|
            |╞══════════════╪═══════╡|
            |│ [1, 2]       ┆ 2     │|
            |│ [3, 4, null] ┆ 3     │|
            |│ null         ┆ null  │|
            |│ []           ┆ 0     │|
            |└──────────────┴───────┘|
            └────────────────────────┘
        """
        return self._expr._with_elementwise(
            lambda plx: self._expr._to_compliant_expr(plx).list.len()
        )
