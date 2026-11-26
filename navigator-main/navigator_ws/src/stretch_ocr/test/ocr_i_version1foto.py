from transformers import AutoModel, AutoTokenizer
import torch
import os
import re
import glob
import sys
import warnings
from rapidfuzz import process, fuzz
import logging

# --- 1. SILENCIADOR TOTAL (WARNINGS + PRINTS) ---
warnings.filterwarnings("ignore")
logging.getLogger("transformers").setLevel(logging.ERROR)


class HiddenPrints:
    def __enter__(self):
        self._original_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout.close()
        sys.stdout = self._original_stdout


os.environ["CUDA_VISIBLE_DEVICES"] = '0'

# --- 2. CARGA DEL MODELO ---
model_name = 'deepseek-ai/DeepSeek-OCR'
with HiddenPrints():
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    model = AutoModel.from_pretrained(model_name, _attn_implementation='flash_attention_2', trust_remote_code=True,
                                      use_safetensors=True)
    model = model.eval().cuda().to(torch.bfloat16)


# --- 3. CEREBRO DEL ROBOT MEJORADO ---
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
            if raw_code.startswith('5') and len(raw_code) == 4:
                code = 'S' + raw_code[1:]
            elif not raw_code.startswith('S') and len(raw_code) == 3:
                code = 'S' + raw_code
            else:
                code = raw_code
            return f"D {direction} {code}"
        return None

    def _get_match(self, text, threshold=65):
        if not text or len(text.strip()) == 0: return None

        # 1. Chequeo de despacho dinámico (Regex)
        dynamic = self._check_dynamic_pattern(text)
        if dynamic: return dynamic

        # 2. Match difuso con la lista conocida
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


def get_latest_file(directory):
    files = glob.glob(os.path.join(directory, "*.mmd")) + glob.glob(os.path.join(directory, "*.txt"))
    if not files: return None
    # Excluir el archivo de salida corregido si ya existe para no leerlo como input
    files = [f for f in files if "corrected_output.txt" not in f]
    if not files: return None
    return max(files, key=os.path.getmtime)


# --- 4. EJECUCIÓN ---

image_file = "rgb/rgb_02100.png"
output_path = "outputs/"
prompt = "<image>\nFree OCR."

if not os.path.exists(output_path):
    os.makedirs(output_path)

# Limpiar carpeta output (opcional, cuidado si tienes otras cosas)
for f in glob.glob(os.path.join(output_path, "*")):
    try:
        os.remove(f)
    except:
        pass

# Ejecutar inferencia
with HiddenPrints():
    try:
        model.infer(tokenizer, prompt=prompt, image_file=image_file, output_path=output_path,
                    base_size=1024, image_size=640, crop_mode=True, save_results=True, test_compress=True)
    except Exception:
        pass

# Procesar resultado
result_file = get_latest_file(output_path)

if result_file:
    with open(result_file, 'r', encoding='utf-8') as f:
        content = f.read()

    corrector = SmartTextCorrector()
    final_output = corrector.correct(content)

    if final_output:
        # 1. Imprimir en consola (para que tú lo veas)
        print(final_output)

        # 2. GUARDAR EN ARCHIVO (Para el robot)
        save_path = os.path.join(output_path, "corrected_output.txt")
        with open(save_path, "w", encoding='utf-8') as f_out:
            f_out.write(final_output)

        # print(f"Guardado en: {save_path}") # Descomenta si quieres confirmación