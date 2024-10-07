# Use the official Python image from the Docker Hub
FROM python:3.9-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory
WORKDIR /Django_Translatation_App

# Install dependencies
COPY requirements.txt /Django_Translatation_App/
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . /Django_Translatation_App/

# Expose the port the app runs on
EXPOSE 8000

# Run the application
CMD ["sh", "-c", "python manage.py migrate && python manage.py runserver 0.0.0.0:8000"]