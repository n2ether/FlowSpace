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

# Shell form so $PORT (injected by Railway) expands at runtime.
# Falls back to 8000 for local runs where PORT isn't set.
CMD uvicorn server:app --host 0.0.0.0 --port ${PORT:-8000}
