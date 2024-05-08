import datetime
import json
import os
import random
import uuid
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from aiofiles import open as aio_open
import pika
import logging

from src.image_processing.image_processor import ImageProcessor

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# Get the logger for pika and set its level to WARNING to reduce output
logging.getLogger("pika").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

app = FastAPI()

# 允许的跨域源列表
origins = [
    "http://localhost:3000",  # 假设你的前端运行在3000端口
    "https://localhost:3000",
    "http://localhost:8080",
    "http://localhost:8000",  # 允许FastAPI的Swagger UI访问
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 服务静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")

# 确保上传目录存在
UPLOAD_DIR = Path("data/uploaded_images")
UPLOAD_DIR.mkdir(exist_ok=True)

base_url = os.getenv("BASE_URL")
# base_url = "https://exuwomf4pougcn-3000.proxy.runpod.net"
image_processor = ImageProcessor(base_url)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_bytes()
            # 生成文件名
            file_path = UPLOAD_DIR / f"image_{datetime.datetime.now().isoformat()}.png"
            # 异步写入文件
            async with aio_open(file_path, 'wb') as f:
                await f.write(data)
            logger.info(f"Saved image to {file_path}")

            # 处理图片
            processed_image = await process_image(file_path)
            await websocket.send_bytes(processed_image)
    except WebSocketDisconnect:
        logger.info("Client disconnected.")


async def process_image(file_path):
    # 上传图片到服务器
    image_name_server = image_processor.upload_image(file_path)

    # 准备prompt workflow
    with open(Path('static/workflow_api_huihua_2_1.json'), 'r') as file:
        prompt_workflow = json.load(file)

    # 设置prompt workflow
    prompt_workflow["13"]["inputs"]["image"] = f"/workspace/ComfyUI/input/{image_name_server}"
    prompt_workflow["3"]["inputs"]["denoise"] = 1.0
    prompt_workflow["3"]["inputs"]["seed"] = random.randint(0, 4284967295) * random.randint(0, 10000)
    prompt_workflow["6"]["inputs"]["text"] = "猫"
    prompt_workflow["29"]["inputs"]["width"] = 618
    prompt_workflow["29"]["inputs"]["height"] = 884

    # 生成 UUID 并发送到队列
    uuid_value = str(uuid.uuid4())
    rabbitmq_host = os.getenv('RABBITMQ_HOST', 'rabbitmq')  # 默认为localhost
    # rabbitmq_host = "localhost"



    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=rabbitmq_host))
        channel = connection.channel()
        channel.queue_declare(queue='uuid_queue')
        channel.basic_publish(exchange='', routing_key='uuid_queue', body=uuid_value)
        logger.info(f"Successfully published UUID {uuid_value} to RabbitMQ.")
    except Exception as e:
        logger.error(f"Failed to publish UUID to RabbitMQ: {e}")
        return None
    finally:
        if connection.is_open:
            connection.close()
            logger.info("RabbitMQ connection closed.")
    # 队列prompt
    prompt_id = image_processor.queue_prompt(prompt_workflow)
    if not prompt_id:
        return None
    # 等待处理完成信号
    image_processor.wait_for_image_processed_signal()

    images = image_processor.get_images()
    if images:
        logger.info(f"Successfully processed images, returning the first image.")
        return images[0]
    else:
        logger.info("No images processed.")
        return None