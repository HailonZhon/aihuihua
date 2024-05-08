import os
import os.path
import requests
import json
import pika
import logging
import time
from requests_toolbelt.multipart.encoder import MultipartEncoder

# 配置日志

class ImageProcessor:
    def __init__(self, base_url, proxy_url=None):
        self.logger = logging.getLogger('ImageProcessor')
        self.base_url = base_url
        self.proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None
        self.image_name_server = None
        self.prompt_id = None

    def upload_image(self, image_path):
        url = f"{self.base_url}/upload/image"
        filename = image_path.name
        try:
            start_time = time.time()
            with open(image_path, 'rb') as file:
                m = MultipartEncoder(
                    fields={'image': (filename, file, 'image/png')}
                )
                response = requests.post(url, data=m, headers={'Content-Type': m.content_type}, proxies=self.proxies)
                if response.status_code == 200:
                    self.image_name_server = response.json()['name']
                    self.logger.info(f'upload_image:图片上传成功 {response.json()}')
                else:
                    logging.error(f'upload_image:图片上传失败 {response.status_code} {response.text}')
                    return None
            upload_duration = time.time() - start_time
            self.logger.info(f'upload_image:上传图片耗时 {upload_duration:.2f} 秒')
        except Exception as e:
            logging.error(f'upload_image:上传图片过程中出错: {e}')
            return None
        return self.image_name_server

    def queue_prompt(self, prompt_workflow):
        if self.image_name_server is None:
            self.logger.info("queue_prompt:请先上传一张图片和选择风格")
            return None

        try:
            start_time = time.time()
            request_data = json.dumps({"prompt": prompt_workflow})
            response = requests.post(
                f"{self.base_url}/prompt",
                data=request_data,
                headers={'Content-Type': 'application/json'},
                proxies=self.proxies
            )
            if response.status_code == 200:
                self.prompt_id = response.json()['prompt_id']
                self.logger.info(f'queue_prompt:Prompt ID: {self.prompt_id}')
                queue_duration = time.time() - start_time
                self.logger.info(f'queue_prompt:队列Prompt耗时 {queue_duration:.2f} 秒')
                return self.prompt_id
            else:
                logging.error('queue_prompt:API 请求失败')
                return None
        except Exception as e:
            logging.error(f'queue_prompt:队列Prompt过程中出错: {e}')
            return None

    def get_images(self):
        if self.prompt_id is None:
            self.logger.info("get_images:没有可用的 Prompt ID 来获取图片。")
            return []

        try:
            start_time = time.time()
            response = requests.get(f"{self.base_url}/history/{self.prompt_id}")
            data = response.json()
            if not data:
                return []
            images_data = []
            outputs = data[self.prompt_id]['outputs']

            for node_id, node_output in outputs.items():
                if 'images' in node_output:
                    for image in node_output['images']:
                        image_data = self.get_server_image(image['filename'], image['subfolder'], image['type'])
                        if image_data:
                            images_data.append(image_data)
            get_images_duration = time.time() - start_time
            self.logger.info(f'get_images:获取图片耗时 {get_images_duration:.2f} 秒')
            return images_data
        except Exception as e:
            logging.error(f'get_images:获取图片过程中出错: {e}')
            return []

    def get_server_image(self, filename, subfolder, image_type):
        url = f"{self.base_url}/view?filename={filename}&subfolder={subfolder}&type={image_type}"
        try:
            start_time = time.time()
            response = requests.get(url, stream=True)
            if response.status_code == 200:
                image_data = response.content
                if not os.path.exists('data/output'):
                    os.makedirs('data/output')
                with open(f"data/output/{filename}", "wb") as f:
                    f.write(image_data)
                self.logger.info("get_server_image:图片成功加载")
                get_server_image_duration = time.time() - start_time
                self.logger.info(f'get_server_image:加载服务器图片耗时 {get_server_image_duration:.2f} 秒')
                return image_data
            else:
                logging.error("get_server_image:加载图片失败")
                return None
        except Exception as e:
            logging.error(f'get_server_image:加载服务器图片过程中出错: {e}')
            return None

    def wait_for_image_processed_signal(self):
        # 等待 WebSocket 通信程序发送的处理完成信号
        rabbitmq_host = os.getenv('RABBITMQ_HOST', 'rabbitmq')  # 默认为localhost
        try:
            start_time = time.time()
            connection = pika.BlockingConnection(pika.ConnectionParameters(host=rabbitmq_host))
            channel = connection.channel()
            channel.queue_declare(queue='image_processed')

            def callback(ch, method, properties, body):
                if body.decode() == 'done':
                    ch.stop_consuming()

            channel.basic_consume(queue='image_processed', on_message_callback=callback, auto_ack=True)
            channel.start_consuming()
            connection.close()
            wait_duration = time.time() - start_time
            self.logger.info(f'wait_for_image_processed_signal:等待图片处理信号耗时 {wait_duration:.2f} 秒')
        except Exception as e:
            logging.error(f'wait_for_image_processed_signal:等待处理信号过程中出错: {e}')
