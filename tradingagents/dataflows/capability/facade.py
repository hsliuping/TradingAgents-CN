"""数据门面（DataFacade）：能力查询的统一出口

工具层只调本门面，不感知具体数据源：
    df = await get_data_facade().get_capability("margin").query(trade_date="20261023")

调度复用 dataflows DataSourceManager 的数据源优先级配置
（system_configs 同一份配置，不新建第二套）。

降级语义（严格执行，参考 P5 历史教训）：

| 情况                          | 处理                         |
|-------------------------------|------------------------------|
| 异常 / 超时 / 返回 None        | 记录失败，试下一源（请求失败才降级） |
| 成功但数据为空（空 DataFrame）  | 返回空结果，不降级            |
| 成功但缺个别标准字段           | 缺失列填 NaN + quality 标记   |
| 返回 Dict（全标量值，单条聚合） | 包装为单行 DataFrame 后标准化 |
| 返回 Dict（含 list/dict/Series/DataFrame 集合值） | 记录失败，试下一源 |

注意：现有 provider 实现以 None 同时表示"失败"与"成功但无数据"，无法区分。
门面按"失败"处理（降级）。新实现请遵循契约：请求失败/不可用返回 None，
成功但无数据返回空 DataFrame（空数据不降级）。

设计文档：docs/05-design/v4.0/data-architecture-problems-and-optimization.md 5.4
"""

import logging
from typing import Any, Dict, List, Optional

import pandas as pd

from .registry import CapabilityEntry, registry

logger = logging.getLogger(__name__)

def _default_source_order() -> List[str]:
    """兜底顺序：从唯一定义处 DEFAULT_SOURCE_PRIORITY 推导（local 10 / tushare 3 / akshare 2 / baostock 1），
    避免本地镜像常量与唯一事实源漂移。"""
    from tradingagents.dataflows.data_source_manager import DEFAULT_SOURCE_PRIORITY

    return sorted(DEFAULT_SOURCE_PRIORITY, key=DEFAULT_SOURCE_PRIORITY.get, reverse=True)

# 内置 provider 实例工厂（按 source 解析；注册时可显式传 provider_factory 覆盖）
def _tushare_provider():
    from tradingagents.dataflows.providers.china.tushare import get_tushare_provider
    return get_tushare_provider()

def _akshare_provider():
    from tradingagents.dataflows.providers.china.akshare import get_akshare_provider
    return get_akshare_provider()

_PROVIDER_FACTORIES = {
    "tushare": _tushare_provider,
    "akshare": _akshare_provider,
}


