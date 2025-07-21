# --------- 阶段 1: 构建依赖 ----------
    FROM python:3.10-slim-bookworm AS base

    ENV PYTHONUNBUFFERED=1 \
        PYTHONDONTWRITEBYTECODE=1
    
    WORKDIR /app
    
    # 使用阿里云源加速 apt 安装
    RUN echo 'deb http://mirrors.aliyun.com/debian/ bookworm main' > /etc/apt/sources.list && \
        echo 'deb-src http://mirrors.aliyun.com/debian/ bookworm main' >> /etc/apt/sources.list && \
        echo 'deb http://mirrors.aliyun.com/debian/ bookworm-updates main' >> /etc/apt/sources.list && \
        echo 'deb-src http://mirrors.aliyun.com/debian/ bookworm-updates main' >> /etc/apt/sources.list && \
        echo 'deb http://mirrors.aliyun.com/debian-security bookworm-security main' >> /etc/apt/sources.list && \
        echo 'deb-src http://mirrors.aliyun.com/debian-security bookworm-security main' >> /etc/apt/sources.list
    
    RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        wkhtmltopdf \
        xvfb \
        fonts-wqy-zenhei \
        fonts-wqy-microhei \
        fonts-liberation \
        pandoc \
        procps \
        && rm -rf /var/lib/apt/lists/*
    
    # 安装 Python 包管理器
    RUN pip install --upgrade pip
    
    # 复制 wheels 和 requirements 文件
    COPY wheels/ /app/wheels/
    COPY requirements.txt .
    
    # 优先离线安装 .whl 文件中的依赖，避免在线构建超时
    RUN pip install --no-cache-dir wheels/*
    
    # --------- 阶段 2: 应用构建 ----------
    FROM base AS final
    
    WORKDIR /app
    
    # 虚拟显示器启动脚本
    RUN echo '#!/bin/bash\nXvfb :99 -screen 0 1024x768x24 -ac +extension GLX &\nexport DISPLAY=:99\nexec "$@"' > /usr/local/bin/start-xvfb.sh \
        && chmod +x /usr/local/bin/start-xvfb.sh
    
    # 拷贝项目代码
    COPY . .
    
    # 日志与数据目录
    RUN mkdir -p /app/data /app/logs
    
    # 启动 streamlit
    EXPOSE 8501
    CMD ["python", "-m", "streamlit", "run", "web/app.py", "--server.address=0.0.0.0", "--server.port=8501"]
    