from __future__ import annotations

from typing import Generic

from narwhals.typing import SeriesT


class SeriesListNamespace(Generic[SeriesT]):
    def __init__(self, series: SeriesT) -> None:
        self._narwhals_series = series

    def len(self) -> SeriesT:
        """Return the number of elements in each list.

        Null values count towards the total.

        Returns:
            A new series.

        Examples:
            >>> import pyarrow as pa
            >>> import narwhals as nw
            >>> s_native = pa.chunked_array([[[1, 2], [3, 4, None], None, []]])
            >>> s = nw.from_native(s_native, series_only=True)
            >>> s.list.len().to_native()  # doctest: +ELLIPSIS
            <pyarrow.lib.ChunkedArray object at ...>
            [
              [
                2,
                3,
                null,
                0
              ]
            ]
        """
        return self._narwhals_series._with_compliant(
            self._narwhals_series._compliant_series.list.len()
        )
