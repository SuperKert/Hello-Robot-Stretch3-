# LIBS
import os
import sys
import re
import logging
import warnings

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

# Modo debug
DEBUG_MODE = True  # Cambiar a False para desactivar visualización en tiempo real

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

            #Quedarse solo con los 3 dígitos
            if raw_code.startswith('S') or raw_code.startswith('5'):
                code = raw_code[1:]
            else:
                code = raw_code

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

# NODE INTEGRATION FOR ROS2
class DeepSeekOCRNode(Node):
    def __init__(self):
        super().__init__('deepseek_ocr_node')
        self.get_logger().info("Iniciando nodo OCR...")

        # --- CONFIGURACIÓN ---
        self.SKIP_FRAMES = 10  #N de cada frames se van a analizar
        self.frame_counter = 0
        self.DEBUG_MODE = DEBUG_MODE

        # Reutilizar modelo y tokenizer precargados globalmente (evita carga duplicada)
        self.get_logger().info("Usando modelo DeepSeek-OCR precargado...")
        self.tokenizer = tokenizer
        self.model = model

        # Inicializar corrector de texto
        self.corrector = SmartTextCorrector()

        # Variables para visualización debug
        if self.DEBUG_MODE:
            cv2.namedWindow('OCR Debug - DeepSeek', cv2.WINDOW_NORMAL)
            cv2.resizeWindow('OCR Debug - DeepSeek', 1280, 720)
            self.get_logger().info("🎥 Modo DEBUG activado - Ventana OpenCV creada")

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
        # Decodificar imagen comprimida directamente en memoria
        try:
            np_arr = np.frombuffer(msg.data, np.uint8)
            image_np = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            if image_np is None:
                self.get_logger().warn("Imagen corrupta o no decodificable")
                return
        except Exception as e:
            self.get_logger().error(f"Error decodificando imagen: {e}")
            return

        # Crear copia para visualización debug (antes de convertir a RGB)
        debug_image = image_np.copy() if self.DEBUG_MODE else None

        try:
            # Ejecutar OCR directamente con la imagen en memoria (sin guardar en disco)
            prompt = "<image>\nFree OCR."
            # Convertir BGR (OpenCV) a RGB (PIL)
            image_rgb = cv2.cvtColor(image_np, cv2.COLOR_BGR2RGB)
            with torch.no_grad():
                # Pasar la imagen directamente como numpy array en memoria
                result = self.model.infer(
                    self.tokenizer,
                    prompt=prompt,
                    image=image_rgb,  # Usar 'image' en lugar de 'image_file'
                    base_size=1024,
                    image_size=640,
                    crop_mode=True,
                    save_results=False,  # No guardar archivos
                    test_compress=False
                )
            # El resultado viene directamente como string
            if result and isinstance(result, str):
                raw_text = result
            elif result and hasattr(result, 'text'):
                raw_text = result.text
            else:
                self.get_logger().warn("No se pudo extraer texto del resultado")
                return
            # Aplicar corrección de texto
            corrected_text = self.corrector.correct(raw_text)

            # ===== VISUALIZACIÓN DEBUG =====
            if self.DEBUG_MODE:
                self._show_debug_window(debug_image, raw_text, corrected_text)
            # ================================

            if corrected_text:
                # Publicar texto corregido
                msg_out = String()
                msg_out.data = corrected_text
                self.publisher_.publish(msg_out)
                self.get_logger().info(f"OCR Corregido: {corrected_text}")
        except Exception as e:
            self.get_logger().error(f"Error en inferencia OCR: {e}")
            import traceback
            self.get_logger().error(f"Traceback: {traceback.format_exc()}")

    def _show_debug_window(self, image, raw_text, corrected_text):
        """Muestra ventana de debug con imagen y texto OCR superpuesto"""
        try:
            # Crear copia para no modificar original
            display_img = image.copy()
            h, w = display_img.shape[:2]

            # Crear zona oscura en la parte superior para el texto
            overlay = display_img.copy()
            cv2.rectangle(overlay, (0, 0), (w, min(300, h//3)), (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.7, display_img, 0.3, 0, display_img)

            # Configuración de texto
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.6
            thickness = 2
            color_raw = (100, 100, 255)  # Rojo claro para texto raw
            color_corrected = (100, 255, 100)  # Verde para texto corregido

            y_offset = 30

            # Título
            cv2.putText(display_img, "DeepSeek OCR - Debug Mode", (10, y_offset),
                       font, 0.7, (255, 255, 255), 2)
            y_offset += 40

            # Texto RAW (del modelo)
            cv2.putText(display_img, "RAW OCR:", (10, y_offset),
                       font, font_scale, color_raw, thickness)
            y_offset += 30

            if raw_text:
                # Dividir en líneas si es muy largo
                raw_lines = raw_text.split('\n')[:3]  # Máximo 3 líneas
                for line in raw_lines:
                    if len(line) > 80:
                        line = line[:77] + "..."
                    cv2.putText(display_img, line, (20, y_offset),
                               font, 0.5, (200, 200, 255), 1)
                    y_offset += 25
            else:
                cv2.putText(display_img, "(vacio)", (20, y_offset),
                           font, 0.5, (150, 150, 150), 1)
                y_offset += 25

            y_offset += 15

            # Texto CORREGIDO
            cv2.putText(display_img, "CORRECTED:", (10, y_offset),
                       font, font_scale, color_corrected, thickness)
            y_offset += 30

            if corrected_text:
                corrected_lines = corrected_text.split('\n')[:3]
                for line in corrected_lines:
                    if len(line) > 80:
                        line = line[:77] + "..."
                    cv2.putText(display_img, line, (20, y_offset),
                               font, 0.5, (150, 255, 150), 1)
                    y_offset += 25
            else:
                cv2.putText(display_img, "(sin coincidencias)", (20, y_offset),
                           font, 0.5, (150, 150, 150), 1)

            # Mostrar frame counter
            cv2.putText(display_img, f"Frame: {self.frame_counter}", (w - 150, 30),
                       font, 0.6, (255, 255, 0), 2)

            # Mostrar imagen
            cv2.imshow('OCR Debug - DeepSeek', display_img)
            cv2.waitKey(1)  # Necesario para actualizar ventana

        except Exception as e:
            self.get_logger().error(f"Error en visualización debug: {e}")


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
