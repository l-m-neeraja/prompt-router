FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY prompts.py .
COPY app.py .
COPY api.py .

# Default: run interactive CLI
CMD ["python", "app.py"]
