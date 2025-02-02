FROM python:3.10.12

# оновлюємо пакети та встановлюємо необхідні для роботи додатку
RUN apt-get update && \
    apt-get install -y iputils-ping && \
    apt-get install -y ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY . .

ENV FLASK_APP=controller.py


CMD ["flask", "run", "--host", "0.0.0.0", "--port", "8080"]