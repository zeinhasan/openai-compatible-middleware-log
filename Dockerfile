# Use an official lightweight Python image.
FROM python:3.10-slim

# Set environment variables to prevent Python from writing .pyc files
# and to flush stdout/stderr immediately.
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose the port the app runs on
EXPOSE 8004

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8004"]
