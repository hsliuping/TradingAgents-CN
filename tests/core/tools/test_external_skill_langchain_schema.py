from core.tools.config import ToolCategory, ToolMetadata, ToolParameter
from core.tools.registry import ToolRegistry


def test_generated_external_skill_uses_parameter_schema_for_dict_invoke():
    registry = ToolRegistry()
    tool_id = "test_external_dupont_schema"

    def external_skill_wrapper(**kwargs):
        symbol = kwargs["symbol"]
        periods = kwargs.get("periods", 8)
        return f"symbol={symbol},periods={periods}"

    metadata = ToolMetadata(
        id=tool_id,
        name="测试外部 Skill",
        description="验证外部 Skill 的参数 schema",
        category=ToolCategory.EXTERNAL,
        source="generated",
        parameters=[
            ToolParameter(name="symbol", type="string", description="股票代码", required=True),
            ToolParameter(name="periods", type="integer", description="期数", required=False, default=8),
        ],
    )

    registry.register(metadata, override=True)
    registry.register_function(
        tool_id=tool_id,
        func=external_skill_wrapper,
        name="测试外部 Skill",
        category="external",
        description="验证外部 Skill 的参数 schema",
        override=True,
        parameters=metadata.parameters,
    )
    registry._tools[tool_id].source = "generated"

    try:
        tool = registry.get_langchain_tool(tool_id)

        assert tool is not None
        result = tool.invoke({"symbol": "002594"})

        assert result == "symbol=002594,periods=8"
        assert tool.args_schema is not None
        schema_fields = tool.args_schema.model_fields
        assert "symbol" in schema_fields
        assert "periods" in schema_fields
    finally:
        registry.unregister(tool_id)