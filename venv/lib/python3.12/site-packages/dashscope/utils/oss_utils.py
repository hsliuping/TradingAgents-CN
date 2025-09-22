# Copyright (c) Alibaba, Inc. and its affiliates.

import mimetypes
import os
from datetime import datetime
from http import HTTPStatus
from time import mktime
from typing import List
from urllib.parse import unquote_plus, urlparse
from wsgiref.handlers import format_date_time

import requests

from dashscope.api_entities.dashscope_response import DashScopeAPIResponse
from dashscope.client.base_api import GetMixin
from dashscope.common.constants import FILE_PATH_SCHEMA
from dashscope.common.error import InvalidInput, UploadFileException
from dashscope.common.logging import logger
from dashscope.common.utils import get_user_agent


class OssUtils(GetMixin):
    SUB_PATH = 'uploads'

    @classmethod
    def _decode_response_error(cls, response: requests.Response):
        if 'application/json' in response.headers.get('content-type', ''):
            message = response.json()
        else:
            message = response.content.decode('utf-8')
        return message

    @classmethod
    def upload(cls,
               model: str,
               file_path: str,
               api_key: str = None,
               **kwargs) -> DashScopeAPIResponse:
        """Upload file for model fine-tune or other tasks.

        Args:
            file_path (str): The local file name to upload.
            purpose (str): The purpose of the file[fine-tune|inference]
            description (str, optional): The file description message.
            api_key (str, optional): The api key. Defaults to None.

        Returns:
            DashScopeAPIResponse: The upload information
        """
        upload_info = cls.get_upload_certificate(model=model, api_key=api_key)
        if upload_info.status_code != HTTPStatus.OK:
            raise UploadFileException(
                'Get upload certificate failed, code: %s, message: %s' %
                (upload_info.code, upload_info.message))
        upload_info = upload_info.output
        headers = {}
        headers = {'user-agent': get_user_agent()}
        headers['Accept'] = 'application/json'
        headers['Date'] = format_date_time(mktime(datetime.now().timetuple()))
        form_data = {}
        form_data['OSSAccessKeyId'] = upload_info['oss_access_key_id']
        form_data['Signature'] = upload_info['signature']
        form_data['policy'] = upload_info['policy']
        form_data['key'] = upload_info['upload_dir'] + \
            '/' + os.path.basename(file_path)
        form_data['x-oss-object-acl'] = upload_info['x_oss_object_acl']
        form_data['x-oss-forbid-overwrite'] = upload_info[
            'x_oss_forbid_overwrite']
        form_data['success_action_status'] = '200'
        form_data['x-oss-content-type'] = mimetypes.guess_type(file_path)[0]
        url = upload_info['upload_host']
        files = {'file': open(file_path, 'rb')}
        with requests.Session() as session:
            response = session.post(url,
                                    files=files,
                                    data=form_data,
                                    headers=headers,
                                    timeout=3600)
            if response.status_code == HTTPStatus.OK:
                return 'oss://' + form_data['key']
            else:
                msg = (
                    'Uploading file: %s to oss failed, error: %s' %
                    (file_path, cls._decode_response_error(response=response)))
                logger.error(msg)
                raise UploadFileException(msg)

    @classmethod
    def get_upload_certificate(cls,
                               model: str,
                               api_key: str = None,
                               **kwargs) -> DashScopeAPIResponse:
        """Get a oss upload certificate.

        Args:
            api_key (str, optional): The api key. Defaults to None.

        Returns:
            DashScopeAPIResponse: The job info
        """
        params = {'action': 'getPolicy'}
        params['model'] = model
        return super().get(None, api_key, params=params, **kwargs)


def upload_file(model: str, upload_path: str, api_key: str):
    if upload_path.startswith(FILE_PATH_SCHEMA):
        parse_result = urlparse(upload_path)
        if parse_result.netloc:
            file_path = parse_result.netloc + unquote_plus(parse_result.path)
        else:
            file_path = unquote_plus(parse_result.path)
        if os.path.exists(file_path):
            file_url = OssUtils.upload(model=model,
                                       file_path=file_path,
                                       api_key=api_key)
            if file_url is None:
                raise UploadFileException('Uploading file: %s failed' %
                                          upload_path)
            return file_url
        else:
            raise InvalidInput('The file: %s is not exists!' % file_path)
    return None


def check_and_upload_local(model: str, content: str, api_key: str):
    """Check the content is local file path, upload and return the url

    Args:
        model (str): Which model to upload.
        content (str): The content.
        api_key (_type_): The api key.

    Raises:
        UploadFileException: Upload failed.
        InvalidInput: The input is invalid

    Returns:
        _type_: if upload return True and file_url otherwise False, origin content.
    """
    if content.startswith(FILE_PATH_SCHEMA):
        parse_result = urlparse(content)
        if parse_result.netloc:
            file_path = parse_result.netloc + unquote_plus(parse_result.path)
        else:
            file_path = unquote_plus(parse_result.path)
        if os.path.isfile(file_path):
            file_url = OssUtils.upload(model=model,
                                       file_path=file_path,
                                       api_key=api_key)
            if file_url is None:
                raise UploadFileException('Uploading file: %s failed' %
                                          content)
            return True, file_url
        else:
            raise InvalidInput('The file: %s is not exists!' % file_path)
    elif content.startswith('oss://'):
        return True, content
    elif not content.startswith('http'):
        content = os.path.expanduser(content)
        if os.path.isfile(content):
            file_url = OssUtils.upload(model=model,
                                       file_path=content,
                                       api_key=api_key)
            if file_url is None:
                raise UploadFileException('Uploading file: %s failed' %
                                          content)
            return True, file_url
    return False, content


def check_and_upload(model, elem: dict, api_key):
    has_upload = False
    for key, content in elem.items():
        # support video:[images] for qwen2-vl
        is_list = isinstance(content, list)
        contents = content if is_list else [content]

        if key in ['image', 'video', 'audio', 'text']:
            for i, content in enumerate(contents):
                is_upload, file_url = check_and_upload_local(
                    model, content, api_key)
                if is_upload:
                    contents[i] = file_url
                    has_upload = True
        elem[key] = contents if is_list else contents[0]

    return has_upload


def preprocess_message_element(model: str, elem: List[dict], api_key: str):
    is_upload = check_and_upload(model, elem, api_key)
    return is_upload
