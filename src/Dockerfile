FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    curl \
    build-essential \
    libpq-dev \
    nano \
    poppler-utils \
    tesseract-ocr \
    libmagic1 \
    libglib2.0-0 \
    libsm6 libxext6 libxrender-dev

RUN python3 -m venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --upgrade pip

RUN pip install \
    streamlit \
    requests \
    debugpy \
    geopy \
    pycountry \
    python-dotenv \
    phonenumbers \
    redis \
    sqlalchemy \
    psycopg2-binary \
    python-magic \
    pytesseract \
    html2text \
    pdfplumber \
    python-docx \
    Pillow

WORKDIR /app

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "main.py", "--server.headless=true", "--server.port=8501", "--server.address=0.0.0.0", "--browser.gatherUsageStats=false"]
