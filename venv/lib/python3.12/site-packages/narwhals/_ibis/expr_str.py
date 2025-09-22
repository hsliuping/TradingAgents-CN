from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, cast

import ibis
import ibis.expr.types as ir
from ibis.expr.datatypes import Timestamp

from narwhals._compliant import LazyExprNamespace
from narwhals._compliant.any_namespace import StringNamespace
from narwhals._ibis.utils import lit
from narwhals._utils import _is_naive_format, not_implemented

if TYPE_CHECKING:
    from narwhals._ibis.expr import IbisExpr


class IbisExprStringNamespace(LazyExprNamespace["IbisExpr"], StringNamespace["IbisExpr"]):
    def starts_with(self, prefix: str) -> IbisExpr:
        def fn(expr: ir.StringColumn) -> ir.BooleanValue:
            return expr.startswith(prefix)

        return self.compliant._with_callable(fn)

    def ends_with(self, suffix: str) -> IbisExpr:
        def fn(expr: ir.StringColumn) -> ir.BooleanValue:
            return expr.endswith(suffix)

        return self.compliant._with_callable(fn)

    def contains(self, pattern: str, *, literal: bool) -> IbisExpr:
        def fn(expr: ir.StringColumn) -> ir.BooleanValue:
            return expr.contains(pattern) if literal else expr.re_search(pattern)

        return self.compliant._with_callable(fn)

    def slice(self, offset: int, length: int | None) -> IbisExpr:
        def fn(expr: ir.StringColumn) -> ir.StringValue:
            return expr.substr(start=offset, length=length)

        return self.compliant._with_callable(fn)

    def split(self, by: str) -> IbisExpr:
        def fn(expr: ir.StringColumn) -> ir.ArrayValue:
            return expr.split(by)

        return self.compliant._with_callable(fn)

    def len_chars(self) -> IbisExpr:
        return self.compliant._with_callable(lambda expr: expr.length())

    def to_lowercase(self) -> IbisExpr:
        return self.compliant._with_callable(lambda expr: expr.lower())

    def to_uppercase(self) -> IbisExpr:
        return self.compliant._with_callable(lambda expr: expr.upper())

    def strip_chars(self, characters: str | None) -> IbisExpr:
        if characters is not None:
            msg = "Ibis does not support `characters` argument in `str.strip_chars`"
            raise NotImplementedError(msg)

        return self.compliant._with_callable(lambda expr: expr.strip())

    def _replace_all(self, pattern: str, value: str) -> Callable[..., ir.StringValue]:
        def fn(expr: ir.StringColumn) -> ir.StringValue:
            return expr.re_replace(pattern, value)

        return fn

    def _replace_all_literal(
        self, pattern: str, value: str
    ) -> Callable[..., ir.StringValue]:
        def fn(expr: ir.StringColumn) -> ir.StringValue:
            return expr.replace(pattern, value)  # pyright: ignore[reportArgumentType]

        return fn

    def replace_all(self, pattern: str, value: str, *, literal: bool) -> IbisExpr:
        fn = self._replace_all_literal if literal else self._replace_all
        return self.compliant._with_callable(fn(pattern, value))

    def _to_datetime(self, format: str) -> Callable[..., ir.TimestampValue]:
        def fn(expr: ir.StringColumn) -> ir.TimestampValue:
            return expr.as_timestamp(format)

        return fn

    def _to_datetime_naive(self, format: str) -> Callable[..., ir.TimestampValue]:
        def fn(expr: ir.StringColumn) -> ir.TimestampValue:
            dtype: Any = Timestamp(timezone=None)
            return expr.as_timestamp(format).cast(dtype)

        return fn

    def to_datetime(self, format: str | None) -> IbisExpr:
        if format is None:
            msg = "Cannot infer format with Ibis backend"
            raise NotImplementedError(msg)
        fn = self._to_datetime_naive if _is_naive_format(format) else self._to_datetime
        return self.compliant._with_callable(fn(format))

    def to_date(self, format: str | None) -> IbisExpr:
        if format is None:
            msg = "Cannot infer format with Ibis backend"
            raise NotImplementedError(msg)

        def fn(expr: ir.StringColumn) -> ir.DateValue:
            return expr.as_date(format)

        return self.compliant._with_callable(fn)

    def zfill(self, width: int) -> IbisExpr:
        def func(expr: ir.StringColumn) -> ir.Value:
            length = expr.length()
            less_than_width = length < lit(width)
            zero, hyphen, plus = "0", "-", "+"
            starts_with_minus = expr.startswith(hyphen)
            starts_with_plus = expr.startswith(plus)
            one = cast("ir.IntegerScalar", lit(1))
            sub_length = cast("ir.IntegerValue", length - one)
            substring = expr.substr(one, sub_length).lpad(width - 1, zero)
            return ibis.cases(
                (starts_with_minus & less_than_width, (substring.lpad(width, hyphen))),
                (starts_with_plus & less_than_width, (substring.lpad(width, plus))),
                (less_than_width, expr.lpad(width, zero)),
                else_=expr,
            )

        return self.compliant._with_callable(func)

    replace = not_implemented()
