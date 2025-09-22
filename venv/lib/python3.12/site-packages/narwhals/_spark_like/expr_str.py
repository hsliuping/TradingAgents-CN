from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

from narwhals._compliant import LazyExprNamespace
from narwhals._compliant.any_namespace import StringNamespace
from narwhals._spark_like.utils import strptime_to_pyspark_format
from narwhals._utils import _is_naive_format, not_implemented

if TYPE_CHECKING:
    from sqlframe.base.column import Column

    from narwhals._spark_like.expr import SparkLikeExpr


class SparkLikeExprStringNamespace(
    LazyExprNamespace["SparkLikeExpr"], StringNamespace["SparkLikeExpr"]
):
    def len_chars(self) -> SparkLikeExpr:
        return self.compliant._with_elementwise(self.compliant._F.char_length)

    def replace_all(self, pattern: str, value: str, *, literal: bool) -> SparkLikeExpr:
        def func(expr: Column) -> Column:
            replace_all_func = (
                self.compliant._F.replace if literal else self.compliant._F.regexp_replace
            )
            return replace_all_func(
                expr,
                self.compliant._F.lit(pattern),  # pyright: ignore[reportArgumentType]
                self.compliant._F.lit(value),  # pyright: ignore[reportArgumentType]
            )

        return self.compliant._with_elementwise(func)

    def strip_chars(self, characters: str | None) -> SparkLikeExpr:
        import string

        def func(expr: Column) -> Column:
            to_remove = characters if characters is not None else string.whitespace
            return self.compliant._F.btrim(expr, self.compliant._F.lit(to_remove))

        return self.compliant._with_elementwise(func)

    def starts_with(self, prefix: str) -> SparkLikeExpr:
        return self.compliant._with_elementwise(
            lambda expr: self.compliant._F.startswith(expr, self.compliant._F.lit(prefix))
        )

    def ends_with(self, suffix: str) -> SparkLikeExpr:
        return self.compliant._with_elementwise(
            lambda expr: self.compliant._F.endswith(expr, self.compliant._F.lit(suffix))
        )

    def contains(self, pattern: str, *, literal: bool) -> SparkLikeExpr:
        def func(expr: Column) -> Column:
            contains_func = (
                self.compliant._F.contains if literal else self.compliant._F.regexp
            )
            return contains_func(expr, self.compliant._F.lit(pattern))

        return self.compliant._with_elementwise(func)

    def slice(self, offset: int, length: int | None) -> SparkLikeExpr:
        # From the docs: https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.functions.substring.html
        # The position is not zero based, but 1 based index.
        def func(expr: Column) -> Column:
            col_length = self.compliant._F.char_length(expr)

            _offset = (
                col_length + self.compliant._F.lit(offset + 1)
                if offset < 0
                else self.compliant._F.lit(offset + 1)
            )
            _length = self.compliant._F.lit(length) if length is not None else col_length
            return expr.substr(_offset, _length)

        return self.compliant._with_elementwise(func)

    def split(self, by: str) -> SparkLikeExpr:
        return self.compliant._with_elementwise(
            lambda expr: self.compliant._F.split(expr, by)
        )

    def to_uppercase(self) -> SparkLikeExpr:
        return self.compliant._with_elementwise(self.compliant._F.upper)

    def to_lowercase(self) -> SparkLikeExpr:
        return self.compliant._with_elementwise(self.compliant._F.lower)

    def to_datetime(self, format: str | None) -> SparkLikeExpr:
        F = self.compliant._F  # noqa: N806
        if not format:
            function = F.to_timestamp
        elif _is_naive_format(format):
            function = partial(
                F.to_timestamp_ntz, format=F.lit(strptime_to_pyspark_format(format))
            )
        else:
            format = strptime_to_pyspark_format(format)
            function = partial(F.to_timestamp, format=format)
        return self.compliant._with_elementwise(
            lambda expr: function(F.replace(expr, F.lit("T"), F.lit(" ")))
        )

    def to_date(self, format: str | None) -> SparkLikeExpr:
        F = self.compliant._F  # noqa: N806
        return self.compliant._with_elementwise(
            lambda expr: F.to_date(expr, format=strptime_to_pyspark_format(format))
        )

    def zfill(self, width: int) -> SparkLikeExpr:
        def func(expr: Column) -> Column:
            F = self.compliant._F  # noqa: N806

            length = F.length(expr)
            less_than_width = length < width
            hyphen, plus = F.lit("-"), F.lit("+")
            starts_with_minus = F.startswith(expr, hyphen)
            starts_with_plus = F.startswith(expr, plus)
            sub_length = length - F.lit(1)
            # NOTE: `len` annotated as `int`, but `Column.substr` accepts `int | Column`
            substring = F.substring(expr, 2, sub_length)  # pyright: ignore[reportArgumentType]
            padded_substring = F.lpad(substring, width - 1, "0")
            return (
                F.when(
                    starts_with_minus & less_than_width,
                    F.concat(hyphen, padded_substring),
                )
                .when(
                    starts_with_plus & less_than_width, F.concat(plus, padded_substring)
                )
                .when(less_than_width, F.lpad(expr, width, "0"))
                .otherwise(expr)
            )

        # can't use `_with_elementwise` due to `when` operator.
        # TODO(unassigned): implement `window_func` like we do in `Expr.cast`
        return self.compliant._with_callable(func)

    replace = not_implemented()
