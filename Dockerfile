FROM ubuntu:20.04

# 设置时区
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 安装系统依赖
RUN apt update && apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    mpv \
    x11-apps \
    pulseaudio \
    && rm -rf /var/lib/apt/lists/*

# 创建工作目录
WORKDIR /app

# 复制应用程序文件
COPY . .

# 安装Python依赖
RUN pip3 install -r requirements.txt

# 创建启动脚本
RUN echo '#!/bin/bash\npython3 -m src.app' > start.sh && chmod +x start.sh

# 设置启动命令
CMD ["./start.sh"]