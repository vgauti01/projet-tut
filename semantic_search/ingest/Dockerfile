
FROM python:3.11-slim
WORKDIR /ingest
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "ingest_hybrid.py"]