FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy data and backend source
COPY data/ ./data/
COPY backend/ ./backend/

# Pre-train model at image build time so the API starts instantly
RUN python backend/train.py

# Hugging Face Spaces requires a non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser /app
USER appuser

# Hugging Face Spaces requires port 7860
EXPOSE 7860

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "7860"]
