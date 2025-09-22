# coding: utf-8

import tempfile
import six
import math

if six.PY2:
    from urllib2 import urlopen, Request
else:
    from urllib.request import urlopen, Request



def demo_reporthook(downloaded, total_size):
    print("Downloaded {}, Total is {}".format(downloaded, total_size))

class BaseCralwer:

    def __init__(self, mode="http"):
        self.mode = "http"

    def fetch_and_parse(self, reporthook = None, path_to_download=None, proxies=None, chunksize=1024 * 50, *args, **kwargs):
        """
        function to get data ,
        :param reporthook 使用urllib.request 的report_hook 来汇报下载进度 \
                    参考 https://docs.python.org/3/library/urllib.request.html#module-urllib.request
        :param path_to_download 数据文件下载的地址，如果没有提供，则下载到临时文件中，并在解析之后删除
        :param proxies urllib格式的代理服务器设置
        :return: 解析之后的数据结果
        """
        if (self.mode == "http"):
            download_file = self.fetch_via_http(reporthook=reporthook, path_to_download=path_to_download, proxies=proxies, chunksize=chunksize, *args, **kwargs) 
        else:
            download_file = self.get_content(reporthook=reporthook, path_to_download=path_to_download, chunksize=chunksize, *args, **kwargs);
        
        result =  self.parse(download_file, *args, **kwargs)
        try:
            download_file.close()
        except:
            pass
        return result

    def fetch_via_http(self, reporthook = None, path_to_download=None, proxies=None, chunksize=1024 * 50, *args, **kwargs):
        if path_to_download is None:
            download_file = tempfile.NamedTemporaryFile(delete=True)
        else:
            download_file = open(path_to_download, 'wb')

        url = self.get_url(*args, **kwargs)

        request = Request(url)
        request.add_header('Referer', url)
        request.add_header('User-Agent', r"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/76.0.3809.100 Safari/537.36")
        res = urlopen(request)

        if six.PY2:
            resinfo = res.info()
        else:
            resinfo = res

        if resinfo.getheader('Content-Length') is not None:
            total_size = int(resinfo.getheader('Content-Length').strip())
            downloaded = 0

            while True:
                chunk = res.read(chunksize)
                downloaded += len(chunk)
                if reporthook is not None:
                    reporthook(downloaded,total_size)
                if not chunk:
                    break
                download_file.write(chunk)
        else:
            content = res.read()
            download_file.write(content)

        download_file.seek(0)
        return download_file


    def get_url(self, *args, **kwargs):
        raise NotImplementedError("will impl in subclass")
    
    def get_content(self, reporthook = None, path_to_download=None, proxies=None, chunksize=1024 * 50, *args, **kwargs):
        raise NotImplementedError("will impl in subclass")

    def parse(self, download_file, *args, **kwargs):
        raise NotImplementedError("will impl in subclass")