FROM python:3.11-slim

WORKDIR /src

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency installation
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Install Python dependencies
COPY pyproject.toml .
RUN uv pip install --system -r pyproject.toml

# Copy project files
COPY . .

# Expose the application port
EXPOSE 8000

# Start FastAPI server
CMD ["python", "main.py"]

