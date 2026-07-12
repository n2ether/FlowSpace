FROM python:3.11-slim

WORKDIR /app

# Install system deps for reportlab / pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev libssl-dev libjpeg-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
