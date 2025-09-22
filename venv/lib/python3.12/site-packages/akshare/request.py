import time

import requests
from requests.exceptions import RequestException

from akshare.exceptions import NetworkError, APIError, RateLimitError, DataParsingError
from akshare.utils.context import config


def make_request_with_retry_json(
    url, params=None, headers=None, proxies=None, max_retries=3, retry_delay=1
):
    """
    发送 HTTP GET 请求，支持重试机制和代理设置。

    :param url: 请求的 URL
    :param params: URL 参数 (可选)
    :param headers: 请求头 (可选)
    :param proxies: 代理设置 (可选)
    :param max_retries: 最大重试次数
    :param retry_delay: 初始重试延迟（秒）
    :return: 解析后的 JSON 数据
    """
    if proxies is None:
        proxies = config.proxies
    for attempt in range(max_retries):
        try:
            response = requests.get(
                url, params=params, headers=headers, proxies=proxies
            )
            if response.status_code == 200:
                try:
                    data = response.json()
                    if not data:
                        raise DataParsingError("Empty response data")
                    return data
                except ValueError:
                    raise DataParsingError("Failed to parse JSON response")
            elif response.status_code == 429:
                raise RateLimitError(
                    f"Rate limit exceeded. Status code: {response.status_code}"
                )
            else:
                raise APIError(
                    f"API request failed. Status code: {response.status_code}"
                )

        except (RequestException, RateLimitError, APIError, DataParsingError) as e:
            if attempt == max_retries - 1:
                if isinstance(e, RateLimitError):
                    raise
                elif isinstance(e, (APIError, DataParsingError)):
                    raise
                else:
                    raise NetworkError(
                        f"Failed to connect after {max_retries} attempts: {str(e)}"
                    )

            time.sleep(retry_delay)
            retry_delay *= 2  # 指数退避策略

    raise NetworkError(f"Failed to connect after {max_retries} attempts")


def make_request_with_retry_text(
    url, params=None, headers=None, proxies=None, max_retries=3, retry_delay=1
):
    """
    发送 HTTP GET 请求，支持重试机制和代理设置。

    :param url: 请求的 URL
    :param params: URL 参数 (可选)
    :param headers: 请求头 (可选)
    :param proxies: 代理设置 (可选)
    :param max_retries: 最大重试次数
    :param retry_delay: 初始重试延迟（秒）
    :return: 解析后的 JSON 数据
    """
    if proxies is None:
        proxies = config.proxies
    for attempt in range(max_retries):
        try:
            response = requests.get(
                url, params=params, headers=headers, proxies=proxies
            )
            if response.status_code == 200:
                try:
                    data = response.text
                    if not data:
                        raise DataParsingError("Empty response data")
                    return data
                except ValueError:
                    raise DataParsingError("Failed to parse JSON response")
            elif response.status_code == 429:
                raise RateLimitError(
                    f"Rate limit exceeded. Status code: {response.status_code}"
                )
            else:
                raise APIError(
                    f"API request failed. Status code: {response.status_code}"
                )

        except (RequestException, RateLimitError, APIError, DataParsingError) as e:
            if attempt == max_retries - 1:
                if isinstance(e, RateLimitError):
                    raise
                elif isinstance(e, (APIError, DataParsingError)):
                    raise
                else:
                    raise NetworkError(
                        f"Failed to connect after {max_retries} attempts: {str(e)}"
                    )

            time.sleep(retry_delay)
            retry_delay *= 2  # 指数退避策略

    raise NetworkError(f"Failed to connect after {max_retries} attempts")
