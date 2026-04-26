FROM registry.cn-hangzhou.aliyuncs.com/library/python:3.11-slim
WORKDIR /app
ARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
ARG PIP_TRUSTED_HOST=mirrors.aliyun.com
ENV PIP_INDEX_URL=${PIP_INDEX_URL}
ENV PIP_TRUSTED_HOST=${PIP_TRUSTED_HOST}
ENV PIP_NO_CACHE_DIR=1
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt
COPY app ./app
RUN mkdir -p storage
EXPOSE 8011
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8011"]
