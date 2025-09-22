#coding: utf-8

from pytdx.reader.base_reader import BaseReader
from pytdx.crawler.history_financial_crawler import HistoryFinancialCrawler

# 使用 history_financial_cralwer 里面的HistoryFinancialCrawler完成此功能，这个reader仅对其做简单的封装

class HistoryFinancialReader(BaseReader):

    def get_df(self, data_file):
        """
        读取历史财务数据文件，并返回pandas结果 ， 类似gpcw20171231.zip格式，具体字段含义参考

        https://github.com/rainx/pytdx/issues/133

        :param data_file: 数据文件地址， 数据文件类型可以为 .zip 文件，也可以为解压后的 .dat
        :return: pandas DataFrame格式的历史财务数据
        """

        crawler = HistoryFinancialCrawler()

        with open(data_file, 'rb') as df:
            data = crawler.parse(download_file=df)

        return crawler.to_df(data)


if __name__ == '__main__':
    # print(HistoryFinancialReader().get_df('/tmp/tmpfile.zip'))
    print(HistoryFinancialReader().get_df('/tmp/gpcw20170930.dat'))