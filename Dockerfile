FROM python:3.13-slim


# Set environment variables consistently
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT="/usr/local/" \
    # Ensure scripts know where the app root is
    PYTHONPATH="/app"


# Install uv package manager
# Install in /usr/local/bin as it is a "local" software
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/


WORKDIR /app

# Copy and install dependencies first for caching efficiency
COPY pyproject.toml uv.lock* ./
RUN uv sync --no-dev --frozen --no-cache

COPY . /app

RUN chmod +x scripts/* || true

# Create and switch to a non-root user
RUN useradd -ms /bin/bash appuser
USER appuser

# Make port 8000 available (adjust if your API uses a different port)
EXPOSE 8000

# Default command (no reload in production)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
