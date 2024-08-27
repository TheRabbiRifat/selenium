# Use the official Python image with a version of your choice
FROM python:3.11-slim

# Set environment variables to ensure that Python runs in a consistent environment
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install the dependencies from requirements.txt
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Install wkhtmltopdf and dependencies
RUN apt-get update && apt-get install -y \
    wkhtmltopdf \
    && apt-get clean

# Copy the entire project into the container
COPY . .

# Expose the port Flask will run on
EXPOSE 8080

# Define the command to run the Flask application
CMD ["python", "app.py"]
