#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/8/28 15:00
Desc: To test intention, just write test code here!
"""

import pathlib

from akshare.datasets import get_ths_js, get_crypto_info_csv


def test_cost_living():
    """
    just for test aim
    :return: assert result
    :rtype: assert
    """
    pass


def test_path_func():
    """
    test path func
    :return: path of file
    :rtype: pathlib.Path
    """
    temp_path = get_ths_js("ths.js")
    assert isinstance(temp_path, pathlib.Path)


def test_zipfile_func():
    """
    test path func
    :return: path of file
    :rtype: pathlib.Path
    """
    temp_path = get_crypto_info_csv("crypto_info.zip")
    assert isinstance(temp_path, pathlib.Path)


if __name__ == "__main__":
    # test_cost_living()
    test_path_func()
    test_zipfile_func()
