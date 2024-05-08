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

