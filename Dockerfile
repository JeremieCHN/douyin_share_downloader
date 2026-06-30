# 抖音无水印下载 Web 服务镜像
FROM python:3.12-slim

WORKDIR /app

# 仅安装运行依赖；gunicorn 仅镜像内使用，不污染 requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# 拷贝应用代码（下载产物等由 .dockerignore 排除）
COPY douyin_dl/ ./douyin_dl/
COPY web/ ./web/

# 下载目录挂载点，便于持久化产物
RUN mkdir -p /app/downloads
VOLUME ["/app/downloads"]

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 5000

# 视频/图文下载可能耗时较长，放宽 worker 超时
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "300", "web.app:app"]
