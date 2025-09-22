# coding=utf-8

    
from pytdx.parser.base import BaseParser
from pytdx.helper import get_datetime, get_volume, get_price
from collections import OrderedDict
import struct
#import hexdump
from pytdx.log import DEBUG, log

class GetHistoryInstrumentBarsRange(BaseParser):
    def __init__(self, *args, **kvargs):
        self.seqid = 1
        BaseParser.__init__(self, *args, **kvargs)
        
        
    def setParams(self, market, code, date,date2):
        
        
        pkg = bytearray.fromhex('01')
        pkg.extend(struct.pack("<B", self.seqid))
        self.seqid = self.seqid+1
        pkg.extend(bytearray.fromhex('38 92 00 01 16 00 16 00 0D 24'))
        code = code.encode("utf-8")
        #x =struct.pack("<B9s",  market, code)
        pkg.extend(struct.pack("<B9s",  market, code))
        pkg.extend(bytearray.fromhex('07 00'))
        pkg.extend(struct.pack("<LL", date,date2))
        #print(hexdump.hexdump(pkg))
        self.send_pkg = pkg
#      
        
        
    def _parse_date(self, num):
        year = num // 2048 + 2004
        month = (num % 2048) // 100
        day = (num % 2048) % 100

        return year, month, day

    def _parse_time(self, num):
        return (num // 60) , (num % 60)

    def parseResponse(self, body_buf):
#        print('测试', body_buf)
#        fileobj = open("a.bin", 'wb')  # make partfile
#        fileobj.write(body_buf)  # write data into partfile
#        fileobj.close()
        #print(hexdump.hexdump(body_buf[0:1024]))
#        import zlib
#        d=zlib.decompress(body_buf[16:])        
#        print(hexdump.hexdump(d))
        klines=[]
        pos = 12

        # 算了，前面不解析了，没太大用
        # (market, code) = struct.unpack("<B9s", body_buf[0: 10]

        (ret_count,) = struct.unpack("H", body_buf[pos: pos+2])
        pos = pos+2
        #print(hexdump.hexdump(body_buf[20:52]))
       # print(hexdump.hexdump(body_buf[20: 20+ret_count*32]))
        #global raw_li
        print(ret_count)
        
        for i in range(ret_count):
            (d1,d2,open_price, high, low, close, position, trade, settlementprice) = struct.unpack("<HHffffIIf", body_buf[pos:pos+32])  
            #print(raw_li[0])
            pos = pos+ 32
            #print(i)
            #pass
            #print(raw_li[i][0])
            year, month, day = self._parse_date(d1)
            hour, minute     = self._parse_time(d2)
#            print('%02d%02d%02d %02d %02d'%(year,month,day,hour,minute))
#            print('%5.2f %5.2f %5.2f %5.2f %7d %7d %5.2f'%(open_price, high, low, close, position, trade, settlementprice))
#            (open_price, high, low, close, position, trade, price) = struct.unpack("<ffffIIf", body_buf[pos: pos+28])
#            pos += 28
            kline = OrderedDict([
                ("datetime", "%d-%02d-%02d %02d:%02d" % (year, month, day, hour, minute)),
                ("year", year),
                ("month", month),
                ("day", day),
                ("hour", hour),
                ("minute", minute),
                ("open", open_price),
                ("high", high),
                ("low", low),
                ("close", close),
                ("position", position),
                ("trade", trade),
                ("settlementprice", settlementprice)
               
                
                
            ])
            klines.append(kline)

        return klines
        
    
#00000000  01 01 08 6A 01 01 16 00  16 00 FF 23 2F 49 46 4C   ...j.... ...#/IFL 
#00000010  30 00 F0 F4 94 13 07 00  01 00 00 00 00 00 F0 00   0....... ........ 
    
#00000000: 01 01 08 6A 01 01 16 00  16 00 FF 23 4A 4E 56 44  ...j.......#JNVD
#00000010: 41 00 C0 EC A3 13 07 00  01 00 00 00 00 00 C0 03  A...............    

#00000000  01 01 08 6A 01 01 16 00  16 00 FF 23 2F 49 46 31   ...j.... ...#/IF1 
#00000010  37 30 39 00 94 13 07 00  01 00 00 00 00 00 F0 00   709..... ........ 

if __name__ == '__main__':
    import pprint
    from pytdx.exhq import TdxExHq_API
    api = TdxExHq_API()
    with api.connect('61.152.107.141', 7727):
        x = api.to_df(api.get_history_instrument_bars_range(74, "BABA", 20170613,20170620))
        pprint.pprint(x.tail())

        
        
        

