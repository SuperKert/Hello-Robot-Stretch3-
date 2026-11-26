# LIBS
import os
import sys
import re
import logging
import tempfile
import warnings
import glob

# necessary OCR libraries
import cv2
import numpy as np
import torch
from rapidfuzz import process, fuzz
from transformers import AutoModel, AutoTokenizer

# ROS 2 libraries
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import String

# Configuration
os.environ["CUDA_VISIBLE_DEVICES"] = '0'
model_name = 'deepseek-ai/DeepSeek-OCR'

#Silenciador de warnings
warnings.filterwarnings("ignore")
logging.getLogger("transformers").setLevel(logging.ERROR)

class HiddenPrints:
    def __enter__(self):
        self._original_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout.close()
        sys.stdout = self._original_stdout

with HiddenPrints():
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    model = AutoModel.from_pretrained(model_name, _attn_implementation='flash_attention_2', trust_remote_code=True,
                                      use_safetensors=True)
    model = model.eval().cuda().to(torch.bfloat16)

#Corrector del OCR
class SmartTextCorrector:
    def __init__(self):
        self.known_signs = [
            "SALIDA DE EMERGENCIA", "ROMPER EN CASO DE INCENDIO",
            "EDIFICIO SUR", "EDIFICIO NORTE", "EDIFICIO ESTE", "EDIFICIO OESTE",
            "PLANTA PRIMERA", "PLANTA SEGUNDA",
            "ACCESO EDIFICIO NORTE", "ACCESO EDIFICIO SUR",
            "ACCESO EDIFICIO ESTE", "ACCESO EDIFICIO OESTE",
            "PASILLO 1", "PASILLO 2", "PASILLO 3", "PASILLO 4",
            "DPTO. TEORIA DE LA SEÑAL Y COM.", "DESPACHOS DE PROFESORES",
            "DEPARTAMENTO DE AUTOMATICA", "DPTO. CC. DE LA COMPUTACION",
            "DPTO. CC EMPRESARIALES - FILOLOGIA M.",
            "FISICA - MATEMATICAS - BRITISH COUNCIL",
            "DEPARTAMENTO DE ELECTRONICA", "LABORATORIOS DE INVESTIGACION",
            "DPTO. DE FISICA Y MATEMATICAS", "DIRECCION E. POLITECNICA SUP.",
            "SUBD -SECRT. E. POLITECNICA SUP.", "ADMINISTRACION DEL EDIFICIO"
        ]

    def _check_dynamic_pattern(self, text):
        # Detecta patrones tipo D S 101, D N 502, etc.
        pattern = r"(D)\s*([SNEO05])\s*([S5]?\d{3})"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            raw_dir = match.group(2).upper()
            direction = 'O' if raw_dir == '0' else ('S' if raw_dir == '5' else raw_dir)
            raw_code = match.group(3).upper()

            # Normalizar el código: eliminar S o 5 inicial y quedarse solo con los 3 dígitos
            if raw_code.startswith('S') or raw_code.startswith('5'):
                code = raw_code[1:]  # Quitar primer carácter
            else:
                code = raw_code  # Mantener los 3 dígitos tal cual

            # Asegurar que code tiene exactamente 3 dígitos con padding de ceros
            code = code.zfill(3)

            return f"D {direction} {code}"
        return None

    def _get_match(self, text, threshold=65):
        if not text or len(text.strip()) == 0: return None

        # 1. Comprobar patron de despacho
        dynamic = self._check_dynamic_pattern(text)
        if dynamic: return dynamic

        # 2. Match difuso con diccionario
        best_match, score, _ = process.extractOne(text.upper(), self.known_signs, scorer=fuzz.ratio)

        if score >= threshold:
            return best_match
        return None

    def correct(self, raw_text):
        if not raw_text: return ""

        clean_blob = raw_text.replace('**', '').replace('##', '').replace('\r', '')
        lines = clean_blob.split('\n')

        seen_items = set()
        valid_results = []

        i = 0
        while i < len(lines):
            current_line = lines[i].strip()
            if not current_line:
                i += 1
                continue

            # Obtener candidato (línea sola)
            match = self._get_match(current_line)

            final_match = None
            steps_to_jump = 1

            if match:
                final_match = match
            else:
                # Intentar unir con la siguiente línea (para frases partidas)
                if i + 1 < len(lines):
                    combined = current_line + " " + lines[i + 1].strip()
                    match_combined = self._get_match(combined)
                    if match_combined:
                        final_match = match_combined
                        steps_to_jump = 2

            # Guardar si es válido y nuevo
            if final_match:
                if final_match not in seen_items:
                    valid_results.append(final_match)
                    seen_items.add(final_match)

            i += steps_to_jump

        return "\n".join(valid_results)


