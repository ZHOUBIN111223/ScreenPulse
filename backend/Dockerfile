FROM python:3.11-slim
WORKDIR /app
ENV PIP_NO_CACHE_DIR=1
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt
COPY app ./app
RUN mkdir -p storage
EXPOSE 8011
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8011"]
