# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy the current directory contents into the container at /usr/src/app
COPY requirements.txt /usr/src/app
COPY WebSocketProcessor.py /usr/src/app

# Install any needed packages specified in requirements.txt
RUN pip install -r requirements.txt

# CMD command to test Python execution
#CMD ["python", "-c", "print('Hello from inside the container!')"]
CMD ["python","-u","WebSocketProcessor.py"]