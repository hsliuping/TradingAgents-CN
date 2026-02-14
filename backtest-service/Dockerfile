# Backtrader 回测服务 (GPLv3)
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
EXPOSE 8900

ENV HOST=0.0.0.0
ENV PORT=8900

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8900"]
