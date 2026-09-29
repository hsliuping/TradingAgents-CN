"""issue #785 修复回归测试：「填 Key → 拉模型 → 勾选导入」

背景：issue #785 要求把「厂家管理 → 模型目录 → 大模型配置」三页面流程简化为
一次操作。修复过程中发现三个独立 bug 会让新接入的模型在分析页下拉框里永远不出现：

Bug #1 —— `_filter_popular_models` 有厂商白名单，非 OpenAI/Anthropic/Google 的模型
         全部被丢弃（本地真机验证：9 个 sensenova 模型 → 0 保留）。
Bug #2 —— `GET /api/config/llm` 丢弃无 API Key 的模型（34/35 个配置不可见）。
         该分支依赖 has_valid_api_key()，与 Bug #1 是两条独立路径，本次未改。
Bug #3 —— `batch_import_llm_configs` 对无法识别的模型默认 capability_level=5（旗舰），
         让新厂商模型被误推荐为主力。应兜底到 2（标准）。

本文件只测纯函数（无需 DB / 网络），因此可在无 MongoDB 的环境直接运行。
"""

import pytest

from app.services.config_service import ConfigService


@pytest.fixture
def svc():
    """只实例化用于调用纯函数；这些方法不访问 self 的 DB 连接。"""
    return ConfigService.__new__(ConfigService)


# ---------------------------------------------------------------------------
# Bug #1：_filter_popular_models 不能按厂商歧视模型
# ---------------------------------------------------------------------------

class TestFilterPopularModels:
    def test_real_sensenova_models_all_survive(self, svc):
        """本地真机拉取的 9 个 sensenova 模型必须全部保留。

        旧代码对这批模型保留 0 个 —— 这正是 issue #785 报「配好的模型下拉框里没有」
        的直接原因。
        """
        real_models = [
            {"id": "sensenova-6.8-flash-lite", "name": "sensenova-6.8-flash-lite"},
            {"id": "deepseek-v4-flash", "name": "deepseek-v4-flash"},
            {"id": "deepseek-v4-pro", "name": "deepseek-v4-pro"},
            {"id": "deepseek-flash", "name": "deepseek-flash"},
            {"id": "deepseek-v4.1-flash", "name": "deepseek-v4.1-flash"},
            {"id": "kimi-k3", "name": "kimi-k3"},
            {"id": "glm-5.2", "name": "glm-5.2"},
            {"id": "sensenova-u1.5-lite", "name": "sensenova-u1.5-lite"},
            {"id": "sensenova-u1-fast", "name": "sensenova-u1-fast"},
        ]
        kept = svc._filter_popular_models(real_models, "sensenova")
        kept_ids = {m["id"] for m in kept}
        assert kept_ids == {m["id"] for m in real_models}, (
            f"非主流厂商模型被错误丢弃：保留了 {kept_ids}"
        )

    def test_no_vendor_whitelist(self, svc):
        """厂商名不应决定模型是否保留。

        doubao / ep- 是腾讯混元的渠道前缀，kimi / glm 是月之暗面与智谱，
        都曾经是「白名单之外 = 全丢」。
        """
        models = [
            {"id": "kimi-k3", "name": "kimi-k3"},
            {"id": "glm-5.2", "name": "glm-5.2"},
            {"id": "doubao-seed-1.6", "name": "doubao-seed-1.6"},
            {"id": "ep-xxxx-yyy", "name": "ep-xxxx-yyy"},
        ]
        kept = {m["id"] for m in svc._filter_popular_models(models, "some-vendor")}
        assert kept == {m["id"] for m in models}

    def test_deepspeed_v4_1_flash_not_false_positive(self, svc):
        """版本号里的 `.1` 不应触发任何过滤（历史误报点）。"""
        models = [{"id": "deepseek-v4.1-flash", "name": "deepseek-v4.1-flash"}]
        kept = svc._filter_popular_models(models, "sensetime")
        assert len(kept) == 1

    def test_preview_variant_still_excluded(self, svc):
        """preview 变体仍应被剔除 —— 过滤逻辑不是「全放行」。"""
        models = [
            {"id": "kimi-k2-preview", "name": "kimi-k2-preview"},
            {"id": "gpt-4-mini-preview", "name": "gpt-4-mini-preview"},
            {"id": "my-model:alpha", "name": "my-model:alpha"},
            {"id": "my-model_beta", "name": "my-model_beta"},
        ]
        kept = {m["id"] for m in svc._filter_popular_models(models, "mixed")}
        assert kept == set(), f"preview/alpha/beta 变体应被剔除，实际保留 {kept}"

    def test_dated_snapshot_still_excluded(self, svc):
        """按日期快照命名的模型仍应被剔除。

        只认「完整」日期：带横线的 YYYY-MM-DD，或结尾 8 位 YYYYMMDD。
        缩写日期（如 250228）不算快照，会保留 —— 这是刻意行为，见实现注释。
        """
        models = [
            {"id": "glm-4.6-2025-02-28", "name": "glm-4.6-2025-02-28"},
            {"id": "deepseek-v3-20250228", "name": "deepseek-v3-20250228"},
            {"id": "qwen3-2025-04-08", "name": "qwen3-2025-04-08"},
            {"id": "glm-4.6-250228", "name": "glm-4.6-250228"},  # 6 位缩写日期：保留
            {"id": "glm-4.6", "name": "glm-4.6"},                 # 正式版：保留
        ]
        kept = {m["id"] for m in svc._filter_popular_models(models, "mixed")}
        assert kept == {"glm-4.6", "glm-4.6-250228"}, f"实际 {kept}"

    def test_function_tag_still_excluded(self, svc):
        """online / free / extended / instruct 等功能变体仍应被剔除。"""
        models = [
            {"id": "glm-4.5-online", "name": "glm-4.5-online"},
            {"id": "deepseek-v3/free", "name": "deepseek-v3/free"},
            {"id": "deepseek-v4-extended", "name": "deepseek-v4-extended"},
            {"id": "qwen3-instruct", "name": "qwen3-instruct"},
        ]
        kept = svc._filter_popular_models(models, "mixed")
        assert kept == [], f"功能变体应剔除，实际保留 {{m['id'] for m in kept}}"

    def test_function_tag_does_not_false_positive(self, svc):
        """功能标签必须紧跟分隔符或行首，不能把正常模型名里的普通单词误判。

        pretrained 历史上曾被 exp 别名误伤（pretrained 里的 exp 匹配 \b），已修。
        """
        models = [
            {"id": "deepseek-v4-flash", "name": "deepseek-v4-flash"},        # flash 不是标签
            {"id": "sensenova-6.8-flash-lite", "name": "sensenova-6.8-flash-lite"},
            {"id": "glm-4.6", "name": "glm-4.6"},
            {"id": "pretrained-1b", "name": "pretrained-1b"},                # exp 别名已删除
        ]
        kept = {m["id"] for m in svc._filter_popular_models(models, "mixed")}
        assert kept == {m["id"] for m in models}

    def test_empty_and_none_inputs(self, svc):
        """空列表 / None 不能抛异常。"""
        assert svc._filter_popular_models([], "x") == []
        assert svc._filter_popular_models(None, "x") == []
