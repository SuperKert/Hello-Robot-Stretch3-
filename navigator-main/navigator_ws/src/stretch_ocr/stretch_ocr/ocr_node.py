#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import String
import cv2
import numpy as np
import os
import sys
import glob
import torch
import warnings
import shutil
import logging
from transformers import AutoModel, AutoTokenizer
from rapidfuzz import process, fuzz
from utils.hidden_prints import HiddenPrints
from text_postprocessing import SmartTextCorrector

# --- 1. UTILIDADES Y SILENCIADORES (Tu código original) ---

warnings.filterwarnings("ignore")
logging.getLogger("transformers").setLevel(logging.ERROR)

# --- 3. NODO ROS2 ---

class DeepSeekOCRNode(Node):
    def __init__(self, dict_path: str = '../resource/dict.txt'):
        super().__init__('deepseek_ocr_node')

        # Configuración
        os.environ["CUDA_VISIBLE_DEVICES"] = '0'
        self.model_name = 'deepseek-ai/DeepSeek-OCR'

        # Carpetas temporales para emular el sistema de archivos que requiere el modelo
        self.temp_dir = "/tmp/ros_ocr_temp"
        self.img_path = os.path.join(self.temp_dir, "frame.png")
        self.output_path = os.path.join(self.temp_dir, "out")

        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)
        if not os.path.exists(self.output_path):
            os.makedirs(self.output_path)

        # Cargar Modelo (Esto tardará unos segundos al arrancar)
        self.get_logger().info("Cargando modelo DeepSeek-OCR... (esto puede tardar)")
        with HiddenPrints():
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, trust_remote_code=True)
            self.model = AutoModel.from_pretrained(
                self.model_name,
                _attn_implementation='flash_attention_2',
                trust_remote_code=True,
                use_safetensors=True
            )
            self.model = self.model.eval().cuda().to(torch.bfloat16)

        self.corrector = SmartTextCorrector(dict_path=dict_path)
        self.get_logger().info(f"Cargado diccionario de corrección inteligente con {self.corrector.len_loaded_words} palabras")
        self.get_logger().info("Modelo cargado y listo.")

        # ROS Communications
        self.subscription = self.create_subscription(
            CompressedImage,
            '/camera/color/image_raw/compressed',
            self.image_callback,
            1)  # Queue size 1 para priorizar lo nuevo

        self.publisher_ = self.create_publisher(String, '/ocr/ocr_output', 10)

        # Variables de control de flujo
        self.latest_image_msg = None
        self.is_processing = False

        # Timer para procesar inferencia (independiente del callback de la cámara)
        # Esto evita que el callback se bloquee. Revisa cada 0.1s si hay trabajo.
        self.timer = self.create_timer(0.1, self.process_loop)

    def image_callback(self, msg):
        # Simplemente guardamos la referencia a la última imagen
        self.latest_image_msg = msg

    def get_latest_result_file(self, directory):
        files = glob.glob(os.path.join(directory, "*.mmd")) + glob.glob(os.path.join(directory, "*.txt"))
        if not files: return None
        return max(files, key=os.path.getmtime)

    def process_loop(self):
        # Si no hay imagen o ya estamos procesando, salimos
        if self.latest_image_msg is None or self.is_processing:
            return

        self.is_processing = True
        try:
            # 1. Decodificar imagen ROS Compressed -> OpenCV
            np_arr = np.frombuffer(self.latest_image_msg.data, np.uint8)
            cv_image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if cv_image is None:
                self.get_logger().warn("Fallo al decodificar imagen")
                return

            # 2. Guardar imagen temporalmente (el modelo requiere path)
            cv2.imwrite(self.img_path, cv_image)

            # 3. Limpiar carpeta de salida anterior
            for f in glob.glob(os.path.join(self.output_path, "*")):
                try:
                    os.remove(f)
                except:
                    pass

            # 4. Inferencia
            prompt = "<image>\nFree OCR."
            with HiddenPrints():
                try:
                    self.model.infer(
                        self.tokenizer,
                        prompt=prompt,
                        image_file=self.img_path,
                        output_path=self.output_path,
                        base_size=1024,
                        image_size=640,
                        crop_mode=True,
                        save_results=True,
                        test_compress=True
                    )
                except Exception as e:
                    self.get_logger().error(f"Error en inferencia: {str(e)}")
                    return

            # 5. Leer resultado y procesar con SmartTextCorrector
            result_file = self.get_latest_result_file(self.output_path)
            if result_file:
                with open(result_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                final_output = self.corrector.correct(content)

                # 6. Publicar
                if final_output:
                    msg = String()
                    msg.data = final_output
                    self.publisher_.publish(msg)
                    self.get_logger().info(f"Publicado: {final_output.replace(chr(10), ' | ')}")  # Muestra log limpio

        except Exception as e:
            self.get_logger().error(f"Error fatal en loop: {str(e)}")
        finally:
            # Limpieza y bandera
            self.latest_image_msg = None  # Vaciamos para esperar una nueva fresca
            self.is_processing = False

