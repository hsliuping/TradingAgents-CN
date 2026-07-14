# 历史遗留测试归档（2026-06-14 整理）

## 为什么归档

2026-06-14 整理 `tests/` 目录时，发现根目录堆了 251+ 个散落文件：

- `test_*.py`（功能验证后没清理）
- `debug_*.py`（调试脚本）
- `quick_*.py`（快速验证）
- `simple_*.py` / `analyze_*.py` / `check_*.py`（一次性脚本）
- `tests/0.1.14/` 子目录（历史版本）

这些文件**没有删除**而是归档到此目录，**理由**：

1. git history 仍可追溯
2. 半年后无引用即可从 `_archive/` 删除（更彻底的清理）
3. pytest 已配置为忽略此目录（`pytest.ini` 加了 `--ignore=tests/_archive`）

## 重命名规则

- `tests/0.1.14/test_*.py` → `tests/_archive/legacy_2026-06-14/test_*_v0.1.14.py`（避免与根目录 `test_*.py` 同名冲突）
- 其他文件保持原名归档

## 文件清单

- 总数：约 296 个
- 类型：单元/集成/调试/quick 脚本混合

## 恢复单个文件

如需恢复某个具体文件：

```bash
git mv tests/_archive/legacy_2026-06-14/<file>.py tests/<目标路径>/
```

## 彻底删除

如确认可删除整个归档：

```bash
git rm -r tests/_archive/legacy_2026-06-14/
```

**警告**：删除前请确认无下游依赖（CI、文档、scripts 等）。
