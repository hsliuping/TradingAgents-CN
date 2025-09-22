#!/usr/bin/env python
# -*- coding:utf-8 -*- 

'''
Created on 2016年10月1日
@author: Jimmy Liu
@group : waditu
@contact: jimmysoa@sina.cn
'''

import json
import time
import six
from tushare.trader import vars as vs

def nowtime_str():
    return time.time() * 1000


def get_jdata(txtdata):
    txtdata = txtdata.content
    if six.PY3:
        txtdata = txtdata.decode('utf-8')
    jsonobj = json.loads(txtdata)
    return jsonobj
        
        
def get_vcode(broker, res):
    from PIL import Image
    import pytesseract as pt
    import io
    if broker == 'csc':
        imgdata = res.content
        img = Image.open(io.BytesIO(imgdata))
        vcode = pt.image_to_string(img)
        return vcode
    