# Función ya no necesaria - ahora trabajamos directamente en memoria
# def get_latest_file(directory):
#     files = glob.glob(os.path.join(directory, "*.mmd")) + glob.glob(os.path.join(directory, "*.txt"))
#     if not files: return None
#     files = [f for f in files if "corrected_output.txt" not in f]
#     if not files: return None
#     return max(files, key=os.path.getmtime)


# # --- 4. EJECUCIÓN ---
#
# image_file = "rgb/rgb_02100.png"
# output_path = "outputs/"
# prompt = "<image>\nFree OCR."
#
# if not os.path.exists(output_path):
#     os.makedirs(output_path)
#
# # Limpiar carpeta output (opcional, cuidado si tienes otras cosas)
# for f in glob.glob(os.path.join(output_path, "*")):
#     try:
#         os.remove(f)
#     except:
#         pass
#
# # Ejecutar inferencia
# with HiddenPrints():
#     try:
#         model.infer(tokenizer, prompt=prompt, image_file=image_file, output_path=output_path,
#                     base_size=1024, image_size=640, crop_mode=True, save_results=True, test_compress=True)
#     except Exception:
#         pass
#
# # Procesar resultado
# result_file = get_latest_file(output_path)
#
# if result_file:
#     with open(result_file, 'r', encoding='utf-8') as f:
#         content = f.read()
#
#     corrector = SmartTextCorrector()
#     final_output = corrector.correct(content)
#
#     if final_output:
#         # 1. Imprimir en consola (para que tú lo veas)
#         print(final_output)
#
#         # 2. GUARDAR EN ARCHIVO (Para el robot)
#         save_path = os.path.join(output_path, "corrected_output.txt")
#         with open(save_path, "w", encoding='utf-8') as f_out:
#             f_out.write(final_output)

# NODE INTEGRATION FOR ROS2
class DeepSeekOCRNode(Node):
    def __init__(self):
        super().__init__('deepseek_ocr_node')
        self.get_logger().info("Iniciando nodo OCR...")

        # --- CONFIGURACIÓN ---
        self.SKIP_FRAMES = 10  # Reducido para mejor respuesta en tiempo real
        self.frame_counter = 0

        # Reutilizar modelo y tokenizer precargados globalmente (evita carga duplicada)
        self.get_logger().info("Usando modelo DeepSeek-OCR precargado...")
        self.tokenizer = tokenizer
        self.model = model

        # Inicializar corrector de texto
        self.corrector = SmartTextCorrector()

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
        # Decodificar imagen comprimida
        try:
            np_arr = np.frombuffer(msg.data, np.uint8)
            image_np = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            if image_np is None:
                self.get_logger().warn("Imagen corrupta o no decodificable")
                return
        except Exception as e:
            self.get_logger().error(f"Error decodificando imagen: {e}")
            return

        # Guardar temporalmente la imagen
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as temp_img:
            temp_path = temp_img.name
            cv2.imwrite(temp_path, image_np)

        try:
            # Ejecutar OCR con el modelo DeepSeek
            prompt = "<image>\nFree OCR."

            with torch.no_grad():
                self.model.infer(
                    self.tokenizer,
                    prompt=prompt,
                    image_file=temp_path,
                    output_path=tempfile.gettempdir(),
                    base_size=1024,
                    image_size=640,
                    crop_mode=True,
                    save_results=True,
                    test_compress=False  # Más rápido en modo continuo
                )

            # Buscar el archivo de salida generado
            result_file = get_latest_file(tempfile.gettempdir())

            if result_file:
                with open(result_file, 'r', encoding='utf-8') as f:
                    raw_text = f.read()

                # Aplicar corrección de texto
                corrected_text = self.corrector.correct(raw_text)

                if corrected_text:
                    # Publicar texto corregido
                    msg_out = String()
                    msg_out.data = corrected_text
                    self.publisher_.publish(msg_out)
                    self.get_logger().info(f"OCR Corregido: {corrected_text}")

                # Limpiar archivo temporal de resultado
                try:
                    os.remove(result_file)
                except Exception as e:
                    self.get_logger().debug(f"No se pudo eliminar {result_file}: {e}")

        except Exception as e:
            self.get_logger().error(f"Error en inferencia OCR: {e}")
        finally:
            # Limpiar imagen temporal
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception as e:
                self.get_logger().debug(f"No se pudo eliminar imagen temporal: {e}")


def main(args=None):
    rclpy.init(args=args)
    node = DeepSeekOCRNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if rclpy.ok():
            node.destroy_node()
            rclpy.shutdown()


if __name__ == '__main__':
    main()