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

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Define environment variable
ENV NAME World

# Run main.py when the container launches (Adjust the path according to where main.py is located)
CMD ["uvicorn", "app.ImageProcess.main:app", "--host", "0.0.0.0", "--port", "8000"]
