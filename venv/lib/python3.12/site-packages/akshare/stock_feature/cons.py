#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2019/12/30 21:02
Desc:
"""

stock_em_sy_js = """
    function getCode(num) {
            var str = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz";
            var codes = str.split('');
            num = num || 6;
            var code = "";
            for (var i = 0; i < num; i++) {
                code += codes[Math.floor(Math.random() * 52)]
            }
            return code
        }
    """
