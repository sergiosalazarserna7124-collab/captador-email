FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py reporte.py ./

# Usuario sin privilegios
RUN useradd -m captador
USER captador

CMD ["python", "main.py"]
