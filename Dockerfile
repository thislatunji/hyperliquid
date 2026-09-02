FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1

# Install production dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app source
COPY . .

# Run the monitor (long-running worker, no web server)
CMD ["python", "monitor.py"]
