# Copyright (c) Alibaba, Inc. and its affiliates.

import logging
import os

from dashscope.common.constants import DASHSCOPE_LOGGING_LEVEL_ENV

logger = logging.getLogger('dashscope')


def enable_logging():
    level = os.environ.get(DASHSCOPE_LOGGING_LEVEL_ENV, None)
    if level is not None:  # set logging level.
        if level not in ['info', 'debug']:
            # set logging level env, but invalid value, use default.
            level = 'info'
        if level == 'info':
            logger.setLevel(logging.INFO)
        else:
            logger.setLevel(logging.DEBUG)
        # set default logging handler
        console_handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(filename)s - %(funcName)s - %(lineno)d - %(levelname)s - %(message)s'  # noqa E501
        )
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)


# in release disable dashscope log
# you can enable dashscope log for debugger.
enable_logging()
