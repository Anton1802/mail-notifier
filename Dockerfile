FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DB_PATH=/app/data/state.db

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py _common.py db.py telegram_notify.py bot_commands.py ./

# config.py и state.db НЕ копируем в образ:
# - config.py содержит секреты и монтируется как volume
# - state.db — рабочее состояние, лежит в /app/data (volume)

RUN useradd -m -u 1000 appuser
RUN mkdir -p /app/data && chown -R appuser:appuser /app/data
USER appuser

VOLUME ["/app/data"]

CMD ["python3", "main.py"]