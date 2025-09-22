# Copyright The OpenTelemetry Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from opentelemetry import context
from opentelemetry.instrumentation.utils import _url_quote


def _add_sql_comment(sql, **meta) -> str:
    """
    Appends comments to the sql statement and returns it
    """
    meta.update(**_add_framework_tags())
    comment = _generate_sql_comment(**meta)
    sql = sql.rstrip()
    if sql.endswith(";"):
        sql = sql[:-1] + comment + ";"
    else:
        sql = sql + comment
    return sql


def _generate_sql_comment(**meta) -> str:
    """
    Return a SQL comment with comma delimited key=value pairs created from
    **meta kwargs.
    """
    key_value_delimiter = ","

    if not meta:  # No entries added.
        return ""

    # Sort the keywords to ensure that caching works and that testing is
    # deterministic. It eases visual inspection as well.
    return (
        " /*"
        + key_value_delimiter.join(
            f"{_url_quote(key)}={_url_quote(value)!r}"
            for key, value in sorted(meta.items())
            if value is not None
        )
        + "*/"
    )


def _add_framework_tags() -> dict:
    """
    Returns orm related tags if any set by the context
    """

    sqlcommenter_framework_values = (
        context.get_value("SQLCOMMENTER_ORM_TAGS_AND_VALUES")
        if context.get_value("SQLCOMMENTER_ORM_TAGS_AND_VALUES")
        else {}
    )
    return sqlcommenter_framework_values
