# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy the current directory contents into the container at /usr/src/app
COPY . /usr/src/app

# Install any needed packages specified in requirements.txt
RUN pip install -r requirements.txt

# Install necessary system tools
RUN apt-get update && \
    apt-get install -y --no-install-recommends apt-utils gnupg curl wget ca-certificates

# Add the RabbitMQ official signing key
RUN wget -O /usr/share/keyrings/rabbitmq-archive-keyring.gpg https://packages.rabbitmq.com/rabbitmq-release-signing-key.asc

# Add the RabbitMQ APT repository to your system
RUN echo "deb [signed-by=/usr/share/keyrings/rabbitmq-archive-keyring.gpg] http://packages.rabbitmq.com/debian buster main" | tee /etc/apt/sources.list.d/rabbitmq.list

# Install RabbitMQ server
RUN apt-get update && \
    apt-get install -y rabbitmq-server

# Enable the RabbitMQ management plugin
RUN rabbitmq-plugins enable rabbitmq_management

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Define environment variable
ENV NAME World

# Run main.py when the container launches (Adjust the path according to where main.py is located)
CMD ["uvicorn", "app.ImageProcess.main:app", "--host", "0.0.0.0", "--port", "8000"]
