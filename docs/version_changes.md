# 版本变更记录

## 2025年8月5日 - Google嵌入模型调用修复

**目的:** 解决项目中Google嵌入模型通过`gemini-balance`代理调用失败的问题。

**问题描述:**
在之前的测试中，Google嵌入模型调用（包括OpenAI兼容格式、Google原生API和Google AI Python SDK）均未能成功，主要表现为`404 Not Found`、`405 Method Not Allowed`以及`API key not valid`错误。经过分析，发现问题在于`base_url`和模型名称的配置与`gemini-balance`代理的预期不符。

**解决方案:**
根据用户提供的`gemini-balance`项目中的`embedding_service.py`文件作为参考，我们调整了API调用方式，使其与代理的OpenAI兼容接口匹配。

**具体修改:**

1.  **文件: `test_google_embedding.py`**
    *   **`test_google_embedding_direct`函数:**
        *   **方法1 (OpenAI兼容格式):**
            *   `base_url`从硬编码的Google官方API端点或根URL修改为从环境变量`GOOGLE_BASE_URL`获取，并拼接`/v1/`路径（例如：`https://gemini-balance.neoncdn.dpdns.org/v1/`）。
            *   `model`参数从`embedding-001`或`text-embedding-ada-002`修改为`"text-embedding-004"`，以匹配代理可能期望的模型名称。
        *   **方法2 (Google原生API):** 保持不变。此方法在代理环境下仍返回`404 Not Found`，但由于代理主要支持OpenAI兼容接口，此失败是可接受的。
        *   **方法3 (Google AI Python SDK):** 保持不变。此方法在代理环境下仍返回`API key not valid`，同样是可接受的。

2.  **文件: `tradingagents/agents/utils/memory.py`**
    *   **`FinancialSituationMemory`类的`__init__`方法 (Google提供商配置部分):**
        *   `self.client`的`base_url`修改为从环境变量`GOOGLE_BASE_URL`获取，并拼接`/v1/`路径。
        *   `self.embedding_model`明确设置为`"text-embedding-004"`，确保模型名称的正确性。
    *   **`get_embedding`方法 (Google提供商部分):**
        *   移除了原生的`requests.post`调用，转而使用`self.client.embeddings.create`，与OpenAI兼容接口保持一致。

**测试结果:**
经过上述修改后，重新运行`test_google_embedding.py`，结果如下：
*   `test_google_embedding_direct`函数中的**方法1 (OpenAI兼容格式)** 成功返回了嵌入结果，维度为768。
*   `test_with_memory_module`函数中的**内存模块嵌入**也成功返回了嵌入结果，维度为768。
*   Google原生API和Google AI Python SDK的调用仍然失败，但这符合预期，因为`gemini-balance`代理主要通过OpenAI兼容接口提供服务。

**结论:**
项目现在能够通过`gemini-balance`代理的OpenAI兼容接口成功调用Google嵌入模型，解决了之前的API调用问题。
