#!/usr/bin/env python3
"""
测试 Ollama API 连接

用于验证本地 Ollama 服务的 OpenAI 兼容端点是否正常工作
"""

import requests
import json
import sys
from typing import Dict, Any

def test_ollama_base():
    """测试 Ollama 基础服务是否运行"""
    print("=" * 60)
    print("测试 1: 检查 Ollama 基础服务")
    print("=" * 60)
    
    try:
        response = requests.get("http://localhost:11434", timeout=5)
        print(f"✅ Ollama 服务运行中")
        print(f"   状态码: {response.status_code}")
        print(f"   响应: {response.text[:100]}")
        return True
    except requests.exceptions.ConnectionError:
        print("❌ Ollama 服务未运行，请先启动 Ollama")
        print("   启动方法: 运行 `ollama serve` 或启动 Ollama 应用")
        return False
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return False

def test_ollama_models():
    """测试获取模型列表"""
    print("\n" + "=" * 60)
    print("测试 2: 获取模型列表")
    print("=" * 60)
    
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            data = response.json()
            models = data.get("models", [])
            print(f"✅ 找到 {len(models)} 个模型:")
            for model in models:
                name = model.get("name", "未知")
                size = model.get("size", 0)
                size_gb = size / (1024**3) if size > 0 else 0
                print(f"   - {name} ({size_gb:.2f} GB)")
            return [m.get("name", "").split(":")[0] for m in models]
        else:
            print(f"❌ 获取模型列表失败: HTTP {response.status_code}")
            return []
    except Exception as e:
        print(f"❌ 获取模型列表失败: {e}")
        return []

def test_openai_compatible_endpoint(model_name: str):
    """测试 OpenAI 兼容端点"""
    print("\n" + "=" * 60)
    print(f"测试 3: 测试 OpenAI 兼容端点 (模型: {model_name})")
    print("=" * 60)
    
    url = "http://localhost:11434/v1/chat/completions"
    
    # 尝试不同的模型名称格式
    model_variants = [
        model_name,  # 原始名称
        model_name.replace("-", ":"),  # 横线转冒号
        model_name.replace(":", "-"),  # 冒号转横线
        model_name.split(":")[0],  # 只取冒号前的部分
        model_name.split("-")[0],  # 只取横线前的部分
    ]
    
    # 去重
    model_variants = list(dict.fromkeys(model_variants))
    
    headers = {
        "Content-Type": "application/json",
    }
    
    # 尝试不同的模型名称
    for variant in model_variants:
        print(f"\n尝试模型名称: {variant}")
        
        data = {
            "model": variant,
            "messages": [
                {"role": "user", "content": "Hello, please respond with 'OK' if you can read this."}
            ],
            "max_tokens": 50,
            "temperature": 0.1
        }
        
        try:
            print(f"   请求 URL: {url}")
            print(f"   请求数据: {json.dumps(data, indent=2, ensure_ascii=False)}")
            
            response = requests.post(url, json=data, headers=headers, timeout=30)
            
            print(f"   响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"   ✅ 成功!")
                print(f"   响应: {json.dumps(result, indent=2, ensure_ascii=False)[:500]}")
                
                if "choices" in result and len(result["choices"]) > 0:
                    content = result["choices"][0]["message"]["content"]
                    print(f"\n   模型回复: {content}")
                
                return True, variant
            else:
                print(f"   ❌ 失败: HTTP {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   错误信息: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
                except:
                    print(f"   错误文本: {response.text[:200]}")
        
        except requests.exceptions.Timeout:
            print(f"   ❌ 请求超时")
        except requests.exceptions.ConnectionError as e:
            print(f"   ❌ 连接失败: {e}")
        except Exception as e:
            print(f"   ❌ 异常: {e}")
    
    return False, None

def test_native_ollama_api(model_name: str):
    """测试 Ollama 原生 API"""
    print("\n" + "=" * 60)
    print(f"测试 4: 测试 Ollama 原生 API (模型: {model_name})")
    print("=" * 60)
    
    url = "http://localhost:11434/api/chat"
    
    # 尝试不同的模型名称格式
    model_variants = [
        model_name,
        model_name.replace("-", ":"),
        model_name.replace(":", "-"),
    ]
    model_variants = list(dict.fromkeys(model_variants))
    
    for variant in model_variants:
        print(f"\n尝试模型名称: {variant}")
        
        data = {
            "model": variant,
            "messages": [
                {"role": "user", "content": "Hello, please respond with 'OK' if you can read this."}
            ],
            "stream": False
        }
        
        try:
            print(f"   请求 URL: {url}")
            print(f"   请求数据: {json.dumps(data, indent=2, ensure_ascii=False)}")
            
            response = requests.post(url, json=data, timeout=30)
            
            print(f"   响应状态码: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"   ✅ 成功!")
                print(f"   响应: {json.dumps(result, indent=2, ensure_ascii=False)[:500]}")
                
                if "message" in result:
                    content = result["message"].get("content", "")
                    print(f"\n   模型回复: {content}")
                
                return True, variant
            else:
                print(f"   ❌ 失败: HTTP {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   错误信息: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
                except:
                    print(f"   错误文本: {response.text[:200]}")
        
        except Exception as e:
            print(f"   ❌ 异常: {e}")
    
    return False, None

def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("Ollama API 测试程序")
    print("=" * 60)
    
    # 测试 1: 检查基础服务
    if not test_ollama_base():
        print("\n❌ Ollama 服务未运行，请先启动服务")
        sys.exit(1)
    
    # 测试 2: 获取模型列表
    available_models = test_ollama_models()
    
    if not available_models:
        print("\n❌ 未找到任何模型，请先下载模型")
        print("   下载命令: ollama pull qwen2.5:7b")
        sys.exit(1)
    
    # 从命令行参数获取模型名称，或使用默认值
    if len(sys.argv) > 1:
        test_model = sys.argv[1]
    else:
        # 尝试找到 qwen2.5 相关的模型
        qwen_models = [m for m in available_models if "qwen" in m.lower()]
        if qwen_models:
            test_model = qwen_models[0]
            print(f"\n使用找到的模型: {test_model}")
        else:
            test_model = available_models[0]
            print(f"\n使用第一个可用模型: {test_model}")
    
    print(f"\n测试模型: {test_model}")
    
    # 测试 3: OpenAI 兼容端点
    success, working_model = test_openai_compatible_endpoint(test_model)
    
    if not success:
        print("\n⚠️ OpenAI 兼容端点测试失败，尝试原生 API...")
        # 测试 4: 原生 API
        success, working_model = test_native_ollama_api(test_model)
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    if success:
        print(f"✅ 测试成功!")
        print(f"   可用的模型名称: {working_model}")
        print(f"\n建议配置:")
        print(f"   - API 基础 URL: http://localhost:11434/v1")
        print(f"   - 模型名称: {working_model}")
    else:
        print("❌ 所有测试都失败了")
        print("\n可能的原因:")
        print("1. 模型名称不正确（尝试使用 'qwen2.5:7b' 或 'qwen2.5-7b'）")
        print("2. Ollama 版本过低（需要 0.1.0+ 支持 OpenAI 兼容模式）")
        print("3. 模型未正确下载")
        sys.exit(1)

if __name__ == "__main__":
    main()
