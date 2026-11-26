# Usamos la imagen oficial de ROS 2 (Humble o Jazzy, cambia según necesites)
FROM ros:humble-ros-base

# 1. Instalar dependencias del sistema (pip, git, herramientas de compilación)
RUN apt-get update && apt-get install -y \
    python3-pip \
    git \
    ros-humble-cv-bridge \
    ros-humble-vision-opencv \
    && rm -rf /var/lib/apt/lists/*

# 2. Instalar las librerías de Python para DeepSeek / OCR
RUN pip3 install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
RUN pip3 install opencv-python transformers numpy

# 3. Configurar el entorno para que 'source' se ejecute automáticamente
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]