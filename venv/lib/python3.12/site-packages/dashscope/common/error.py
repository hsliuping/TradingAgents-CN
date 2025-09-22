# Copyright (c) Alibaba, Inc. and its affiliates.


class DashScopeException(Exception):
    pass


class AuthenticationError(DashScopeException):
    pass


class InvalidParameter(DashScopeException):
    pass


class InvalidTask(DashScopeException):
    pass


class UnsupportedModel(DashScopeException):
    pass


class UnsupportedTask(DashScopeException):
    pass


class ModelRequired(DashScopeException):
    pass


class InvalidModel(DashScopeException):
    pass


class InvalidInput(DashScopeException):
    pass


class InvalidFileFormat(DashScopeException):
    pass


class UnsupportedApiProtocol(DashScopeException):
    pass


class NotImplemented(DashScopeException):
    pass


class MultiInputsWithBinaryNotSupported(DashScopeException):
    pass


class UnexpectedMessageReceived(DashScopeException):
    pass


class UnsupportedData(DashScopeException):
    pass


class AssistantError(DashScopeException):
    def __init__(self, **kwargs):
        self.message = None
        self.code = None
        self.request_id = None
        if 'message' in kwargs:
            import json
            msg = json.loads(kwargs['message'])
            if 'request_id' in msg:
                self.request_id = msg['request_id']
            if 'code' in msg:
                self.code = msg['code']
            if 'message' in msg:
                self.message = msg['message']

    def __str__(self):
        msg = 'Request failed, request_id: %s, code: %s, message: %s' % (  # noqa E501
            self.request_id, self.code, self.message)
        return msg


# for server send generation or inference error.
class RequestFailure(DashScopeException):
    def __init__(self,
                 request_id=None,
                 message=None,
                 name=None,
                 http_code=None):
        self.request_id = request_id
        self.message = message
        self.name = name
        self.http_code = http_code

    def __str__(self):
        msg = 'Request failed, request_id: %s, http_code: %s error_name: %s, error_message: %s' % (  # noqa E501
            self.request_id, self.http_code, self.name, self.message)
        return msg


class UnknownMessageReceived(DashScopeException):
    pass


class InputDataRequired(DashScopeException):
    pass


class InputRequired(DashScopeException):
    pass


class UnsupportedDataType(DashScopeException):
    pass


class ServiceUnavailableError(DashScopeException):
    pass


class UnsupportedHTTPMethod(DashScopeException):
    pass


class AsyncTaskCreateFailed(DashScopeException):
    pass


class UploadFileException(DashScopeException):
    pass


class TimeoutException(DashScopeException):
    pass
