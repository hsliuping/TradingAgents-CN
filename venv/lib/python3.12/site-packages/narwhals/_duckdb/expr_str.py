from __future__ import annotations

from typing import TYPE_CHECKING

from narwhals._compliant import LazyExprNamespace
from narwhals._compliant.any_namespace import StringNamespace
from narwhals._duckdb.utils import F, lit, when
from narwhals._utils import not_implemented

if TYPE_CHECKING:
    from duckdb import Expression

    from narwhals._duckdb.expr import DuckDBExpr


class DuckDBExprStringNamespace(
    LazyExprNamespace["DuckDBExpr"], StringNamespace["DuckDBExpr"]
):
    def starts_with(self, prefix: str) -> DuckDBExpr:
        return self.compliant._with_elementwise(
            lambda expr: F("starts_with", expr, lit(prefix))
        )

    def ends_with(self, suffix: str) -> DuckDBExpr:
        return self.compliant._with_elementwise(
            lambda expr: F("ends_with", expr, lit(suffix))
        )

    def contains(self, pattern: str, *, literal: bool) -> DuckDBExpr:
        def func(expr: Expression) -> Expression:
            if literal:
                return F("contains", expr, lit(pattern))
            return F("regexp_matches", expr, lit(pattern))

        return self.compliant._with_elementwise(func)

    def slice(self, offset: int, length: int | None) -> DuckDBExpr:
        def func(expr: Expression) -> Expression:
            offset_lit = lit(offset)
            return F(
                "array_slice",
                expr,
                lit(offset + 1)
                if offset >= 0
                else F("length", expr) + offset_lit + lit(1),
                F("length", expr) if length is None else lit(length) + offset_lit,
            )

        return self.compliant._with_elementwise(func)

    def split(self, by: str) -> DuckDBExpr:
        return self.compliant._with_elementwise(
            lambda expr: F("str_split", expr, lit(by))
        )

    def len_chars(self) -> DuckDBExpr:
        return self.compliant._with_elementwise(lambda expr: F("length", expr))

    def to_lowercase(self) -> DuckDBExpr:
        return self.compliant._with_elementwise(lambda expr: F("lower", expr))

    def to_uppercase(self) -> DuckDBExpr:
        return self.compliant._with_elementwise(lambda expr: F("upper", expr))

    def strip_chars(self, characters: str | None) -> DuckDBExpr:
        import string

        return self.compliant._with_elementwise(
            lambda expr: F(
                "trim", expr, lit(string.whitespace if characters is None else characters)
            )
        )

    def replace_all(self, pattern: str, value: str, *, literal: bool) -> DuckDBExpr:
        if not literal:
            return self.compliant._with_elementwise(
                lambda expr: F("regexp_replace", expr, lit(pattern), lit(value), lit("g"))
            )
        return self.compliant._with_elementwise(
            lambda expr: F("replace", expr, lit(pattern), lit(value))
        )

    def to_datetime(self, format: str | None) -> DuckDBExpr:
        if format is None:
            msg = "Cannot infer format with DuckDB backend, please specify `format` explicitly."
            raise NotImplementedError(msg)

        return self.compliant._with_elementwise(
            lambda expr: F("strptime", expr, lit(format))
        )

    def to_date(self, format: str | None) -> DuckDBExpr:
        if format is not None:
            return self.to_datetime(format=format).dt.date()

        compliant_expr = self.compliant
        return compliant_expr.cast(compliant_expr._version.dtypes.Date())

    def zfill(self, width: int) -> DuckDBExpr:
        # DuckDB does not have a built-in zfill function, so we need to implement it manually
        # using string manipulation functions.

        def func(expr: Expression) -> Expression:
            less_than_width = F("length", expr) < lit(width)
            zero, hyphen, plus = lit("0"), lit("-"), lit("+")

            starts_with_minus = F("starts_with", expr, hyphen)
            starts_with_plus = F("starts_with", expr, plus)
            substring = F("substr", expr, lit(2))
            padded_substring = F("lpad", substring, lit(width - 1), zero)
            return (
                when(
                    starts_with_minus & less_than_width,
                    F("concat", hyphen, padded_substring),
                )
                .when(
                    starts_with_plus & less_than_width,
                    F("concat", plus, padded_substring),
                )
                .when(less_than_width, F("lpad", expr, lit(width), zero))
                .otherwise(expr)
            )

        # can't use `_with_elementwise` due to `when` operator.
        # TODO(unassigned): implement `window_func` like we do in `Expr.cast`
        return self.compliant._with_callable(func)

    replace = not_implemented()
