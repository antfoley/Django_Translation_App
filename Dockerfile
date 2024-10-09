# Use the official Python image from the Docker Hub
FROM python:3.9-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory
WORKDIR /Django_Translatation_App

# Install dependencies
COPY requirements.txt /Django_Translatation_App/
RUN python -m venv /opt/venv
RUN /opt/venv/bin/pip install --upgrade pip
RUN /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# Activate virtual environment
ENV PATH="/opt/venv/bin:$PATH"

# Copy the application code
COPY . /Django_Translatation_App/

# Copy the API credentials
COPY C:/Users/AnthonyFoley/Project1_TranslationApp/Django_Translation_App/translation_app/booming-post-404017-49309d69296e.json /Django_Translatation_App/translation_app/booming-post-404017-49309d69296e.json

# Set the environment variable to point to the new location of the JSON file
ENV GOOGLE_APPLICATION_CREDENTIALS=/app/config/booming-post-404017-49309d69296e.json

# Expose the port the app runs on
EXPOSE 8000

# Run the application
CMD ["sh", "-c", "python manage.py migrate && python manage.py runserver 0.0.0.0:8000"]