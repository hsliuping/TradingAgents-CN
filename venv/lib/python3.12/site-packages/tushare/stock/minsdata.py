# -*- coding:utf-8 -*- 

import tushare as ts
import pandas as pd
import random
from multiprocessing.dummy import Pool as ThreadPool


class TsData(object):
    def __init__(self):
        self.url = 'http://file.tushare.org/tsdata/symbols.csv'
        self.stocks = self._get_data()
        self.cons = None #self._get_cons()
        self.data = pd.DataFrame()
        

    def _get_data(self):
        df = pd.read_csv(self.url,
                         dtype={'symbol': object})
        return list(df['symbol'].values)
    

    def _get_cons(self):
        con1 = ts.get_apis()
        con2 = ts.get_apis()
        con3 = ts.get_apis()
        con4 = ts.get_apis()
        con5 = ts.get_apis()
        return [con1, con2, con3, con4, con5]


    def _get_server(self):
        random.shuffle(self.cons)
        return self.cons[0]
    
    
    
    def _data(self, symbol, start_date='', end_date=''):
        try:
            conn = self._get_server()
            df = ts.bar(symbol, conn=conn, freq='5min')
            df = df.reset_index(inplace=True)
            df = df[['datetime', 'open', 'close', 'high', 'low', 'volume', 'code']]
            self.data = self.data.append(df, ignore_index=True) 
            return df
        except:
            return None
        
    
    def _get_k_data(self, symbol):
        try:
            df = ts.get_k_data(symbol, ktype='5')
            df = df[['date', 'open', 'close', 'high', 'low', 'volume', 'code']]
            df.columns = ['datetime', 'open', 'close', 'high', 'low', 'volume', 'code']
            return df
        except:
            return None
        
            
    
    def get_m_data(self, symbols):
        print(symbols)
        df = self._get_k_data(symbols)
        if df is None:
            if self.cons is None:
                self.cons = self._get_cons()
            df = self._data(symbols)
        self.data = self.data.append(df, ignore_index=True)
        
        
    
    def get_data(self, symbols=None):
        if symbols is None:
            stocks = self._get_data()
        pool = ThreadPool(600)
        pool.map(self.get_m_data, stocks)
        if self.cons is not None:
            for con in self.cons:
                ts.close_apis(con)
        return self.data
        
        
if __name__ == '__main__':
    api = TsData()
    df = api.get_data()
    print(df)
