FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY pipeline ./pipeline
RUN pip install --no-cache-dir '.[test]'
COPY . .
RUN mkdir -p /app/data && useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 8501
CMD ["streamlit", "run", "streamlit_app.py", "--server.address=0.0.0.0"]
