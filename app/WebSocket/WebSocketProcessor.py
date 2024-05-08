import json
import os
import time
import logging

import pika
import websocket

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# 设置pika日志的级别为WARNING，减少输出
logging.getLogger("pika").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


class WebSocketProcessor:
    def __init__(self):
        self.ws = None
        self.prompt_id = None

    def connect_websocket(self, ws_url):
        logger.info(f"尝试连接到WebSocket，URL为：{ws_url}")
        try:
            self.ws = websocket.create_connection(ws_url)
            logger.info("WebSocket连接成功建立。")
        except Exception as e:
            logger.error(f"连接WebSocket失败：{e}")
            self.ws = None

    def listen_for_completion(self):
        while True:
            try:
                result = self.ws.recv()
                logger.info(result)
                if isinstance(result, str):
                    data = json.loads(result)
                    logger.info(f"从WebSocket接收到数据：{data}")
                    if data['type'] == 'status' and 'sid' not in data['data']:
                        if data['data']['status']['exec_info']['queue_remaining'] == 0:
                            logger.info("队列剩余为0，即将通知主进程。")
                            self.notify_main_process()
            except websocket.WebSocketConnectionClosedException as e:
                logger.warning(f"WebSocket连接关闭：{e}")
                break
            except TypeError as e:
                logger.error(f"处理WebSocket数据时发生TypeError：{e}")
                self.ws = None
                break
            except Exception as e:
                logger.error(f"监听WebSocket时发生错误：{e}")
                self.ws = None
                break

    @staticmethod
    def notify_main_process():
        rabbitmq_host = os.getenv('RABBITMQ_HOST', 'rabbitmq')
        logger.info(f"连接到RabbitMQ主机，地址为：{rabbitmq_host}")
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=rabbitmq_host))
            channel = connection.channel()
            channel.queue_declare(queue='image_processed')
            channel.basic_publish(exchange='', routing_key='image_processed', body='done')
            logger.info("通过RabbitMQ发送通知到主进程。")
        except Exception as e:
            logger.error(f"通过RabbitMQ通知主进程失败：{e}")
        finally:
            if connection.is_open:
                connection.close()
                logger.info("RabbitMQ连接已关闭。")

    def close_websocket(self):
        if self.ws:
            try:
                self.ws.close()
                logger.info("WebSocket连接已关闭。")
            except Exception as e:
                logger.error(f"关闭WebSocket时发生错误：{e}")
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
        logger.info(f"接收到UUID：{uuid}")
        ws_processor = WebSocketProcessor()
        ws_processor.connect_websocket(ws_url + uuid)
        ws_processor.listen_for_completion()
        ws_processor.close_websocket()

    channel.basic_consume(queue='uuid_queue', on_message_callback=callback, auto_ack=True)
    logger.info('等待UUIDs。退出请按 CTRL+C')
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        logger.info("手动中断，程序退出。")
    except Exception as e:
        logger.error(f"监听消息时发生异常：{e}")
        # 如果发生异常，重新启动消费流程
        try:
            channel.start_consuming()
        except Exception as e:
            logger.error(f"重试启动消费者失败：{e}")
