FROM python:3.11-slim

# Set unbuffered output for real-time container logging
ENV PYTHONUNBUFFERED=1

# Install system dependencies (FFmpeg required for audio transcoding and amix mixing, libopus0 for Opus encoding)
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg libopus0 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create non-root user shanty for security and host-file permission safety
RUN useradd -m shanty

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chown -R shanty:shanty /app

USER shanty

EXPOSE 8000

CMD ["python", "main.py"]
