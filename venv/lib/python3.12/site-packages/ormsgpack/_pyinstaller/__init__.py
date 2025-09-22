# SPDX-License-Identifier: (Apache-2.0 OR MIT)

import os


def get_hook_dirs() -> list[str]:
    return [os.path.dirname(__file__)]
