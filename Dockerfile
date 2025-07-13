FROM python:3.12-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем requirements.txt и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код приложения
COPY . .

# Создаем необходимые директории
RUN mkdir -p logs data templates/mikrotik_templates

# Устанавливаем права на запись для директорий с данными
RUN chmod 755 logs data templates

# Открываем порт (если нужно для мониторинга)
EXPOSE 8080

# Запускаем приложение
CMD ["python", "main.py"]