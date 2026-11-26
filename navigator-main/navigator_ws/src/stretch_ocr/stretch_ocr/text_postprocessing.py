import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
from std_msgs.msg import String
from rapidfuzz import process, fuzz


class SmartTextCorrector:
    def __init__(self, dict_path : str = '..reource/dict.txt'):
        self.known_signs = list()
        # load know signs from dict path
        with open(dict_path, 'r') as f:
            for line in f:
                word = line.strip()
                if word:
                    self.known_signs.append(word)

    @property
    def len_loaded_words(self):
        return len(self.known_signs)

    def _check_dynamic_pattern(self, text):
        pattern = r"(D)\s*([SNEO05])\s*([S5]?\d{3})"
        match = re_match = __import__('re').search(pattern, text, __import__('re').IGNORECASE)
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
        if len(text) < 2:
            if text.upper() in ["N", "S", "E", "O"]: return text.upper()
            return None
        best_match, score, _ = process.extractOne(text.upper(), self.known_signs, scorer=fuzz.ratio)
        if score >= threshold: return best_match
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