"""
纯本地 Embedding 服务 — 使用 sentence-transformers 加载模型，
通过 Ollama 兼容 HTTP API 暴露，无缝对接 mem0。

使用方式：
- 系统配置 default_embedding_model 设为 local:Qwen/Qwen3-Embedding-0.6B
- 首次运行自动下载模型到 ~/.cache/huggingface/，之后常驻内存
- 无需 GPU，纯 CPU 推理，单条 100-300ms
"""

import json
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

logger = logging.getLogger(__name__)

_LOCAL_PORT = 11435
_DEFAULT_MODEL = "Qwen/Qwen3-Embedding-0.6B"

_model = None
_model_name = None
_server_started = False
_server_lock = threading.Lock()


def _get_model(model_name: str):
    """懒加载 sentence-transformers 模型（缓存单例）"""
    global _model, _model_name
    if _model is not None and _model_name == model_name:
        return _model
    from sentence_transformers import SentenceTransformer

    logger.info("📦 正在下载/加载本地 Embedding 模型: %s ...", model_name)
    _model = SentenceTransformer(model_name, local_files_only=True)
    _model_name = model_name
    dims = _model.get_embedding_dimension()
    logger.info("✅ 本地 Embedding 模型加载完成: %s (维度=%d)", model_name, dims)
    return _model


class _EmbeddingHandler(BaseHTTPRequestHandler):
    """Ollama /api/embeddings 兼容处理器"""

    def do_POST(self):
        if self.path != "/api/embeddings":
            self.send_response(404)
            self.end_headers()
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            req = json.loads(body)

            model_name = req.get("model") or _DEFAULT_MODEL
            prompt = req.get("prompt") or req.get("input") or ""
            if isinstance(prompt, list):
                prompt = " ".join(str(p) for p in prompt)
            if not prompt:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "empty prompt"}).encode("utf-8"))
                return

            model = _get_model(model_name)
            embedding = model.encode(prompt, normalize_embeddings=True).tolist()

            resp = {"embedding": embedding}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(resp).encode("utf-8"))
        except Exception as e:
            logger.warning("本地 Embedding 请求失败: %s", e)
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

    def log_message(self, format, *args):
        pass  # 屏蔽 HTTP 访问日志


def _start_server():
    """启动本地 Embedding HTTP 服务（守护线程）"""
    global _server_started
    with _server_lock:
        if _server_started:
            return
        # 预加载模型
        _get_model(_DEFAULT_MODEL)
        server = HTTPServer(("127.0.0.1", _LOCAL_PORT), _EmbeddingHandler)
        thread = threading.Thread(
            target=server.serve_forever, daemon=True, name="local-embedder"
        )
        thread.start()
        _server_started = True
        logger.info(
            "✅ 本地 Embedding 服务已启动: http://127.0.0.1:%d", _LOCAL_PORT
        )


def ensure_local_embedder():
    """确保本地 Embedding 服务已启动（幂等调用）"""
    _start_server()
