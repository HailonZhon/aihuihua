# 使用官方 Python 运行时作为父镜像
FROM python:3.9-slim

# 设置工作目录
WORKDIR /usr/src/app

# 将当前目录内容复制到容器的 /usr/src/app
COPY . /usr/src/app

# 安装 requirements.txt 中指定的所有需要的包
RUN pip install  -r requirements.txt

# 安装必需的系统工具，并且设置 DNS 服务器
RUN echo "nameserver 8.8.8.8" > /etc/resolv.conf && \
    echo "nameserver 8.8.4.4" >> /etc/resolv.conf && \
    apt-get update && \
    apt-get install -y --no-install-recommends apt-utils gnupg curl wget ca-certificates

# 添加 RabbitMQ 官方签名密钥
RUN wget -O /usr/share/keyrings/rabbitmq-archive-keyring.gpg https://packages.rabbitmq.com/rabbitmq-release-signing-key.asc

# 添加 RabbitMQ APT 源到系统中
RUN echo "deb [signed-by=/usr/share/keyrings/rabbitmq-archive-keyring.gpg] http://packages.rabbitmq.com/debian buster main" | tee /etc/apt/sources.list.d/rabbitmq.list

# 安装 RabbitMQ 服务器
RUN apt-get update && \
    apt-get install -y rabbitmq-server

# 启用 RabbitMQ 管理插件
RUN rabbitmq-plugins enable rabbitmq_management

# 对外暴露 8000 端口
EXPOSE 8000

# 定义环境变量
ENV NAME World

# 容器启动时运行 main.py (根据 main.py 的实际位置调整路径)
CMD ["uvicorn", "app.ImageProcess.main:app", "--host", "0.0.0.0", "--port", "8000"]
