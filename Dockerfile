FROM python:3.12-slim
 
# Не пишем .pyc, вывод сразу в лог без буферизации
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
 
WORKDIR /app
 
# Ставим зависимости отдельным слоем для кэширования
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
 
# Копируем код проекта
COPY main.py _common.py db.py telegram.py ./
 
# config.py и state.db НЕ копируем в образ:
# - config.py содержит секреты и монтируется как volume
# - state.db — рабочее состояние, тоже монтируется как volume
 
# Непривилегированный пользователь
RUN useradd -m -u 1000 appuser
 
# Создаём папку для данных заранее и сразу отдаём её appuser,
# чтобы volume не создавался от root при первом монтировании
RUN mkdir -p /app/data && chown -R appuser:appuser /app/data
 
USER appuser
 
VOLUME ["/app/data"]
 
CMD ["python3", "main.py"]
 