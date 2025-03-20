FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8888

ENV FLASK_APP=run.py
ENV FLASK_ENV=production

CMD ["gunicorn", "-k", "-w", "1", "-b", "0.0.0.0:8888", "app:app"]
