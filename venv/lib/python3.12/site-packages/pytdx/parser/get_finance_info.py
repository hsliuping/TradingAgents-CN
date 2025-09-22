# coding=utf-8

from pytdx.parser.base import BaseParser
from pytdx.helper import get_datetime, get_volume, get_price
from collections import OrderedDict
import struct
import six


"""
b1cb74000c1f1876006f100091009100010000303030303031b884ce4912000100bcc6330103cf2f018999d149c0f92f48e0bab94a700dd24b000000000000000052b89e3ee52e334f00000000b0c5f74a6078904a203db54800000000000000009a65574c881d464d006dd34b00000000000000004019fb4a802b1549405cdbcc7157d7cc00000000e028fb4ae0a2bd4ae0a2bd4a3f87844c3d0a2f4100004040

市场    证券代码        流通股本        所属省份        所属行业        财务更新
日期    上市日期        总股本  国家股  发起人法人股    法人股  B股     H股
职工股  总资产  流动资产        固定资产        无形资产        股东人数
流动负债        长期负债        资本公积金      净资产  主营收入        主营利润
        应收帐款        营业利润        投资收益        经营现金流      总现金流
        存货    利润总额        税后利润        净利润  未分利润        保留
保留
0       000001  1691799.000000  18      1       20170428        19910403
1717041.125000  180199.000000   6086000.000000  27532000.000000 0.000000
0.000000        0.310000        3006194944.000000       0.000000        8119000.
000000  4734000.000000  371177.000000   0.000000        0.000000        56465000
.000000 207739008.000000        27712000.000000 0.000000        0.000000
8228000.000000  611000.000000   -115008000.000000       -112901000.000000
0.000000        8230000.000000  6214000.000000  6214000.000000  69483000.000000
10.940000       3.000000


"""

class GetFinanceInfo(BaseParser):

    def setParams(self, market, code):
        if type(code) is six.text_type:
            code = code.encode("utf-8")
        pkg = bytearray.fromhex(u'0c 1f 18 76 00 01 0b 00 0b 00 10 00 01 00')
        pkg.extend(struct.pack(u"<B6s", market, code))
        self.send_pkg = pkg

    def parseResponse(self, body_buf):
        pos = 0
        pos += 2 #skip num ,we only query 1 in this case
        market, code = struct.unpack(u"<B6s",body_buf[pos: pos+7])
        pos += 7

        (
            liutongguben,
            province,
            industry,
            updated_date,
            ipo_date,
            zongguben,
            guojiagu,
            faqirenfarengu,
            farengu,
            bgu,
            hgu,
            zhigonggu,
            zongzichan,
            liudongzichan,
            gudingzichan,
            wuxingzichan,
            gudongrenshu,
            liudongfuzhai,
            changqifuzhai,
            zibengongjijin,
            jingzichan,
            zhuyingshouru,
            zhuyinglirun,
            yingshouzhangkuan,
            yingyelirun,
            touzishouyu,
            jingyingxianjinliu,
            zongxianjinliu,
            cunhuo,
            lirunzonghe,
            shuihoulirun,
            jinglirun,
            weifenlirun,
            baoliu1,
            baoliu2
        ) = struct.unpack("<fHHIIffffffffffffffffffffffffffffff", body_buf[pos:])

        def _get_v(v):
            return v

        return OrderedDict(
            [
                ("market", market),
                ("code", code.decode("utf-8")),
                ("liutongguben", _get_v(liutongguben)*10000),
                ('province', province),
                ('industry', industry),
                ('updated_date', updated_date),
                ('ipo_date', ipo_date),
                ("zongguben", _get_v(zongguben)*10000),
                ("guojiagu", _get_v(guojiagu)*10000),
                ("faqirenfarengu", _get_v(faqirenfarengu)*10000),
                ("farengu", _get_v(farengu)*10000),
                ("bgu", _get_v(bgu)*10000),
                ("hgu", _get_v(hgu)*10000),
                ("zhigonggu", _get_v(zhigonggu)*10000),
                ("zongzichan", _get_v(zongzichan)*10000),
                ("liudongzichan", _get_v(liudongzichan)*10000),
                ("gudingzichan", _get_v(gudingzichan)*10000),
                ("wuxingzichan", _get_v(wuxingzichan)*10000),
                ("gudongrenshu", _get_v(gudongrenshu)),
                ("liudongfuzhai", _get_v(liudongfuzhai)*10000),
                ("changqifuzhai", _get_v(changqifuzhai)*10000),
                ("zibengongjijin", _get_v(zibengongjijin)*10000),
                ("jingzichan", _get_v(jingzichan)*10000),
                ("zhuyingshouru", _get_v(zhuyingshouru)*10000),
                ("zhuyinglirun", _get_v(zhuyinglirun)*10000),
                ("yingshouzhangkuan", _get_v(yingshouzhangkuan)*10000),
                ("yingyelirun", _get_v(yingyelirun)*10000),
                ("touzishouyu", _get_v(touzishouyu)*10000),
                ("jingyingxianjinliu", _get_v(jingyingxianjinliu)*10000),
                ("zongxianjinliu", _get_v(zongxianjinliu)*10000),
                ("cunhuo", _get_v(cunhuo)*10000),
                ("lirunzonghe", _get_v(lirunzonghe)*10000),
                ("shuihoulirun", _get_v(shuihoulirun)*10000),
                ("jinglirun", _get_v(jinglirun)*10000),
                ("weifenpeilirun", _get_v(weifenlirun)*10000),
                ("meigujingzichan", _get_v(baoliu1)),
                ("baoliu2", _get_v(baoliu2))
            ]
        )

if __name__ == '__main__':
    import pprint
    from pytdx.hq import TdxHq_API
    api = TdxHq_API()
    with api.connect():
        pprint.pprint(api.get_finance_info(0, "000166"))
