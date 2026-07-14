# TradingAgents-CN 测试目录

## 目录结构（2026-06-14 整理后）

```
tests/
├── README.md                          # 本文件
├── __init__.py
├── conftest.py
├── pytest.ini
│
├── _archive/legacy_2026-06-14/        # 历史遗留（296 个文件，不参与 pytest）
│   └── README.md                      # 归档说明
│
├── _scratch/                          # 临时调试脚本（不删除，可重跑）
│   └── .gitkeep
│
├── config/                            # 配置相关单元测试
├── dataflows/                         # 数据流单元测试
├── integration/                       # 集成测试（默认 pytest 跳过，需 -m integration）
├── middleware/                        # 中间件单元测试
├── services/                          # 服务层单元测试
├── system/                            # 系统级单元测试
├── tradingagents/                     # tradingagents 模块单元测试
├── unit/                              # 通用单元测试
│
└── test_tushare_unified/              # Tushare 集成测试（已组织）
```

## 整理背景

- 旧版 `tests/` 根目录堆了 251+ 个散落的 `test_*.py` / `debug_*.py` / `quick_*.py`
- `tests/0.1.14/` 子目录是历史版本归档
- 这些**已不需要**的测试**没有删除**，而是归档到 `tests/_archive/legacy_2026-06-14/`
- 后续可在适当时机从 `_archive/` 删除（建议半年以上无引用再删）

## 跑测试

```bash
# 跑所有非集成测试
pytest tests/

# 跑所有测试（含集成）
pytest tests/ -m ""

# 跑单个测试
pytest tests/config/test_settings.py::TestSettings::test_load -v

# 跑某个子目录
pytest tests/dataflows/ -v
```

## 新增测试规范（详见根目录 CLAUDE.md）

- **禁止**：在项目根目录临时写 `verify_*.py` / `test_*.py` / `debug_*.py` 验证后删除
- **单元测试**：`tests/<模块路径>/test_<被测函数>.py`
- **集成测试**：`tests/integration/test_<场景>.py`
- **临时调试**：`tests/_scratch/<日期>-<描述>.py`（不删除）
- **pytest 不会**扫描 `_archive/` 和 `_scratch/`（已在 `pytest.ini` 配置）
