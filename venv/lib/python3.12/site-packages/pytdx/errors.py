# coding=utf-8


class TdxConnectionError(Exception):
    """
    当连接服务器出错的时候，会抛出的异常
    """
    pass

class TdxFunctionCallError(Exception):
    """
    当行数调用出错的时候
    """
    def __init__(self, *args, **kwargs):
        super(TdxFunctionCallError, self).__init__(*args, **kwargs)
        self.original_exception = None




