# Professional Dockerfile for QuantVision
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y build-essential libgl1-mesa-glx && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt ./
COPY requirements/ ./requirements/
RUN pip install --no-cache-dir -r requirements.txt

# Copy app source code
COPY src/ ./src/
COPY data/ ./data/
COPY README.md ./

# Expose Streamlit default port
EXPOSE 8501

# Set environment variables for Streamlit
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ENABLECORS=false

# Run the Streamlit app
CMD ["streamlit", "run", "src/app.py"]
