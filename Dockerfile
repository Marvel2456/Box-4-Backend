# Use official Python 3.12 slim image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install requirements
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy wait script and entrypoint
COPY wait_for_db.py entrypoint.sh /app/
RUN chmod +x /app/entrypoint.sh

# Copy project files
COPY . /app/

# Expose application port
EXPOSE 8000

# Set container entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]

# Default command running production WSGI server
CMD ["gunicorn", "core.wsgi:application", "--bind", "0.0.0.0:8000"]
