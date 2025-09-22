#coding: utf-8
import click

from concurrent.futures import ThreadPoolExecutor
from pytdx.hq import TdxHq_API
import datetime
import time
from pytdx.util.best_ip import select_best_ip

GET_QUOTES_PER_GROUPS=80

@click.command()
@click.argument("ips", nargs=-1)
def main(ips):

    if len(ips) == 0:
        best_ip = select_best_ip()
        ips = [best_ip]
        print("Using default ip: {}".format(best_ip))

    def single_client_benchmark(ip):

        def _log(msg):
            click.echo("HQ_BENCHMARK: [{:15s}] {} ".format(ip, datetime.datetime.now()) + msg)

        def _grouped_list(stocks):
            return [stocks[i:i + GET_QUOTES_PER_GROUPS] for i in range(0, len(stocks), GET_QUOTES_PER_GROUPS)]

        _log("start benchmark")

        total_time = connecting_time = get_security_count_time = get_security_list_time = get_security_quotes_time = num = 0

        start_time = time.time()
        last_time = start_time

        try:
            api = TdxHq_API(multithread=True)

            port = 7709

            if ":" in ip:
                ip, port = ip.split(':')
                port = int(port)

            with api.connect(ip=ip, port=port):
                _log("connected")
                cur_time = time.time()
                connecting_time = cur_time - last_time
                last_time = cur_time
                _log("connecting time is {}".format(connecting_time))

                num = api.get_security_count(0)
                _log("all shenzhen market stock count is {}".format(num))

                cur_time = time.time()
                get_security_count_time = cur_time - last_time
                last_time = cur_time
                _log("get_security_count_time is {}".format(get_security_count_time))

                all = []
                for i in range((num // 1000) + 1):
                    offset = i * 1000
                    section = api.get_security_list(0, offset)
                    all = all + section

                cur_time = time.time()
                get_security_list_time = cur_time - last_time
                last_time = cur_time

                _log("get_security_list_time is {}".format(get_security_list_time))

                codes = [one['code'] for one in all]

                results = []
                for stocks in _grouped_list(codes):
                    req_list = [(0, code) for code in stocks]
                    one_results = api.get_security_quotes(req_list)
                    results = results + one_results

                cur_time = time.time()
                get_security_quotes_time = cur_time - last_time
                last_time = cur_time
                _log("get_security_quotes_time is {}".format(get_security_quotes_time))

                total_time = last_time - start_time

                _log("total_time is {}".format(total_time))

            _log("end benchmark")
        except Exception as e:
            _log("hit exception " + str(e))

        return {
            "ip": ip,
            "total_time": total_time,
            "connecting_time": connecting_time,
            "get_security_count_time": get_security_count_time,
            "get_security_list_time": get_security_list_time,
            "get_security_quotes_time": get_security_quotes_time,
            "security_count": num
        }

    with ThreadPoolExecutor(max_workers=len(ips)) as executor:
        results = executor.map(single_client_benchmark, ips)



        rows = []
        rows.append(("IP", "Total", "Connecting", "Get Count", "Get List", "Get Quotes"))
        for result in results:
            rows.append(
                [result['ip'],

                 "{:0.6f}".format(result['total_time']),
                 "{:0.6f}".format(result['connecting_time']),

                 "{:0.6f} ({})".format(result['get_security_count_time'], result['security_count']),
                 "{:0.6f}".format(result['get_security_list_time']),

                 "{:0.6f}".format(result['get_security_quotes_time'])]
            )

        print("=" * 40)
        print_table(rows)



# helper function from http://blog.paphus.com/blog/2012/09/04/simple-ascii-tables-in-python/
def print_table(lines, separate_head=True):
  """Prints a formatted table given a 2 dimensional array"""
  #Count the column width
  widths = []
  for line in lines:
      for i,size in enumerate([len(x) for x in line]):
          while i >= len(widths):
              widths.append(0)
          if size > widths[i]:
              widths[i] = size

  #Generate the format string to pad the columns
  print_string = ""
  for i,width in enumerate(widths):
      print_string += "{" + str(i) + ":" + str(width) + "} | "
  if (len(print_string) == 0):
      return
  print_string = print_string[:-3]

  #Print the actual data
  for i,line in enumerate(lines):
      print(print_string.format(*line))
      if (i == 0 and separate_head):
          print("-"*(sum(widths)+3*(len(widths)-1)))


if __name__ == '__main__':
    main()