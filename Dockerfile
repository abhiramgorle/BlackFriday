# For Railway or any always-on host. Not needed for GitHub Actions.
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONUNBUFFERED=1 INTERVAL_SECONDS=1800
CMD ["python", "run.py", "loop"]
