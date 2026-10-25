FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir psycopg2-binary==2.9.9 openpyxl==3.1.5
COPY load_to_postgres.py .
COPY extract_full_history.py .
CMD ["python", "load_to_postgres.py"]
