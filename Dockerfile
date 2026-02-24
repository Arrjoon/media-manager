FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

COPY req.txt /app/
RUN pip install --no-cache-dir -r req.txt

COPY . /app/

# Copy the entrypoint script
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Use entrypoint instead of CMD
ENTRYPOINT ["/app/entrypoint.sh"]