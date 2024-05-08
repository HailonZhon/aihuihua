import json
import os
import time
import logging

import pika
import websocket

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# Get the logger for pika and set its level to WARNING to reduce output
logging.getLogger("pika").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


class WebSocketProcessor:
    def __init__(self):
        self.ws = None
        self.prompt_id = None

    def connect_websocket(self, ws_url):
        logger.info(f"Attempting to connect to WebSocket at URL: {ws_url}")
        try:
            self.ws = websocket.create_connection(ws_url)
            logger.info("WebSocket connection established successfully.")
        except Exception as e:
            logger.error(f"Failed to connect to WebSocket: {e}")
            self.ws = None

    def listen_for_completion(self):
        while True:
            try:
                result = self.ws.recv()
                logger.info(result)
                if isinstance(result, str):
                    data = json.loads(result)
                    logger.info(f"Received data from WebSocket: {data}")
                    if data['type'] == 'status' and 'sid' not in data['data']:
                        if data['data']['status']['exec_info']['queue_remaining'] == 0:
                            logger.info("Queue remaining is 0, about to notify the main process.")
                            self.notify_main_process()
            except websocket.WebSocketConnectionClosedException as e:
                logger.warning(f"WebSocket connection closed: {e}")
                break
            except TypeError as e:
                logger.error(f"TypeError in processing WebSocket data: {e}")
                self.ws = None
                break
            except Exception as e:
                logger.error(f"Error while listening to WebSocket: {e}")
                self.ws = None
                break

    @staticmethod
    def notify_main_process():
        rabbitmq_host = os.getenv('RABBITMQ_HOST', 'rabbitmq')
        logger.info(f"Connecting to RabbitMQ host at: {rabbitmq_host}")
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=rabbitmq_host))
            channel = connection.channel()
            channel.queue_declare(queue='image_processed')
            channel.basic_publish(exchange='', routing_key='image_processed', body='done')
            logger.info("Notification sent to the main process through RabbitMQ.")
        except Exception as e:
            logger.error(f"Failed to notify the main process via RabbitMQ: {e}")
        finally:
            if connection.is_open:
                connection.close()
                logger.info("RabbitMQ connection closed.")

    def close_websocket(self):
        if self.ws:
            try:
                self.ws.close()
                logger.info("WebSocket connection has been closed.")
            except Exception as e:
                logger.error(f"Error occurred while closing WebSocket: {e}")
            finally:
                self.ws = None


if __name__ == "__main__":
    rabbitmq_host = os.getenv('RABBITMQ_HOST', 'rabbitmq')
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=rabbitmq_host))
    channel = connection.channel()
    channel.queue_declare(queue='uuid_queue')
    ws_url = os.getenv('WS_URL', 'ws://66.114.112.70:40391/ws?clientId=')


    def callback(ch, method, properties, body):
        uuid = body.decode()
        logger.info(f"Received UUID: {uuid}")
        ws_processor = WebSocketProcessor()
        ws_processor.connect_websocket(ws_url + uuid)
        ws_processor.listen_for_completion()
        ws_processor.close_websocket()


    channel.basic_consume(queue='uuid_queue', on_message_callback=callback, auto_ack=True)
    logger.info('Waiting for UUIDs. To exit press CTRL+C')
    channel.start_consuming()
