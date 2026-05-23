FROM python:3.12-slim

COPY basic_auth.ini /basic_auth.ini
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 5000
