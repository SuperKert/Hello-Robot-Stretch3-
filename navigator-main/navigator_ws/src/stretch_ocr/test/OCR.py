from transformers import AutoModel, AutoTokenizer
import torch
import os
import re
import glob
import sys
import warnings
from rapidfuzz import process, fuzz
import logging
import gc

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

# --- 2. CARGA DEL MODELO (Se carga UNA sola vez fuera del bucle) ---
print("Cargando modelo DeepSeek-OCR...")
model_name = 'deepseek-ai/DeepSeek-OCR'
with HiddenPrints():
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    model = AutoModel.from_pretrained(model_name, _attn_implementation='flash_attention_2', trust_remote_code=True,
                                      use_safetensors=True)
    model = model.eval().cuda().to(torch.bfloat16)
print("Modelo cargado correctamente.\n")


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
            match = self._get_match(current_line)
            final_match = None
            steps_to_jump = 1
            if match:
                final_match = match
            else:
                if i + 1 < len(lines):
                    combined = current_line + " " + lines[i + 1].strip()
                    match_combined = self._get_match(combined)
                    if match_combined:
                        final_match = match_combined
                        steps_to_jump = 2
            if final_match:
                if final_match not in seen_items:
                    valid_results.append(final_match)
                    seen_items.add(final_match)
            i += steps_to_jump
        return "\n".join(valid_results)


def get_latest_file(directory):
    # Busca archivos output del modelo (normalmente .txt o .mmd)
    files = glob.glob(os.path.join(directory, "*.mmd")) + glob.glob(os.path.join(directory, "*.txt"))
    if not files: return None
    # Importante: Excluir el archivo 'corrected_output.txt' para no leerlo como input si volvemos a ejecutar
    files = [f for f in files if "corrected_output.txt" not in os.path.basename(f)]
    if not files: return None
    return max(files, key=os.path.getmtime)


# --- 4. EJECUCIÓN EN BUCLE OPTIMIZADA ---

input_folder = "rgb/"
root_output_folder = "outputs/"

# CONFIGURACIÓN DE SALTO (OPTIMIZACIÓN)
# 1 = Analiza todas.
# 3 = Analiza la 1, salta 2, analiza la 4... (3 veces más rápido)
K_FRAMES = 3

# 1. Obtener lista de todas las imágenes
image_extensions = ['*.png', '*.jpg', '*.jpeg']
image_files = []
for ext in image_extensions:
    image_files.extend(glob.glob(os.path.join(input_folder, ext)))

image_files = sorted(image_files)

if not image_files:
    print(f"No se encontraron imágenes en '{input_folder}'")
    sys.exit()

# --- AQUI ESTA LA MAGIA: FILTRADO DE LISTA ---
# Usamos slicing [::K_FRAMES] para coger solo 1 de cada K
images_to_process = image_files[::K_FRAMES]

print(f"Total imágenes en carpeta: {len(image_files)}")
print(f"Imágenes a procesar (saltando cada {K_FRAMES}): {len(images_to_process)}\n")

corrector = SmartTextCorrector()

# ... (parte anterior del código igual) ...

# 2. Iterar solo sobre las imágenes seleccionadas
for i, img_path in enumerate(images_to_process):

    filename = os.path.basename(img_path)
    base_name = os.path.splitext(filename)[0]

    print(f"[{i + 1}/{len(images_to_process)}] Procesando: {base_name} ...", end=" ", flush=True)

    current_output_dir = os.path.join(root_output_folder, base_name)

    if not os.path.exists(current_output_dir):
        os.makedirs(current_output_dir)

    # Limpieza de archivos anteriores
    for f in glob.glob(os.path.join(current_output_dir, "*")):
        try:
            os.remove(f)
        except:
            pass

    # --- INFERENCIA ---
    prompt = "<image>\nFree OCR."
    infer_success = False

    with HiddenPrints():
        try:
            model.infer(tokenizer, prompt=prompt, image_file=img_path, output_path=current_output_dir,
                        base_size=1024, image_size=640, crop_mode=True, save_results=True, test_compress=True)
            infer_success = True
        except Exception as e:
            pass

            # >>>>>>>> AQUI ESTÁ EL CAMBIO IMPORTANTE <<<<<<<<
    # Forzamos limpieza de memoria RAM y VRAM (GPU)
    gc.collect()
    torch.cuda.empty_cache()
    # >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>

    if not infer_success:
        print("Error (Saltado).")
        # Si falla, intentamos limpiar más fuerte por si acaso para la siguiente
        torch.cuda.ipc_collect()
        continue

    # --- CORRECCIÓN ---
    result_file = get_latest_file(current_output_dir)

    if result_file:
        with open(result_file, 'r', encoding='utf-8') as f:
            content = f.read()

        final_output = corrector.correct(content)

        status_msg = "OK" if final_output.strip() else "VACÍO"

        save_path = os.path.join(current_output_dir, "corrected_output.txt")
        with open(save_path, "w", encoding='utf-8') as f_out:
            f_out.write(final_output)

        print(f"{status_msg}. Guardado.")
    else:
        print("Fallo (No output).")

print("\n--- PROCESO TERMINADO ---")