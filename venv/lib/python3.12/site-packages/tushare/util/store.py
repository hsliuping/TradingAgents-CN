# -*- coding:utf-8 -*-
"""
Created on 2015/02/04
@author: Jimmy Liu
@group : waditu
@contact: jimmysoa@sina.cn
"""
import pandas as pd
import tushare as ts
from pandas import compat
import os


class Store(object):

    def __init__(self, data=None, name=None, path=None):
        if isinstance(data, pd.DataFrame):
            self.data = data
        else:
            raise RuntimeError('data type is incorrect')
        self.name = name
        self.path = path

    def save_as(self, name, path, to='csv'):
        if name is None:
            name = self.name
        if path is None:
            path = self.path
        file_path = '%s%s%s.%s'
        if isinstance(name, compat.string_types) and name is not '':
            if (path is None) or (path == ''):
                file_path = '.'.join([name, to])
            else:
                try:
                    if os.path.exists(path) is False:
                        os.mkdir(path) 
                    file_path = file_path%(path, '/', name, to)
                except:
                    pass
            
        else:
            print('input error')

