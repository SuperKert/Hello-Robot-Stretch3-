from transformers import AutoModel, AutoTokenizer
import torch
import os
import re
import glob
import sys
import warnings  # Para controlar los warnings
from rapidfuzz import process, fuzz
import logging

# --- 1. SILENCIADOR TOTAL (WARNINGS + PRINTS) ---

# A) Silenciar Warnings de Python/Transformers
warnings.filterwarnings("ignore")  # Ignora todos los warnings
logging.getLogger("transformers").setLevel(logging.ERROR)


# B) Silenciar Prints de DeepSeek
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
            "N", "S", "E", "O",
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

        dynamic = self._check_dynamic_pattern(text)
        if dynamic: return dynamic

        # Filtro extra de seguridad: Si es una sola letra, tiene que ser EXACTA
        if len(text) < 2:
            if text.upper() in ["N", "S", "E", "O"]:
                return text.upper()
            return None  # Si es basura de 1 letra que no es N/S/E/O, fuera

        best_match, score, _ = process.extractOne(text.upper(), self.known_signs, scorer=fuzz.ratio)

        if score >= threshold:
            return best_match
        return None

    def correct(self, raw_text):
        if not raw_text: return ""

        clean_blob = raw_text.replace('**', '').replace('##', '').replace('\r', '')
        lines = clean_blob.split('\n')

        # Usamos un conjunto (set) auxiliar para detectar duplicados al vuelo
        seen_items = set()
        valid_results = []

        i = 0
        while i < len(lines):
            current_line = lines[i].strip()
            if not current_line:
                i += 1
                continue

            # Obtener candidato
            match = self._get_match(current_line)

            # Lógica principal de Match
            final_match = None
            steps_to_jump = 1

            if match:
                final_match = match
            else:
                # Intentar unir con la siguiente
                if i + 1 < len(lines):
                    combined = current_line + " " + lines[i + 1].strip()
                    match_combined = self._get_match(combined)
                    if match_combined:
                        final_match = match_combined
                        steps_to_jump = 2

            # --- AQUÍ ESTÁ LA SOLUCIÓN AL BUCLE INFINITO ---
            if final_match:
                # Solo lo añadimos si NO lo hemos visto ya en esta imagen
                if final_match not in seen_items:
                    valid_results.append(final_match)
                    seen_items.add(final_match)

            i += steps_to_jump

        return "\n".join(valid_results)


def get_latest_file(directory):
    files = glob.glob(os.path.join(directory, "*.mmd")) + glob.glob(os.path.join(directory, "*.txt"))
    if not files: return None
    return max(files, key=os.path.getmtime)


# --- 4. EJECUCIÓN ---

image_file = "rgb/rgb_04328.png"
output_path = "outputs/"
prompt = "<image>\nFree OCR."

if not os.path.exists(output_path):
    os.makedirs(output_path)

for f in glob.glob(os.path.join(output_path, "*")):
    try:
        os.remove(f)
    except:
        pass

with HiddenPrints():
    try:
        model.infer(tokenizer, prompt=prompt, image_file=image_file, output_path=output_path,
                    base_size=1024, image_size=640, crop_mode=True, save_results=True, test_compress=True)
    except Exception:
        pass

result_file = get_latest_file(output_path)
if result_file:
    with open(result_file, 'r', encoding='utf-8') as f:
        content = f.read()

    corrector = SmartTextCorrector()
    final_output = corrector.correct(content)

    if final_output:
        print(final_output)