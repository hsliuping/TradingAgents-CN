# Copyright (c) Alibaba, Inc. and its affiliates.


class WebsocketStreamingMode:
    # TODO how to know request is duplex or other.
    NONE = 'none'  # no stream
    IN = 'in'  # stream in
    OUT = 'out'
    DUPLEX = 'duplex'


ACTION_KEY = 'action'
EVENT_KEY = 'event'
HEADER = 'header'
TASK_ID = 'task_id'
ERROR_NAME = 'error_code'
ERROR_MESSAGE = 'error_message'


class EventType:
    STARTED = 'task-started'
    GENERATED = 'result-generated'
    FINISHED = 'task-finished'
    FAILED = 'task-failed'


class ActionType:
    START = 'run-task'
    CONTINUE = 'continue-task'
    FINISHED = 'finish-task'
