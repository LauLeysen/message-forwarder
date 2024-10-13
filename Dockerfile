# Use an official Python runtime as a base image
FROM python:3.11.4-slim

# Set the working directory
WORKDIR /app

# Copy requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Set environment variables (or use .env file)
ENV CHANNEL_IDS=${CHANNEL_IDS}
ENV DISCORD_TOKEN=${DISCORD_TOKEN}
ENV TELEGRAM_TOKEN=${TELEGRAM_TOKEN}
ENV TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID}

# Run the application
CMD ["python", "main.py"]
