import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import String
import cv2
import numpy as np
import torch
import os
import tempfile
import re
import json
from transformers import AutoModel, AutoTokenizer

os.environ["CUDA_VISIBLE_DEVICES"] = '0'


class DeepSeekOCRNode(Node):
    def __init__(self):
        super().__init__('deepseek_ocr_node')
        self.get_logger().info("Cargando nodo OCR...")

        # --- CONFIGURACIÓN ---
        self.SKIP_FRAMES = 15  # Procesamos 1 de cada 5 imágenes
        self.frame_counter = 0

        self.get_logger().info("Cargando modelo DeepSeek-OCR...")
        self.model_name = 'deepseek-ai/DeepSeek-OCR'

        try:
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, trust_remote_code=True)

            # Fix para warnings de padding
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token

            self.model = AutoModel.from_pretrained(
                self.model_name,
                trust_remote_code=True,
                use_safetensors=True
            )
            self.model = self.model.eval().cuda().to(torch.bfloat16)

            # Rompemos bucles
            self.model.generation_config.pad_token_id = self.tokenizer.pad_token_id
            self.model.generation_config.do_sample = False
            self.model.generation_config.repetition_penalty = 1.2

            self.get_logger().info("¡Modelo listo!")

        except Exception as e:
            self.get_logger().error(f"Error fatal cargando modelo: {e}")
            raise e

        # --- ROS Setup ---
        self.subscription = self.create_subscription(
            CompressedImage,
            '/camera/color/image_raw/compressed',
            self.image_callback,
            10
        )
        self.publisher_ = self.create_publisher(String, 'ocr_text', 10)
        self.is_processing = False

        self.get_logger().info("Pub/Sub configurados correctamente. Nodo OCR listo.")

    def parse_deepseek_output(self, raw_text):
        """
        Parsea la salida para encontrar texto y coordenadas
        """
        detected_objects = []
        pattern = r'<\|ref\|>(.*?)<\|/ref\|><\|det\|>\[\[(.*?)\]\]<\|/det\|>'
        matches = re.findall(pattern, raw_text, re.DOTALL)

        for text_content, bbox_str in matches:
            text_clean = text_content.strip()

            # Filtro anti-ruido: ignorar si es solo 1 digito o vacío
            if (text_clean.isdigit() and len(text_clean) < 2) or not text_clean:
                continue

            try:
                bbox = [int(x.strip()) for x in bbox_str.split(',')]
                if len(bbox) == 4:
                    detected_objects.append({
                        "label": text_clean,
                        "bbox": bbox
                    })
            except ValueError:
                continue

        return detected_objects

    def image_callback(self, msg):
        self.frame_counter += 1
        if self.frame_counter % self.SKIP_FRAMES != 0:
            return

        if self.is_processing:
            return

        self.is_processing = True
        try:
            self.process_image(msg)
        except Exception as e:
            self.get_logger().error(f"Error procesando: {e}")
        finally:
            self.is_processing = False

    def process_image(self, msg):
        np_arr = np.frombuffer(msg.data, np.uint8)
        image_np = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if image_np is None: return

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp_img:
            temp_path = temp_img.name
            cv2.imwrite(temp_path, image_np)

        try:
            self.model.generation_config.do_sample = False
            self.model.generation_config.repetition_penalty = 1.2

            prompt = "<image>\n<|grounding|>Read the text and provide locations."

            with torch.no_grad():
                res = self.model.infer(
                    self.tokenizer,
                    prompt=prompt,
                    image_file=temp_path,
                    output_path=os.path.dirname(temp_path),
                    base_size=1024,
                    image_size=640,
                    crop_mode=True,
                    save_results=False,
                    test_compress=False
                )

            raw_output = str(res)
            # self.get_logger().info(f"Raw Output: {raw_output[:100]}...") # Debug opcional

            parsed_data = self.parse_deepseek_output(raw_output)

            if parsed_data:
                json_output = json.dumps(parsed_data)
                msg_out = String()
                msg_out.data = json_output
                self.publisher_.publish(msg_out)
                self.get_logger().info(f"Detectado: {json_output}")

        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


def main(args=None):
    rclpy.init(args=args)
    node = DeepSeekOCRNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if rclpy.ok():
            node.destroy_nClode()
            rclpy.shutdown()


if __name__ == '__main__':
    main()