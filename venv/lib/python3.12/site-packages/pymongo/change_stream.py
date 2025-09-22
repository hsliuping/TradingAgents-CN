# Copyright 2024-present MongoDB, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Re-import of synchronous ChangeStream API for compatibility."""
from __future__ import annotations

from pymongo.synchronous.change_stream import *  # noqa: F403
from pymongo.synchronous.change_stream import __doc__ as original_doc

__doc__ = original_doc
__all__ = ["ChangeStream", "ClusterChangeStream", "CollectionChangeStream", "DatabaseChangeStream"]  # noqa: F405
