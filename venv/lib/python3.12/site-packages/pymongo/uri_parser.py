# Copyright 2011-present MongoDB, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you
# may not use this file except in compliance with the License.  You
# may obtain a copy of the License at
#
# https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.  See the License for the specific language governing
# permissions and limitations under the License.


"""Re-import of synchronous URI Parser API for compatibility."""
from __future__ import annotations

import sys

from pymongo.errors import InvalidURI
from pymongo.synchronous.uri_parser import *  # noqa: F403
from pymongo.synchronous.uri_parser import __doc__ as original_doc
from pymongo.uri_parser_shared import *  # noqa: F403

__doc__ = original_doc
__all__ = [  # noqa: F405
    "parse_userinfo",
    "parse_ipv6_literal_host",
    "parse_host",
    "validate_options",
    "split_options",
    "split_hosts",
    "parse_uri",
]

if __name__ == "__main__":
    import pprint

    try:
        pprint.pprint(parse_uri(sys.argv[1]))  # noqa: F405, T203
    except InvalidURI as exc:
        print(exc)  # noqa: T201
    sys.exit(0)
