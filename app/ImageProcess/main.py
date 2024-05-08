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

# 配置日志，添加 %(name)s 来显示 logger 的名称
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# 设置 pika 日志级别为 WARNING，减少输出
logging.getLogger("pika").setLevel(logging.WARNING)
logging.getLogger("ImageProcessor").setLevel(logging.WARNING)

app = FastAPI()

# 允许的跨域源列表
origins = [
    "http://localhost:3000",
    "https://localhost:3000",
    "http://localhost:8080",
    "http://localhost:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 配置静态文件服务
app.mount("/static", StaticFiles(directory="static"), name="static")

# 确保上传目录存在
UPLOAD_DIR = Path("data/uploaded_images")
UPLOAD_DIR.mkdir(exist_ok=True)

base_url = os.getenv("BASE_URL")
image_processor = ImageProcessor(base_url)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # 使用 __name__ 来获取当前模块的 logger
    logger = logging.getLogger(__name__)
    await websocket.accept()
    try:
        while True:
            start_time = datetime.datetime.now()
            data = await websocket.receive_bytes()
            file_path = UPLOAD_DIR / f"image_{datetime.datetime.now().isoformat()}.png"

            async with aio_open(file_path, 'wb') as f:
                await f.write(data)
            logger.info(f"websocket_endpoint:图片已保存至 {file_path}")

            # 测量文件写入耗时
            file_write_time = datetime.datetime.now() - start_time
            logger.info(f"websocket_endpoint:文件写入耗时 {file_write_time.total_seconds()} 秒")

            # 处理图片
            start_time = datetime.datetime.now()
            processed_image = await process_image(file_path, logger)
            total_processing_time = datetime.datetime.now() - start_time
            logger.info(f"websocket_endpoint:总处理图片耗时 {total_processing_time.total_seconds()} 秒")

            await websocket.send_bytes(processed_image)

            # 测量总处理耗时
            total_processing_time = datetime.datetime.now() - start_time
            logger.info(f"websocket_endpoint:总处理耗时 {total_processing_time.total_seconds()} 秒")

    except WebSocketDisconnect:
        logger.info("websocket_endpoint:客户端已断开连接")

async def process_image(file_path, logger):
    start_time = datetime.datetime.now()

    # 上传图片到服务器
    image_name_server = image_processor.upload_image(file_path)
    upload_time = datetime.datetime.now() - start_time
    logger.info(f"process_image:图片上传耗时 {upload_time.total_seconds()} 秒")

    with open(Path('static/workflow_api_huihua_2_1.json'), 'r') as file:
        prompt_workflow = json.load(file)

    prompt_workflow["13"]["inputs"]["image"] = f"/workspace/ComfyUI/input/{image_name_server}"
    prompt_workflow["3"]["inputs"]["denoise"] = 1.0
    prompt_workflow["3"]["inputs"]["seed"] = random.randint(0, 4284967295) * random.randint(0, 10000)
    prompt_workflow["6"]["inputs"]["text"] = "猫"
    prompt_workflow["29"]["inputs"]["width"] = 618
    prompt_workflow["29"]["inputs"]["height"] = 884

    uuid_value = str(uuid.uuid4())
    rabbitmq_host = os.getenv('RABBITMQ_HOST', 'rabbitmq')

    try:
        start_time = datetime.datetime.now()
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=rabbitmq_host))
        channel = connection.channel()
        channel.queue_declare(queue='uuid_queue')
        channel.basic_publish(exchange='', routing_key='uuid_queue', body=uuid_value)
        logger.info(f"process_image:成功将 UUID {uuid_value} 发布到 RabbitMQ")

        # 测量 RabbitMQ 消息发布耗时
        rabbitmq_publish_time = datetime.datetime.now() - start_time
        logger.info(f"process_image:RabbitMQ 消息发布耗时 {rabbitmq_publish_time.total_seconds()} 秒")

    except Exception as e:
        logger.error(f"process_image:发布 UUID 到 RabbitMQ 失败: {e}")
        return None
    finally:
        if connection.is_open:
            connection.close()
            logger.info("process_image:RabbitMQ 连接已关闭")

    start_time = datetime.datetime.now()
    prompt_id = image_processor.queue_prompt(prompt_workflow)
    if not prompt_id:
        return None

    # 测量队列操作耗时
    queue_time = datetime.datetime.now() - start_time
    logger.info(f"process_image:队列操作耗时 {queue_time.total_seconds()} 秒")

    image_processor.wait_for_image_processed_signal()

    images = image_processor.get_images()
    if images:
        logger.info(f"process_image:成功处理图片，返回第一张图片")
        return images[0]
    else:
        logger.info("process_image:没有处理的图片")
        return None
