#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/4/29 16:00
Desc: 中国证券投资基金业协会-信息公示数据
中国证券投资基金业协会-新版: https://gs.amac.org.cn
"""

import pandas as pd
import requests

from akshare.utils.tqdm import get_tqdm

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
}


def _get_pages(url: str = "", payload: str = "") -> pd.DataFrame:
    """
    中国证券投资基金业协会-信息公示-私募基金管理人公示 页数
    暂时不使用本函数, 直接可以获取所有数据
    """
    res = requests.post(url=url, json=payload, headers=headers)
    res.encoding = "utf-8"
    json_df = res.json()
    return json_df["totalPages"]


def get_data(url: str = "", payload: str = "") -> pd.DataFrame:
    """
    中国证券投资基金业协会-信息公示-私募基金管理人公示
    """
    res = requests.post(url=url, json=payload, headers=headers)
    res.encoding = "utf-8"
    json_df = res.json()
    return json_df


# 中国证券投资基金业协会-信息公示-会员信息
# 中国证券投资基金业协会-信息公示-会员信息-会员机构综合查询
def amac_member_info() -> pd.DataFrame:
    """
    中国证券投资基金业协会-信息公示-会员信息-会员机构综合查询
    https://gs.amac.org.cn/amac-infodisc/res/pof/member/index.html
    :return: 会员机构综合查询
    :rtype: pandas.DataFrame
    """
    url = "https://gs.amac.org.cn/amac-infodisc/api/pof/pofMember"
    params = {
        "rand": "0.7665138514630696",
        "page": "1",
        "size": "20",
    }
    r = requests.post(url, params=params, json={}, headers=headers)
    data_json = r.json()
    total_page = data_json["totalPages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(0, int(total_page)), leave=False):
        params.update({"page": page})
        r = requests.post(url, params=params, json={}, headers=headers)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["content"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    keys_list = [
        "managerName",
        "memberBehalf",
        "memberType",
        "memberCode",
        "memberDate",
        "primaryInvestType",
        "markStar",
    ]  # 定义要取的 value 的 keys
    manager_data_out = pd.DataFrame(big_df)
    manager_data_out = manager_data_out[keys_list]
    manager_data_out.columns = [
        "机构（会员）名称",
        "会员代表",
        "会员类型",
        "会员编号",
        "入会时间",
        "机构类型",
        "是否星标",
    ]
    manager_data_out["入会时间"] = pd.to_datetime(
        manager_data_out["入会时间"], unit="ms"
    ).dt.date
    return manager_data_out


# 中国证券投资基金业协会-信息公示-从业人员信息
# 中国证券投资基金业协会-信息公示-从业人员信息-基金从业人员资格注册信息
def amac_person_fund_org_list(symbol: str = "公募基金管理公司") -> pd.DataFrame:
    """
    中国证券投资基金业协会-信息公示-从业人员信息-基金从业人员资格注册信息
    https://gs.amac.org.cn/amac-infodisc/res/pof/person/personOrgList.html
    :param symbol: choice of {"公募基金管理公司", "公募基金管理公司资管子公司", "商业银行", "证券公司", "证券公司子公司",
    "私募基金管理人", "保险公司子公司", "保险公司", "外包服务机构", "期货公司", "期货公司资管子公司", "媒体机构",
    "证券投资咨询机构", "评价机构", "外资私募证券基金管理人", "支付结算", "独立服务机构", "地方自律组织", "境外机构",
    "律师事务所", "会计师事务所", "交易所", "独立第三方销售机构", "证券公司资管子公司", "证券公司私募基金子公司", "其他"}
    :type symbol: str
    :return: 基金从业人员资格注册信息
    :rtype: pandas.DataFrame
    """
    symbol_map = {
        "保险公司子公司": "bxgszgs",
        "期货公司资管子公司": "qhgszgzgs",
        "公募基金管理公司资管子公司": "gmjjglgszgzgs",
        "商业银行": "syyh",
        "交易所": "jys",
        "证券公司私募基金子公司": "zqgssmjjzgs",
        "地方自律组织": "dfzlzz",
        "证券公司": "zqgs",
        "评价机构": "pjjg",
        "独立第三方销售机构": "dldsfxsjg",
        "证券投资咨询机构": "zqtzzxjg",
        "外资私募证券基金管理人": "wzsmzqjjglr",
        "境外机构": "jwjg",
        "证券公司子公司": "zqgszgs",
        "公募基金管理公司": "gmjjglgs",
        "媒体机构": "mtjg",
        "支付结算": "zfjs",
        "证券公司资管子公司": "zqgszgzgs",
        "会计师事务所": "kjssws",
        "独立服务机构": "dlfwjg",
        "律师事务所": "lssws",
        "期货公司": "qhgs",
        "保险公司": "bxgs",
        "其他": "qt",
        "外包服务机构": "wbfwjg",
        "私募基金管理人": "smjjglr",
    }
    url = "https://gs.amac.org.cn/amac-infodisc/api/pof/personOrg"
    params = {
        "rand": "0.7665138514630696",
        "page": "1",
        "size": "20",
    }
    r = requests.post(
        url,
        params=params,
        json={"orgType": symbol_map[symbol], "page": "1"},
        headers=headers,
    )
    data_json = r.json()
    total_page = data_json["totalPages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(0, int(total_page)), leave=False):
        params.update({"page": page})
        r = requests.post(
            url,
            params=params,
            json={"orgType": symbol_map[symbol], "page": "1"},
            verify=False,
            headers=headers,
        )
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["content"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    keys_list = [
        "orgName",
        "orgType",
        "workerTotalNum",
        "operNum",
        "salesmanNum",
        "investmentManagerNum",
        "fundManagerNum",
    ]  # 定义要取的 value 的 keys
    manager_data_out = pd.DataFrame(big_df)
    manager_data_out = manager_data_out[keys_list]
    manager_data_out.reset_index(inplace=True)
    manager_data_out["index"] = manager_data_out.index + 1
    manager_data_out.columns = [
        "序号",
        "机构名称",
        "机构类型",
        "员工人数",
        "基金从业资格",
        "基金销售业务资格",
        "基金经理",
        "投资经理",
    ]
    manager_data_out["员工人数"] = pd.to_numeric(manager_data_out["员工人数"])
    manager_data_out["基金从业资格"] = pd.to_numeric(manager_data_out["基金从业资格"])
    manager_data_out["基金销售业务资格"] = pd.to_numeric(
        manager_data_out["基金销售业务资格"]
    )
    manager_data_out["基金经理"] = pd.to_numeric(manager_data_out["基金经理"])
    manager_data_out["投资经理"] = pd.to_numeric(manager_data_out["投资经理"])
    return manager_data_out


# 中国证券投资基金业协会-信息公示-从业人员信息-债券投资交易相关人员公示
def amac_person_bond_org_list() -> pd.DataFrame:
    """
    中国证券投资基金业协会-信息公示-从业人员信息-债券投资交易相关人员公示
    https://human.amac.org.cn/web/org/personPublicity.html
    :return: 债券投资交易相关人员公示
    :rtype: pandas.DataFrame
    """
    import urllib3
    import ssl

    ctx = ssl.create_default_context()
    ctx.options |= ssl.OP_LEGACY_SERVER_CONNECT
    # 使用自定义的 SSL 上下文发起 HTTPS 请求
    http = urllib3.PoolManager(ssl_context=ctx)

    url = "https://human.amac.org.cn/web/api/publicityAddress?rand=0.6288001872566391&pageNum=1&pageSize=5000"
    r = http.request(method="GET", url=url)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["list"])
    temp_df.reset_index(inplace=True)
    temp_df["index"] = range(1, len(temp_df) + 1)
    temp_df.columns = [
        "序号",
        "_",
        "_",
        "机构名称",
        "机构类型",
        "公示网址",
    ]
    temp_df = temp_df[
        [
            "序号",
            "机构类型",
            "机构名称",
            "公示网址",
        ]
    ]
    return temp_df


# 中国证券投资基金业协会-信息公示-私募基金管理人公示
# 中国证券投资基金业协会-信息公示-私募基金管理人公示-私募基金管理人综合查询
def amac_manager_info() -> pd.DataFrame:
    """
    中国证券投资基金业协会-信息公示-私募基金管理人公示-私募基金管理人综合查询
    https://gs.amac.org.cn/amac-infodisc/res/pof/manager/index.html
    :return: 私募基金管理人综合查询
    :rtype: pandas.DataFrame
    """
    url = "https://gs.amac.org.cn/amac-infodisc/api/pof/manager"
    params = {
        "rand": "0.7665138514630696",
        "page": "1",
        "size": "100",
    }
    r = requests.post(url, params=params, json={}, verify=False, headers=headers)
    data_json = r.json()
    total_page = data_json["totalPages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(0, int(total_page)), leave=False):
        params.update({"page": page})
        r = requests.post(url, params=params, json={}, verify=False, headers=headers)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["content"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    keys_list = [
        "managerName",
        "artificialPersonName",
        "primaryInvestType",
        "registerProvince",
        "registerNo",
        "establishDate",
        "registerDate",
    ]  # 定义要取的 value 的 keys
    manager_data_out = pd.DataFrame(big_df)
    manager_data_out = manager_data_out[keys_list]
    manager_data_out.columns = [
        "私募基金管理人名称",
        "法定代表人/执行事务合伙人(委派代表)姓名",
        "机构类型",
        "注册地",
        "登记编号",
        "成立时间",
        "登记时间",
    ]
    manager_data_out["成立时间"] = pd.to_datetime(
        manager_data_out["成立时间"], unit="ms"
    ).dt.date
    manager_data_out["登记时间"] = pd.to_datetime(
        manager_data_out["登记时间"], unit="ms"
    ).dt.date
    return manager_data_out


# 中国证券投资基金业协会-信息公示-私募基金管理人公示-私募基金管理人分类公示
def amac_manager_classify_info() -> pd.DataFrame:
    """
    中国证券投资基金业协会-信息公示-私募基金管理人公示-私募基金管理人分类公示
    https://gs.amac.org.cn/amac-infodisc/res/pof/manager/managerList.html
    :return: 私募基金管理人分类公示
    :rtype: pandas.DataFrame
    """
    url = "https://gs.amac.org.cn/amac-infodisc/api/pof/manager"
    params = {
        "rand": "0.7665138514630696",
        "page": "1",
        "size": "100",
    }
    r = requests.post(url, params=params, json={}, verify=False, headers=headers)
    data_json = r.json()
    total_page = data_json["totalPages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(0, int(total_page)), leave=False):
        params.update({"page": page})
        r = requests.post(url, params=params, json={}, verify=False, headers=headers)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["content"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    keys_list = [
        "managerName",
        "artificialPersonName",
        "primaryInvestType",
        "registerNo",
        "registerProvince",
        "officeAdrAgg",
        "establishDate",
        "registerDate",
        "fundCount",
        "memberType",
        "hasSpecialTips",
        "hasCreditTips",
    ]  # 定义要取的 value 的 keys
    manager_data_out = pd.DataFrame(big_df)
    manager_data_out = manager_data_out[keys_list]
    manager_data_out.columns = [
        "私募基金管理人名称",
        "法定代表人/执行事务合伙人(委派代表)姓名",
        "机构类型",
        "登记编号",
        "注册地",
        "办公地",
        "成立时间",
        "登记时间",
        "在管基金数量",
        "会员类型",
        "是否有提示信息",
        "是否有诚信信息",
    ]
    manager_data_out["成立时间"] = pd.to_datetime(
        manager_data_out["成立时间"], unit="ms"
    ).dt.date
    manager_data_out["登记时间"] = pd.to_datetime(
        manager_data_out["登记时间"], unit="ms"
    ).dt.date
    manager_data_out["在管基金数量"] = pd.to_numeric(manager_data_out["在管基金数量"])
    manager_data_out["是否有提示信息"] = manager_data_out["是否有提示信息"].map(
        {True: "是", False: "否"}
    )
    manager_data_out["是否有诚信信息"] = manager_data_out["是否有诚信信息"].map(
        {True: "是", False: "否"}
    )
    return manager_data_out


# 中国证券投资基金业协会-信息公示-私募基金管理人公示-证券公司私募基金子公司管理人信息公示
def amac_member_sub_info() -> pd.DataFrame:
    """
    中国证券投资基金业协会-信息公示-私募基金管理人公示-证券公司私募基金子公司管理人信息公示
    https://gs.amac.org.cn/amac-infodisc/res/pof/member/index.html?primaryInvestType=private
    :return: 证券公司私募基金子公司管理人信息公示
    :rtype: pandas.DataFrame
    """
    url = "https://gs.amac.org.cn/amac-infodisc/api/pof/pofMember"
    params = {
        "rand": "0.7665138514630696",
        "page": "1",
        "size": "100",
    }
    r = requests.post(url, params=params, json={}, verify=False, headers=headers)
    data_json = r.json()
    total_page = data_json["totalPages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(0, int(total_page)), leave=False):
        params.update({"page": page})
        r = requests.post(url, params=params, json={}, verify=False, headers=headers)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["content"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    keys_list = [
        "managerName",
        "memberBehalf",
        "memberType",
        "memberCode",
        "memberDate",
        "primaryInvestType",
    ]  # 定义要取的 value 的 keys
    manager_data_out = pd.DataFrame(big_df)
    manager_data_out = manager_data_out[keys_list]
    manager_data_out.columns = [
        "机构（会员）名称",
        "会员代表",
        "会员类型",
        "会员编号",
        "入会时间",
        "公司类型",
    ]
    manager_data_out["入会时间"] = pd.to_datetime(
        manager_data_out["入会时间"], unit="ms"
    ).dt.date
    return manager_data_out


# 中国证券投资基金业协会-信息公示-基金产品
# 中国证券投资基金业协会-信息公示-基金产品-私募基金管理人基金产品
def amac_fund_info(start_page: str = "1", end_page: str = "2000") -> pd.DataFrame:
    """
    中国证券投资基金业协会-信息公示-基金产品-私募基金管理人基金产品
    https://gs.amac.org.cn/amac-infodisc/res/pof/fund/index.html
    :param start_page: 开始页码, 获取指定页码直接的数据
    :type start_page: str
    :param end_page: 结束页码, 获取指定页码直接的数据
    :type end_page: str
    :return: 私募基金管理人基金产品
    :rtype: pandas.DataFrame
    """
    url = "https://gs.amac.org.cn/amac-infodisc/api/pof/fund"
    params = {
        "rand": "0.7665138514630696",
        "page": "1",
        "size": "100",
    }
    r = requests.post(url, params=params, json={}, verify=False, headers=headers)
    data_json = r.json()
    total_page = int(data_json["totalPages"])
    if total_page > int(end_page):
        real_end_page = int(end_page)
    else:
        real_end_page = total_page
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(int(start_page) - 1, real_end_page), leave=False):
        params.update({"page": page})
        r = requests.post(url, params=params, json={}, verify=False, headers=headers)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["content"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    keys_list = [
        "fundName",
        "managerName",
        "managerType",
        "workingState",
        "putOnRecordDate",
        "establishDate",
        "mandatorName",
    ]  # 定义要取的 value 的 keys
    manager_data_out = big_df[keys_list].copy()
    manager_data_out.columns = [
        "基金名称",
        "私募基金管理人名称",
        "私募基金管理人类型",
        "运行状态",
        "备案时间",
        "建立时间",
        "托管人名称",
    ]
    manager_data_out["建立时间"] = pd.to_datetime(
        manager_data_out["建立时间"], unit="ms"
    ).dt.date
    manager_data_out["备案时间"] = pd.to_datetime(
        manager_data_out["备案时间"], unit="ms"
    ).dt.date
    return manager_data_out


# 中国证券投资基金业协会-信息公示-基金产品-证券公司集合资管产品公示
def amac_securities_info() -> pd.DataFrame:
    """
    中国证券投资基金业协会-信息公示-基金产品公示-证券公司集合资管产品公示
    https://gs.amac.org.cn/amac-infodisc/res/pof/securities/index.html
    :return: 证券公司集合资管产品公示
    :rtype: pandas.DataFrame
    """
    url = "https://gs.amac.org.cn/amac-infodisc/api/pof/securities"
    params = {
        "rand": "0.7665138514630696",
        "page": "1",
        "size": "100",
    }
    r = requests.post(url, params=params, json={}, verify=False, headers=headers)
    data_json = r.json()
    total_page = data_json["totalPages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(0, int(total_page)), leave=False):
        params.update({"page": page})
        r = requests.post(url, params=params, json={}, verify=False, headers=headers)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["content"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    keys_list = [
        "cpmc",
        "cpbm",
        "gljg",
        "slrq",
        "dqr",
        "tzlx",
        "sffj",
        "tgjg",
        "barq",
        "yzzt",
    ]  # 定义要取的 value 的 keys
    manager_data_out = pd.DataFrame(big_df)
    manager_data_out = manager_data_out[keys_list]
    manager_data_out.columns = [
        "产品名称",
        "产品编码",
        "管理人名称",
        "成立日期",
        "到期时间",
        "投资类型",
        "是否分级",
        "托管人名称",
        "备案日期",
        "运作状态",
    ]
    return manager_data_out


# 中国证券投资基金业协会-信息公示-基金产品-证券公司直投基金
def amac_aoin_info() -> pd.DataFrame:
    """
    中国证券投资基金业协会-信息公示-基金产品公示-证券公司直投基金
    https://gs.amac.org.cn/amac-infodisc/res/aoin/product/index.html
    :return: 证券公司直投基金
    :rtype: pandas.DataFrame
    """
    url = "https://gs.amac.org.cn/amac-infodisc/api/aoin/product"
    params = {
        "rand": "0.7665138514630696",
        "page": "1",
        "size": "100",
    }
    r = requests.post(url, params=params, json={}, verify=False, headers=headers)
    data_json = r.json()
    total_page = data_json["totalPages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(0, int(total_page)), leave=False):
        params.update({"page": page})
        r = requests.post(url, params=params, json={}, verify=False, headers=headers)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["content"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    keys_list = [
        "code",
        "name",
        "aoinName",
        "managerName",
        "createDate",
    ]  # 定义要取的 value 的 keys
    manager_data_out = pd.DataFrame(big_df)
    manager_data_out = manager_data_out[keys_list]
    manager_data_out.columns = [
        "产品编码",
        "产品名称",
        "直投子公司",
        "管理机构",
        "设立日期",
    ]
    manager_data_out["设立日期"] = pd.to_datetime(
        manager_data_out["设立日期"], unit="ms"
    ).dt.date
    return manager_data_out


# 中国证券投资基金业协会-信息公示-基金产品公示-证券公司私募投资基金
def amac_fund_sub_info() -> pd.DataFrame:
    """
    中国证券投资基金业协会-信息公示-基金产品公示-证券公司私募投资基金
    https://gs.amac.org.cn/amac-infodisc/res/pof/subfund/index.html
    :return: 证券公司私募投资基金
    :rtype: pandas.DataFrame
    """
    url = "https://gs.amac.org.cn/amac-infodisc/api/pof/subfund"
    params = {
        "rand": "0.7665138514630696",
        "page": "1",
        "size": "100",
    }
    r = requests.post(url, params=params, json={}, verify=False, headers=headers)
    data_json = r.json()
    total_page = data_json["totalPages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(0, int(total_page)), leave=False):
        params.update({"page": page})
        r = requests.post(url, params=params, json={}, verify=False, headers=headers)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["content"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    keys_list = [
        "productCode",
        "productName",
        "mgrName",
        "trustee",
        "foundDate",
        "registeredDate",
    ]  # 定义要取的 value 的 keys
    manager_data_out = pd.DataFrame(big_df)
    manager_data_out = manager_data_out[keys_list]
    manager_data_out.columns = [
        "产品编码",
        "产品名称",
        "私募基金管理人名称",
        "托管人名称",
        "成立日期",
        "备案日期",
    ]
    manager_data_out["备案日期"] = pd.to_datetime(
        manager_data_out["备案日期"], unit="ms"
    ).dt.date
    manager_data_out["成立日期"] = pd.to_datetime(
        manager_data_out["成立日期"], unit="ms"
    ).dt.date
    return manager_data_out


# 中国证券投资基金业协会-信息公示-基金产品公示-基金公司及子公司集合资管产品公示
def amac_fund_account_info() -> pd.DataFrame:
    """
    中国证券投资基金业协会-信息公示-基金产品公示-基金公司及子公司集合资管产品公示
    https://gs.amac.org.cn/amac-infodisc/res/fund/account/index.html
    :return: 基金公司及子公司集合资管产品公示
    :rtype: pandas.DataFrame
    """
    import warnings

    warnings.filterwarnings(action="ignore", category=FutureWarning)

    url = "https://gs.amac.org.cn/amac-infodisc/api/fund/account"
    params = {
        "rand": "0.7665138514630696",
        "page": "1",
        "size": "100",
    }
    r = requests.post(url, params=params, json={}, verify=False, headers=headers)
    data_json = r.json()
    total_page = data_json["totalPages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(0, int(total_page)), leave=False):
        params.update({"page": page})
        r = requests.post(url, params=params, json={}, verify=False, headers=headers)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["content"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    keys_list = [
        "registerDate",
        "registerCode",
        "name",
        "manager",
    ]  # 定义要取的 value 的 keys
    manager_data_out = pd.DataFrame(big_df)
    manager_data_out = manager_data_out[keys_list]
    manager_data_out.columns = [
        "成立日期",
        "产品编码",
        "产品名称",
        "管理人名称",
    ]
    manager_data_out["成立日期"] = pd.to_datetime(
        manager_data_out["成立日期"], unit="ms"
    ).dt.date
    return manager_data_out


# 中国证券投资基金业协会-信息公示-基金产品公示-资产支持专项计划
def amac_fund_abs() -> pd.DataFrame:
    """
    中国证券投资基金业协会-信息公示-基金产品公示-资产支持专项计划公示信息
    https://gs.amac.org.cn/amac-infodisc/res/fund/abs/index.html
    :return: 资产支持专项计划公示信息
    :rtype: pandas.DataFrame
    """
    url = "https://gs.amac.org.cn/amac-infodisc/api/fund/abs"
    params = {
        "rand": "0.7665138514630696",
        "page": "1",
        "size": "100",
    }
    r = requests.post(url, params=params, json={}, verify=False, headers=headers)
    data_json = r.json()
    total_page = data_json["totalPages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(0, int(total_page)), leave=False):
        params.update({"page": page})
        r = requests.post(url, params=params, json={}, verify=False, headers=headers)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["content"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    big_df.reset_index(inplace=True)
    big_df["index"] = range(1, len(big_df) + 1)
    big_df.columns = [
        "编号",
        "_",
        "_",
        "专项计划全称",
        "备案编号",
        "管理人",
        "托管人",
        "备案通过时间",
        "成立日期",
        "预期到期时间",
    ]
    big_df["备案通过时间"] = pd.to_datetime(big_df["备案通过时间"], unit="ms").dt.date
    big_df["成立日期"] = pd.to_datetime(big_df["成立日期"], unit="ms").dt.date
    big_df["预期到期时间"] = pd.to_datetime(
        big_df["预期到期时间"], unit="ms", errors="coerce"
    ).dt.date
    big_df = big_df[
        [
            "编号",
            "备案编号",
            "专项计划全称",
            "管理人",
            "托管人",
            "成立日期",
            "预期到期时间",
            "备案通过时间",
        ]
    ]
    return big_df


# 中国证券投资基金业协会-信息公示-基金产品公示-期货公司集合资管产品公示
def amac_futures_info() -> pd.DataFrame:
    """
    中国证券投资基金业协会-信息公示-基金产品公示-期货公司集合资管产品公示
    https://gs.amac.org.cn/amac-infodisc/res/pof/futures/index.html
    :return: 期货公司集合资管产品公示
    :rtype: pandas.DataFrame
    """
    url = "https://gs.amac.org.cn/amac-infodisc/api/pof/futures"
    params = {
        "rand": "0.7665138514630696",
        "page": "1",
        "size": "100",
    }
    r = requests.post(url, params=params, json={}, verify=False, headers=headers)
    data_json = r.json()
    total_page = data_json["totalPages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(0, int(total_page)), leave=False):
        params.update({"page": page})
        r = requests.post(url, params=params, json={}, verify=False, headers=headers)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["content"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    keys_list = [
        "mpiName",
        "mpiProductCode",
        "aoiName",
        "mpiTrustee",
        "mpiCreateDate",
        "tzlx",
        "sfjgh",
        "registeredDate",
        "dueDate",
        "fundStatus",
    ]  # 定义要取的 value 的 keys
    manager_data_out = pd.DataFrame(big_df)
    manager_data_out = manager_data_out[keys_list]
    manager_data_out.columns = [
        "产品名称",
        "产品编码",
        "管理人名称",
        "托管人名称",
        "成立日期",
        "投资类型",
        "是否分级",
        "备案日期",
        "到期日",
        "运作状态",
    ]
    return manager_data_out


# 中国证券投资基金业协会-信息公示-诚信信息
# 中国证券投资基金业协会-信息公示-诚信信息-已注销私募基金管理人名单
def amac_manager_cancelled_info() -> pd.DataFrame:
    """
    中国证券投资基金业协会-信息公示-诚信信息公示-已注销私募基金管理人名单
    https://gs.amac.org.cn/amac-infodisc/res/cancelled/manager/index.html
    主动注销: 100
    依公告注销: 200
    协会注销: 300
    :return: 已注销私募基金管理人名单
    :rtype: pandas.DataFrame
    """
    url = "https://gs.amac.org.cn/amac-infodisc/api/cancelled/manager"
    params = {
        "rand": "0.7665138514630696",
        "page": "1",
        "size": "100",
    }
    r = requests.post(url, params=params, json={}, verify=False, headers=headers)
    data_json = r.json()
    total_page = data_json["totalPages"]
    big_df = pd.DataFrame()
    tqdm = get_tqdm()
    for page in tqdm(range(0, int(total_page)), leave=False):
        params.update({"page": page})
        r = requests.post(url, params=params, json={}, verify=False, headers=headers)
        data_json = r.json()
        temp_df = pd.DataFrame(data_json["content"])
        big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
    keys_list = [
        "orgName",
        "orgCode",
        "orgSignDate",
        "cancelDate",
        "status",
    ]  # 定义要取的 value 的 keys
    manager_data_out = pd.DataFrame(big_df)
    manager_data_out = manager_data_out[keys_list]
    manager_data_out.columns = [
        "管理人名称",
        "统一社会信用代码",
        "登记时间",
        "注销时间",
        "注销类型",
    ]
    manager_data_out["登记时间"] = pd.to_datetime(
        manager_data_out["登记时间"], unit="ms"
    ).dt.date
    manager_data_out["注销时间"] = pd.to_datetime(
        manager_data_out["注销时间"], unit="ms"
    ).dt.date
    manager_data_out.sort_values(["注销时间"], ignore_index=True, inplace=True)
    return manager_data_out


if __name__ == "__main__":
    # 中国证券投资基金业协会-信息公示-会员信息
    # 中国证券投资基金业协会-信息公示-会员信息-会员机构综合查询
    amac_member_info_df = amac_member_info()
    print(amac_member_info_df)

    # 中国证券投资基金业协会-信息公示-从业人员信息
    # 中国证券投资基金业协会-信息公示-从业人员信息-基金从业人员资格注册信息
    amac_person_fund_org_list_df = amac_person_fund_org_list(symbol="公募基金管理公司")
    print(amac_person_fund_org_list_df)

    # 中国证券投资基金业协会-信息公示-从业人员信息
    # 中国证券投资基金业协会-信息公示-从业人员信息-债券投资交易相关人员公示
    amac_person_bond_org_list_df = amac_person_bond_org_list()
    print(amac_person_bond_org_list_df)

    # 中国证券投资基金业协会-信息公示-私募基金管理人公示
    # 中国证券投资基金业协会-信息公示-私募基金管理人公示-私募基金管理人综合查询
    amac_manager_info_df = amac_manager_info()
    print(amac_manager_info_df)

    # 中国证券投资基金业协会-信息公示-私募基金管理人公示-私募基金管理人分类公示
    amac_manager_classify_info_df = amac_manager_classify_info()
    print(amac_manager_classify_info_df)

    # 中国证券投资基金业协会-信息公示-私募基金管理人公示-证券公司私募基金子公司管理人信息公示
    amac_member_sub_info_df = amac_member_sub_info()
    print(amac_member_sub_info_df)

    # 中国证券投资基金业协会-信息公示-基金产品
    # 中国证券投资基金业协会-信息公示-基金产品-私募基金管理人基金产品
    amac_fund_info_df = amac_fund_info(start_page="1", end_page="100")
    print(amac_fund_info_df)

    example_df = amac_fund_info_df[
        amac_fund_info_df["私募基金管理人名称"].str.contains("聚宽")
    ]
    print(example_df)

    # 中国证券投资基金业协会-信息公示-基金产品-证券公司集合资管产品公示
    amac_securities_info_df = amac_securities_info()
    print(amac_securities_info_df)

    # 中国证券投资基金业协会-信息公示-基金产品-证券公司直投基金
    amac_aoin_info_df = amac_aoin_info()
    print(amac_aoin_info_df)

    # 中国证券投资基金业协会-信息公示-基金产品公示-证券公司私募投资基金
    amac_fund_sub_info_df = amac_fund_sub_info()
    print(amac_fund_sub_info_df)

    # 中国证券投资基金业协会-信息公示-基金产品公示-基金公司及子公司集合资管产品公示
    amac_fund_account_info_df = amac_fund_account_info()
    print(amac_fund_account_info_df)

    # 中国证券投资基金业协会-信息公示-基金产品公示-资产支持专项计划
    amac_fund_abs_df = amac_fund_abs()
    print(amac_fund_abs_df)

    # 中国证券投资基金业协会-信息公示-基金产品公示-期货公司集合资管产品公示
    amac_futures_info_df = amac_futures_info()
    print(amac_futures_info_df)

    # 中国证券投资基金业协会-信息公示-诚信信息
    # 中国证券投资基金业协会-信息公示-诚信信息-已注销私募基金管理人名单
    amac_manager_cancelled_info_df = amac_manager_cancelled_info()
    print(amac_manager_cancelled_info_df)
