# Imagem oficial Playwright + Python (ja tem Chromium + todas libs do sistema)
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app

# Instala deps Python primeiro (cache de layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o codigo
COPY . .

# Streamlit roda na porta definida por $PORT (Render injeta) ou 8501 (default local)
ENV PYTHONUNBUFFERED=1
EXPOSE 8501

CMD streamlit run app.py \
    --server.port=${PORT:-8501} \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false
