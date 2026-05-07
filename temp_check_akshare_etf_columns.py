from pathlib import Path
import sys

sys.path.insert(0, str(Path.cwd()))

import akshare as ak


def main():
    df = ak.fund_etf_fund_daily_em()
    print(list(df.columns))


if __name__ == '__main__':
    main()
