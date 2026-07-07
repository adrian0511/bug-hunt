# Imagen simple de una sola etapa. No hace falta docker-compose: SQLite va embebido.
FROM python:3.12-slim

WORKDIR /app

# Instala las dependencias primero para aprovechar mejor la cache de capas.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# La app depende del paquete shared/ del monorepo, así que copiamos ambos.
# Se espera que el contexto de build sea la raíz del monorepo: `docker build -f
# reto2-url-shortener/Dockerfile -t url-shortener .`
COPY shared ./shared
COPY reto2-url-shortener/app ./app

# Persiste el archivo de SQLite en una ruta apta para volúmenes.
ENV DATABASE_URL=sqlite:///./data/urlshortener.db
RUN mkdir -p ./data
VOLUME ["/app/data"]

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
