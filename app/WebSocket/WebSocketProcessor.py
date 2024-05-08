import json
import os
import time
import logging

import pika
import websocket

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# 设置 pika 日志的级别为 WARNING，减少输出
logging.getLogger("pika").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


class WebSocketProcessor:
    def __init__(self, ws_url):
        self.ws_url = ws_url
        self.ws = None

    def connect_websocket(self):
        logger.info(f"尝试连接到 WebSocket，URL 为：{self.ws_url}")
        try:
            self.ws = websocket.create_connection(self.ws_url)
            logger.info("WebSocket 连接成功建立。")
        except Exception as e:
            logger.error(f"连接 WebSocket 失败：{e}")
            self.ws = None

    def listen_for_completion(self):
        if not self.ws:
            logger.error("WebSocket 连接未建立，无法监听消息。")
            return False
        try:
            while True:
                result = self.ws.recv()
                logger.info(result)
                if isinstance(result, str):
                    data = json.loads(result)
                    logger.info(f"从 WebSocket 接收到数据：{data}")
                    if data['type'] == 'status' and 'sid' not in data['data']:
                        if data['data']['status']['exec_info']['queue_remaining'] == 0:
                            logger.info("队列剩余为 0，即将通知主进程。")
                            self.notify_main_process()
                            return True
        except websocket.WebSocketConnectionClosedException as e:
            logger.warning(f"WebSocket 连接关闭：{e}")
        except Exception as e:
            logger.error(f"监听 WebSocket 时发生错误：{e}")
        finally:
            self.close_websocket()
        return False

    @staticmethod
    def notify_main_process():
        rabbitmq_host = os.getenv('RABBITMQ_HOST', 'rabbitmq')
        logger.info(f"连接到 RabbitMQ 主机，地址为：{rabbitmq_host}")
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=rabbitmq_host))
            channel = connection.channel()
            channel.queue_declare(queue='image_processed')
            channel.basic_publish(exchange='', routing_key='image_processed', body='done')
            logger.info("通过 RabbitMQ 发送通知到主进程。")
        except Exception as e:
            logger.error(f"通过 RabbitMQ 通知主进程失败：{e}")
        finally:
            if connection and connection.is_open:
                connection.close()
                logger.info("RabbitMQ 连接已关闭。")

    def close_websocket(self):
        if self.ws:
            try:
                self.ws.close()
                logger.info("WebSocket 连接已关闭。")
            except Exception as e:
                logger.error(f"关闭 WebSocket 时发生错误：{e}")


def main():
    rabbitmq_host = os.getenv('RABBITMQ_HOST', 'rabbitmq')
    ws_url_base = os.getenv('WS_URL', 'ws://127.0.0.1:3001/ws?clientId=')

    while True:
        try:
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=rabbitmq_host))
            channel = connection.channel()
            channel.queue_declare(queue='uuid_queue')

            def callback(ch, method, properties, body):
                uuid = body.decode()
                logger.info(f"接收到 UUID：{uuid}")
                ws_processor = WebSocketProcessor(ws_url_base + uuid)
                if ws_processor.connect_websocket():
                    if ws_processor.listen_for_completion():
                        logger.info("WebSocket 会话处理完成，准备接收新的 UUID。")
                    else:
                        logger.info("WebSocket 会话处理失败，准备接收新的 UUID。")

            channel.basic_consume(queue='uuid_queue', on_message_callback=callback, auto_ack=True)
            logger.info('等待 UUIDs。退出请按 CTRL+C')
            channel.start_consuming()
        except KeyboardInterrupt:
            logger.info("手动中断，程序退出。")
            break
        except Exception as e:
            logger.error(f"主循环异常：{e}")
            time.sleep(5)  # 遇到异常时，暂停一段时间再继续


if __name__ == "__main__":
    main()
