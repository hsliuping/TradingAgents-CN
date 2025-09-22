#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Date: 2024/4/25 17:20
Desc: 河北省空气质量预报信息发布系统
https://110.249.223.67/publish
每日 17 时发布
等级划分
1. 空气污染指数为0－50，空气质量级别为一级，空气质量状况属于优。此时，空气质量令人满意，基本无空气污染，各类人群可正常活动。
2. 空气污染指数为51－100，空气质量级别为二级，空气质量状况属于良。此时空气质量可接受，但某些污染物可能对极少数异常敏感人群健康有较弱影响，建议极少数异常敏感人群应减少户外活动。
3. 空气污染指数为101－150，空气质量级别为三级，空气质量状况属于轻度污染。此时，易感人群症状有轻度加剧，健康人群出现刺激症状。建议儿童、老年人及心脏病、呼吸系统疾病患者应减少长时间、高强度的户外锻炼。
4. 空气污染指数为151－200，空气质量级别为四级，空气质量状况属于中度污染。此时，进一步加剧易感人群症状，可能对健康人群心脏、呼吸系统有影响，建议疾病患者避免长时间、高强度的户外锻练，一般人群适量减少户外运动。
5. 空气污染指数为201－300，空气质量级别为五级，空气质量状况属于重度污染。此时，心脏病和肺病患者症状显著加剧，运动耐受力降低，健康人群普遍出现症状，建议儿童、老年人和心脏病、肺病患者应停留在室内，停止户外运动，一般人群减少户外运动。
6. 空气污染指数大于300，空气质量级别为六级，空气质量状况属于严重污染。此时，健康人群运动耐受力降低，有明显强烈症状，提前出现某些疾病，建议儿童、老年人和病人应当留在室内，避免体力消耗，一般人群应避免户外活动。
发布单位：河北省环境应急与重污染天气预警中心 技术支持：中国科学院大气物理研究所 中科三清科技有限公司
"""

import pandas as pd
import requests
from bs4 import BeautifulSoup


def air_quality_hebei() -> pd.DataFrame:
    """
    河北省空气质量预报信息发布系统-空气质量预报, 未来 6 天
    http://218.11.10.130:8080/#/application/home
    :return: city = "", 返回所有地区的数据; city="唐山市", 返回唐山市的数据
    :rtype: pandas.DataFrame
    """
    url = "http://218.11.10.130:8080/api/hour/130000.xml"
    r = requests.get(url)
    soup = BeautifulSoup(r.content, features="xml")
    data = []
    cities = soup.find_all("City")
    for city in cities:
        pointers = city.find_all("Pointer")
        for pointer in pointers:
            row = {
                "City": city.Name.text if city.Name else None,
                "Region": pointer.Region.text if pointer.Region else None,
                "Station": pointer.Name.text if pointer.Name else None,
                "DateTime": pointer.DataTime.text if pointer.DataTime else None,
                "AQI": pointer.AQI.text if pointer.AQI else None,
                "Level": pointer.Level.text if pointer.Level else None,
                "MaxPoll": pointer.MaxPoll.text if pointer.MaxPoll else None,
                "Longitude": pointer.CLng.text if pointer.CLng else None,
                "Latitude": pointer.CLat.text if pointer.CLat else None,
            }
            polls = pointer.find_all("Poll")
            for poll in polls:
                poll_name = poll.Name.text if poll.Name else None
                poll_value = poll.Value.text if poll.Value else None
                row[f"{poll_name}_Value"] = poll_value
                row[f"{poll_name}_IAQI"] = poll.IAQI.text if poll.IAQI else None
            data.append(row)

    df = pd.DataFrame(data)
    numeric_columns = ["AQI", "Longitude", "Latitude"] + [
        col for col in df.columns if col.endswith("_Value") or col.endswith("_IAQI")
    ]
    for col in numeric_columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    column_names = {
        "City": "城市",
        "Region": "区域",
        "Station": "监测点",
        "DateTime": "时间",
        "Level": "空气质量等级",
        "MaxPoll": "首要污染物",
        "Longitude": "经度",
        "Latitude": "纬度",
        "SO2_Value": "二氧化硫_浓度",
        "SO2_IAQI": "二氧化硫_IAQI",
        "CO_Value": "一氧化碳_浓度",
        "CO_IAQI": "一氧化碳_IAQI",
        "NO2_Value": "二氧化氮_浓度",
        "NO2_IAQI": "二氧化氮_IAQI",
        "O3-1H_Value": "臭氧1小时_浓度",
        "O3-1H_IAQI": "臭氧1小时_IAQI",
        "O3-8H_Value": "臭氧8小时_浓度",
        "O3-8H_IAQI": "臭氧8小时_IAQI",
        "PM2.5_Value": "PM2.5_浓度",
        "PM2.5_IAQI": "PM2.5_IAQI",
        "PM10_Value": "PM10_浓度",
        "PM10_IAQI": "PM10_IAQI",
    }
    df = df.rename(columns=column_names)
    basic_columns = [
        "城市",
        "区域",
        "监测点",
        "时间",
        "AQI",
        "空气质量等级",
        "首要污染物",
        "经度",
        "纬度",
    ]
    pollutant_columns = [col for col in df.columns if col not in basic_columns]
    df = df[basic_columns + sorted(pollutant_columns)]
    return df


if __name__ == "__main__":
    air_quality_hebei_df = air_quality_hebei()
    print(air_quality_hebei_df)
