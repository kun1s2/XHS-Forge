# 使用轻量级 Python 镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装必要的系统依赖（如 psycopg2 编译需要的 libpq-dev）
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制后端源码
COPY . .

# 暴露后端端口
EXPOSE 8000

# 启动命令（生产环境建议使用 uvicorn）
CMD ["python", "run.py"]