class CapabilityHandle:
    """单个数据能力的查询句柄"""

    def __init__(self, capability_id: str):
        self.capability_id = capability_id

    async def query(self, **params) -> pd.DataFrame:
        """
        按数据源优先级查询能力数据。

        Returns:
            DataFrame：Schema 标准字段 + source 列（实际数据来源）+
            quality 列（'ok' 必填字段齐全 / 'partial' 必填字段有缺失）。
            所有数据源均失败时返回空 DataFrame（含标准列结构），并打 warning 日志。
        """
        schema = registry.get_entry(
            self.capability_id, registry.get_sources(self.capability_id)[0]
        ).schema
        out_columns = schema.standard_field_names() + ["source", "quality"]

        self._validate_params(schema, params)

        sources = self._resolve_source_order(registry.get_sources(self.capability_id))
        failures: List[str] = []

        for source in sources:
            entry = registry.get_entry(self.capability_id, source)
            raw = await self._fetch(entry, params)
            if raw is None:
                failures.append(f"{source}: 请求失败或源不可用")
                continue
            # Dict 形状（单条聚合统计）：全标量值时包装为单行 DataFrame 后走标准化；
            # 含集合值说明非单条记录形状，按失败处理
            if isinstance(raw, dict):
                if all(not isinstance(v, (list, dict, pd.Series, pd.DataFrame))
                       for v in raw.values()):
                    raw = pd.DataFrame([raw])
                else:
                    failures.append(f"{source}: 返回 Dict 含集合值，非单条记录形状")
                    continue
            if isinstance(raw, pd.DataFrame) and raw.empty:
                # 成功但无数据：不降级，避免语义漂移
                logger.info(
                    "能力 %s 源 %s 成功返回但无数据，不降级",
                    self.capability_id, source,
                )
                return self._standardize(raw, entry, out_columns)
            if not isinstance(raw, pd.DataFrame):
                failures.append(f"{source}: 返回类型 {type(raw).__name__} 非 DataFrame")
                continue
            return self._standardize(raw, entry, out_columns)

        logger.warning(
            "能力 %s 所有数据源均失败（已尝试 %s）: %s",
            self.capability_id, sources, failures,
        )
        return pd.DataFrame(columns=out_columns)

    async def _fetch(self, entry: CapabilityEntry, params: Dict[str, Any]):
        """调用数据源实现；异常按"请求失败"处理并返回 None 触发降级"""
        try:
            if entry.provider_factory is not None:
                provider = entry.provider_factory()
            else:
                factory = _PROVIDER_FACTORIES.get(entry.source)
                if factory is None:
                    raise ValueError(
                        f"数据源 '{entry.source}' 无内置 provider 工厂，"
                        f"请在注册时显式传 provider_factory"
                    )
                provider = factory()
            return await entry.func(provider, **params)
        except Exception as e:
            logger.warning(
                "能力 %s 源 %s 请求失败: %s", self.capability_id, entry.source, e
            )
            return None

    def _standardize(
        self, raw: pd.DataFrame, entry: CapabilityEntry, out_columns: List[str]
    ) -> pd.DataFrame:
        """字段标准化：按注册映射改名 -> 补齐缺失标准字段(NaN) -> 打 source/quality 标记"""
        df = raw.copy()
        rename = {raw_name: std_name for raw_name, std_name in entry.field_mapping.items()
                  if raw_name in df.columns}
        df = df.rename(columns=rename)

        required = entry.schema.required_field_names()
        for name in entry.schema.standard_field_names():
            if name not in df.columns:
                df[name] = pd.NA

        if df.empty:
            df["source"] = entry.source
            df["quality"] = pd.NA
        else:
            df["source"] = entry.source
            missing_required = df[required].isna().any(axis=1) if required else False
            df["quality"] = missing_required.map({True: "partial", False: "ok"})
        return df[out_columns]

    def _validate_params(self, schema, params: Dict[str, Any]) -> None:
        allowed = {p.name for p in schema.params}
        unknown = set(params) - allowed
        if unknown:
            raise ValueError(
                f"能力 '{self.capability_id}' 不支持查询参数 {sorted(unknown)}，"
                f"标准参数: {sorted(allowed)}"
            )

    def _resolve_source_order(self, registered: List[str]) -> List[str]:
        """复用 dataflows 管理器的优先级配置（system_configs），过滤到已注册数据源"""
        try:
            from tradingagents.dataflows.data_source_manager import get_data_source_manager
            manager = get_data_source_manager()
            # 跨包消费走公开方法 get_data_source_priority_order（读取 system_configs 数据源优先级）
            # ChinaDataSource.value 是 DataSourceCode 枚举成员，需再解一层取原始字符串
            order = []
            for s in manager.get_data_source_priority_order():
                v = getattr(s, "value", s)
                v = getattr(v, "value", v)
                order.append(str(v))
        except Exception as e:
            logger.warning(
                "能力 %s 读取数据源优先级配置失败: %s，使用默认顺序", self.capability_id, e
            )
            order = _default_source_order()

        ordered = [s for s in order if s in registered]
        # 已注册但配置未提及的源排在最后（注册顺序），保证不会被静默忽略
        ordered += [s for s in registered if s not in ordered]
        return ordered


class DataFacade:
    """数据门面：数据能力的统一查询入口"""

    def get_capability(self, capability_id: str) -> CapabilityHandle:
        if not registry.get_sources(capability_id):
            raise ValueError(f"数据能力 '{capability_id}' 尚无任何数据源注册")
        return CapabilityHandle(capability_id)

    def list_capabilities(self) -> List[str]:
        return registry.list_capabilities()


_facade = DataFacade()


def get_data_facade() -> DataFacade:
    return _facade
