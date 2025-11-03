import string
from fast_plate_ocr import LicensePlateRecognizer
import os
import csv

# Note: scapy and socket were previously imported but unused; removed to satisfy linter

# Initialize the Fast Plate OCR recognizer
# Model can be configured via FAST_PLATE_OCR_MODEL env var
# Example models: "cct-xs-v1-global-model", "global-plates-mobile-vit-v2-model"
_FPOCR_MODEL_NAME = os.getenv("FAST_PLATE_OCR_MODEL", "cct-xs-v1-global-model")
recognizer = LicensePlateRecognizer(_FPOCR_MODEL_NAME)

special_characters = [
    "-",
    " ",
    ".",
    "'",
    '"',
    "`",
    "~",
    "!",
    "@",
    "#",
    "$",
    "%",
    "^",
    "&",
    "*",
    "(",
    ")",
    "_",
    "+",
    "=",
    "{",
    "}",
    "[",
    "]",
    "|",
    "\\",
    ":",
    ";",
    "<",
    ">",
    ",",
    ".",
    "/",
    "?",
]

# Mapping dictionaries for character conversion
dict_char_to_int = {"O": "0", "I": "1", "J": "3", "A": "4", "G": "6", "S": "5"}

dict_int_to_char = {"0": "O", "1": "I", "3": "J", "4": "A", "6": "G", "5": "S"}


def write_csv(results, output_path):
    """
    Write the results to a CSV file.

    Args:
        results (dict): Dictionary containing the results.
        output_path (str): Path to the output CSV file.
    """
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        f.write(
            "{},{},{},{},{},{},{}\n".format(
                "frame_nmr",
                "car_id",
                "car_bbox",
                "license_plate_bbox",
                "license_plate_bbox_score",
                "license_number",
                "license_number_score",
            )
        )

        for frame_nmr in results.keys():
            for car_id in results[frame_nmr].keys():
                print(results[frame_nmr][car_id])
                if (
                    "car" in results[frame_nmr][car_id].keys()
                    and "license_plate" in results[frame_nmr][car_id].keys()
                    and "text" in results[frame_nmr][car_id]["license_plate"].keys()
                ):
                    f.write(
                        "{},{},{},{},{},{},{}\n".format(
                            frame_nmr,
                            car_id,
                            "[{} {} {} {}]".format(
                                results[frame_nmr][car_id]["car"]["bbox"][0],
                                results[frame_nmr][car_id]["car"]["bbox"][1],
                                results[frame_nmr][car_id]["car"]["bbox"][2],
                                results[frame_nmr][car_id]["car"]["bbox"][3],
                            ),
                            "[{} {} {} {}]".format(
                                results[frame_nmr][car_id]["license_plate"]["bbox"][0],
                                results[frame_nmr][car_id]["license_plate"]["bbox"][1],
                                results[frame_nmr][car_id]["license_plate"]["bbox"][2],
                                results[frame_nmr][car_id]["license_plate"]["bbox"][3],
                            ),
                            results[frame_nmr][car_id]["license_plate"]["bbox_score"],
                            results[frame_nmr][car_id]["license_plate"]["text"],
                            results[frame_nmr][car_id]["license_plate"]["text_score"],
                        )
                    )
        f.close()


def write_log_entry(data_row, csv_header, log_file="log.csv"):
    """将一行数据写入到 CSV 日志文件"""
    file_exists = os.path.isfile(log_file)
    try:
        with open(log_file, mode="a", newline="", encoding="utf-8") as csv_file:
            writer = csv.writer(csv_file)
            if (
                not file_exists or os.path.getsize(log_file) == 0
            ):  # 如果文件不存在或是空的
                writer.writerow(csv_header)  # 写入表头
                print(f"CSV 日志文件 '{log_file}' 已创建并写入表头。")
            writer.writerow(data_row)
    except Exception as e:
        print(f"写入日志到 '{log_file}' 时发生错误: {e}")

def write_log_to_txt(text, log_file="log.txt"):
    """将一行数据写入到 TXT 日志文件"""
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            line = str(text)
            if not line.endswith("\n"):
                line += "\n"
            f.write(line)
    except Exception as e:
        print(f"写入日志到 '{log_file}' 时发生错误: {e}")


def license_complies_format(text):
    """
    Check if the license plate text complies with common Australian formats.
    (e.g., LLLNNN, NNNLLL, LLNNLL).

    Args:
        text (str): License plate text.

    Returns:
        bool: True if the license plate complies with a recognized format, False otherwise.
    """
    if len(text) != 6:  # Australian plates are commonly 6 characters
        return False

    # Helper function to check if a character is a letter (or OCR equivalent)
    def is_letter(char):
        return char in string.ascii_uppercase or char in dict_int_to_char.keys()

    # Helper function to check if a character is a digit (or OCR equivalent)
    def is_digit(char):
        return (
            char in ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]
            or char in dict_char_to_int.keys()
        )

    # Check for LLLNNN format
    if (
        is_letter(text[0])
        and is_letter(text[1])
        and is_letter(text[2])
        and is_digit(text[3])
        and is_digit(text[4])
        and is_digit(text[5])
    ):
        return True

    # Check for NNNLLL format
    if (
        is_digit(text[0])
        and is_digit(text[1])
        and is_digit(text[2])
        and is_letter(text[3])
        and is_letter(text[4])
        and is_letter(text[5])
    ):
        return True

    # Check for LLNNLL format (e.g., New South Wales)
    if (
        is_letter(text[0])
        and is_letter(text[1])
        and is_digit(text[2])
        and is_digit(text[3])
        and is_letter(text[4])
        and is_letter(text[5])
    ):
        return True

    # Check for LLDNLL format (e.g. Victoria)
    # Example: ASD9FH
    if (
        is_letter(text[0])
        and is_letter(text[1])
        and is_digit(text[2])
        and is_letter(text[3])
        and is_letter(text[4])
        and is_letter(text[5])
    ):
        return True

    # Check for NLLLLL format (e.g. Victoria)
    # Example: 1ASHFH
    if (
        is_digit(text[0])
        and is_letter(text[1])
        and is_letter(text[2])
        and is_letter(text[3])
        and is_letter(text[4])
        and is_letter(text[5])
    ):
        return True

    # Check for LLLNLN format (e.g. Queensland)
    # Example: ABC1D2
    if (
        is_letter(text[0])
        and is_letter(text[1])
        and is_letter(text[2])
        and is_digit(text[3])
        and is_letter(text[4])
        and is_digit(text[5])
    ):
        return True

    return False


def format_license(text):
    """
    Format the license plate text by converting characters using the mapping dictionaries.
    It attempts to correct common OCR errors for 6-character plates.

    Args:
        text (str): License plate text (expected to be 6 characters).

    Returns:
        str: Formatted license plate text.
    """
    if len(text) != 6:
        # Or handle this error as appropriate, though license_complies_format should catch it first
        return text

    license_plate_ = ""
    for char_val in text:
        corrected_char = char_val
        # If it's a digit, see if it's a misread letter (e.g., '0' for 'O')
        if char_val in dict_int_to_char:
            # Check if the *original* was likely a letter based on its position or context if needed
            # For simplicity here, we assume dict_int_to_char implies it *could* be a letter
            # This part might need more sophisticated logic if ambiguity is high
            pass  # Keep it as is, or decide based on expected pattern

        # If it's a letter, see if it's a misread digit (e.g., 'O' for '0')
        if char_val in dict_char_to_int:
            corrected_char = dict_char_to_int[char_val]
            license_plate_ += corrected_char
            continue

        # If it was a digit that could be a letter, prefer the letter if it makes sense
        # This logic is a bit simplified and might need refinement based on actual OCR behavior
        # and expected plate patterns. The current license_complies_format already checks patterns.
        if char_val in dict_int_to_char.keys() and char_val.isdigit():
            # This condition means it IS a digit, but it has a potential letter counterpart.
            # e.g. if char_val is '0', dict_int_to_char['0'] is 'O'.
            # We need to decide if it *should* be a letter.
            # For now, let's assume if it's in dict_int_to_char, it was intended as a letter if it was read as a number.
            # This is a common OCR correction direction.
            # However, the original code's mapping was position-dependent.
            # A more robust way would be to check against the identified pattern if possible,
            # or simply apply corrections that make sense (e.g. 0->O, 1->I is common).

            # Simplified: if it's a digit and has a char mapping, assume it should be the char.
            # This might be too aggressive if a position is truly numeric.
            # Given the new compliance check, this function is more about canonicalization.
            pass  # Let's stick to char_to_int correction for now, as int_to_char is less common for digits.

        license_plate_ += char_val  # Use the original or corrected-to-digit character

    # The original format_license had specific positional mapping.
    # With variable formats, we make a best guess or rely on compliance check to validate.
    # A simple re-application of rules: if a char is in dict_char_to_int, convert it. If in dict_int_to_char, convert it.
    # This needs to be careful not to map 'O' to '0' and then back to 'O'.

    # Revised approach: Iterate and apply corrections based on original character type
    final_plate = ""
    for char_val in text.upper():  # Ensure uppercase for dictionary keys
        if char_val in dict_char_to_int.keys():  # e.g., O -> 0, S -> 5
            final_plate += dict_char_to_int[char_val]
        elif (
            char_val in dict_int_to_char.keys()
        ):  # e.g., 0 -> O, 5 -> S (less common if already a char)
            # This case is tricky: if char_val is '0', it maps to 'O'.
            # We only want to do this if the original char_val was a digit.
            if char_val.isdigit():
                final_plate += dict_int_to_char[char_val]
            else:
                final_plate += char_val  # It was a letter that also happens to be a key in dict_int_to_char, keep as letter
        else:
            final_plate += char_val
    return final_plate


# def get_text_with_confidence(image, lang='eng', min_confidence=0):
#     """
#     Extracts text and confidence scores from an image using Tesseract OCR.

#     Args:
#         image_path (str): Path to the input image file.
#         lang (str): Language code for OCR (e.g., 'eng', 'fra').
#         min_confidence (int): Minimum confidence score (0-100) to include a word.
#                              Words with confidence -1 (often non-word segments)
#                              are typically filtered out.

#     Returns:
#         list: A list of dictionaries, where each dictionary contains:
#               {'text': recognized_word, 'confidence': confidence_score}
#               Returns an empty list if an error occurs or no text is found.
#     """
#     results = []
#     try:
#         # Or with OpenCV:
#         # img_cv = cv2.imread(image_path)
#         # To use OpenCV image with pytesseract, you don't need to convert it to PIL Image
#         # data = pytesseract.image_to_data(img_cv, lang=lang, output_type=pytesseract.Output.DICT)

#         # Get detailed OCR data as a dictionary
#         data = pytesseract.image_to_data(image, lang=lang, output_type=pytesseract.Output.DICT)
#         print('data', data)
#         # Number of recognized boxes/words
#         num_boxes = len(data['level'])

#         for i in range(num_boxes):
#             # We are interested in word-level information (level 5)
#             # and confidences that are not -1 (which often means it's not a recognized word)
#             confidence = int(data['conf'][i])
#             recognized_text = data['text'][i].strip()

#             # Filter out empty strings and low confidence results
#             if recognized_text and confidence >= min_confidence and data['level'][i] == 5: # Level 5 is word
#                 results.append({
#                     'text': recognized_text,
#                     'confidence': confidence,
#                     'left': data['left'][i],
#                     'top': data['top'][i],
#                     'width': data['width'][i],
#                     'height': data['height'][i]
#                 })

#     except FileNotFoundError:
#         print(f"Error: Image file not found at '{image_path}'")
#     except pytesseract.TesseractNotFoundError:
#         print("Error: Tesseract is not installed or not in your PATH.")
#         print("Please install Tesseract and/or configure pytesseract.tesseract_cmd.")
#     except Exception as e:
#         print(f"An error occurred: {e}")

#     return results


def read_license_plate(license_plate_crop, remove_special_characters=True):
    """
    Read the license plate text from the given cropped image.

    Args:
        license_plate_crop (PIL.Image.Image): Cropped image containing the license plate.

    Returns:
        tuple: Tuple containing the formatted license plate text and its confidence score.
    """
    # Fast Plate OCR expects an image path or ndarray depending on version.
    # To be version-agnostic, save the crop to a temporary file and run OCR on it.
    try:
        import tempfile
        import cv2

        with tempfile.NamedTemporaryFile(suffix=".png", delete=True) as tmp:
            # Ensure we can write regardless of grayscale or color input
            cv2.imwrite(tmp.name, license_plate_crop)  # pylint: disable=no-member
            result = recognizer.run(tmp.name)

        # Parse result into (text, score)
        text = None
        score = None

        # Handle simple array format like ['1WT1PP___']
        if isinstance(result, (list, tuple)) and len(result) > 0:
            first = result[0]
            if isinstance(first, str):
                # Simple string array format
                text = first
                score = None  # No score provided in this format
            elif isinstance(first, dict):
                text = (
                    first.get("text")
                    or first.get("plate")
                    or first.get("license_plate")
                )
                score = (
                    first.get("score") or first.get("confidence") or first.get("prob")
                )
            elif isinstance(first, (list, tuple)):
                # Try tuple formats like (text, score) or (bbox, text, score)
                if len(first) >= 2 and isinstance(first[0], str):
                    text = first[0]
                    score = first[1] if len(first) > 1 else None
                elif len(first) >= 3 and isinstance(first[1], str):
                    text = first[1]
                    score = first[2]
        elif isinstance(result, dict):
            text = (
                result.get("text") or result.get("plate") or result.get("license_plate")
            )
            score = (
                result.get("score") or result.get("confidence") or result.get("prob")
            )

        if text is None:
            return None, None

        # Normalize text
        normalized_text = (
            "".join(char for char in str(text) if (char not in special_characters))
            if remove_special_characters
            else str(text)
        )

        # Normalize score to float if possible
        try:
            score_val = float(score) if score is not None else None
        except Exception:
            score_val = None

        return normalized_text, score_val
    except Exception as e:
        print(f"Fast Plate OCR error: {e}")
        return None, None


# --- Custom String Similarity Functions ---

# Define confusable character pairs and their substitution cost
# These pairs are treated as similar. Add more as needed.
# The pairs are stored as sorted tuples to ensure order doesn't matter for lookup.
CONFUSABLE_PAIRS = {
    tuple(sorted(("O", "0"))),
    tuple(sorted(("I", "1"))),
    tuple(sorted(("J", "3"))),
    tuple(sorted(("A", "4"))),
    tuple(sorted(("G", "6"))),
    tuple(sorted(("S", "5"))),
    tuple(
        sorted(("B", "8"))
    ),  # As per user example 'S8' vs 'SB' implies '8' similar to 'B'
    tuple(sorted(("H", "M"))),  # As per user example 'HH' vs 'HM'
    # Add other common OCR confusions if necessary, e.g.:
    # tuple(sorted(('Z', '2'))), tuple(sorted(('Q', '0'))),
    # tuple(sorted(('L', '1'))), tuple(sorted(('U', 'V'))),
}
CONFUSABLE_SUBSTITUTION_COST = (
    0.3  # Cost for substituting confusable characters (0 < cost < 1)
)


def _calculate_custom_levenshtein_distance(s1: str, s2: str) -> float:
    """
    Calculates Levenshtein distance with custom costs for confusable characters.
    """
    s1_upper = s1.upper()
    s2_upper = s2.upper()

    if len(s1_upper) < len(s2_upper):
        # Ensure s1 is the longer string for the DP table setup
        return _calculate_custom_levenshtein_distance(s2_upper, s1_upper)

    if len(s2_upper) == 0:
        return float(len(s1_upper))

    previous_row = list(range(len(s2_upper) + 1))  # DP table row

    for i, char_s1 in enumerate(s1_upper):
        current_row = [float(i + 1)]
        for j, char_s2 in enumerate(s2_upper):
            # Calculate costs for insertion, deletion
            insertions = previous_row[j + 1] + 1.0
            deletions = current_row[j] + 1.0

            # Calculate cost for substitution
            substitution_cost = 1.0
            if char_s1 == char_s2:
                substitution_cost = 0.0
            elif tuple(sorted((char_s1, char_s2))) in CONFUSABLE_PAIRS:
                substitution_cost = CONFUSABLE_SUBSTITUTION_COST

            substitutions = previous_row[j] + substitution_cost
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return float(previous_row[-1])


def calculate_similarity_score(s1: str, s2: str) -> float:
    """
    Calculates a similarity score (0.0 to 1.0) between two strings
    based on the custom Levenshtein distance.
    1.0 means identical, 0.0 means completely different.
    """
    if not isinstance(s1, str) or not isinstance(s2, str):
        return 0.0  # Handle non-string inputs if necessary

    if not s1 and not s2:  # Both are empty
        return 1.0
    if not s1 or not s2:  # One is empty
        return 0.0

    distance = _calculate_custom_levenshtein_distance(s1, s2)
    max_len = float(max(len(s1), len(s2)))

    if max_len == 0:  # Should be caught by previous checks
        return 1.0

    similarity = 1.0 - (distance / max_len)
    return max(0.0, similarity)  # Ensure similarity is not negative


def is_string_similar_to_any_in_list(
    text_to_compare: str, string_list: list[str], confidence_percent: int
) -> bool:
    """
    Checks if text_to_compare is similar to any string in string_list
    above a given confidence threshold.

    Args:
        text_to_compare (str): The string to check.
        string_list (list[str]): A list of strings to compare against.
        confidence_percent (int): The similarity confidence threshold (0-100).

    Returns:
        bool: True if a sufficiently similar string is found, False otherwise.
    """
    if not string_list or not isinstance(text_to_compare, str):
        return False

    # Normalize confidence from 0-100 to 0.0-1.0
    normalized_confidence_threshold = confidence_percent / 100.0

    for candidate_string in string_list:
        if not isinstance(candidate_string, str):
            continue  # Skip non-string items in the list

        similarity = calculate_similarity_score(text_to_compare, candidate_string)
        print(
            f"similarity: {similarity}, candidate_string: {candidate_string}, text_to_compare: {text_to_compare}"
        )
        # For debugging, you can uncomment the line below:
        # print(f"Comparing '{text_to_compare}' with '{candidate_string}': Similarity = {similarity:.4f}, Threshold = {normalized_confidence_threshold:.2f}")

        if similarity >= normalized_confidence_threshold:
            return True

    return False


# Example Usage (can be removed or kept for testing):
# if __name__ == '__main__':
#     print("--- Testing String Similarity ---")
#     str1 = "1S8-3HH"
#     list_str = ["1SB3HM", "XYZ789", "1S83HH"]
#     confidence = 70
#
#     # Test 1: Should be True for "1SB3HM" (similarity ~0.77)
#     is_similar = is_string_similar_to_any_in_list(str1, list_str, confidence)
#     print(f"Is '{str1}' similar to any in {list_str} with {confidence}% confidence? {is_similar}") # Expected: True
#
#     # Test 2: Higher confidence, might be False for "1SB3HM"
#     is_similar_high_conf = is_string_similar_to_any_in_list(str1, list_str, 80)
#     print(f"Is '{str1}' similar to any in {list_str} with 80% confidence? {is_similar_high_conf}") # Expected: False for 1SB3HM, True for 1S83HH
#
#     # Test 3: Direct match with "1S83HH" (after removing hyphen, similarity will be high)
#     # Current custom Levenshtein for "1S8-3HH" vs "1S83HH":
#     # 1S8-3HH (len 7) vs 1S83HH (len 6) -> Deletion of '-' costs 1. Distance = 1.
#     # Sim = 1 - (1/7) = 0.857
#     is_similar_almost_match = is_string_similar_to_any_in_list("1S8-3HH", ["1S83HH"], 85)
#     print(f"Is '1S8-3HH' similar to '1S83HH' with 85% confidence? {is_similar_almost_match}") # Expected: True
#
#     str_a = "S8"
#     str_b = "SB"
#     sim_ab = calculate_similarity_score(str_a, str_b)
#     print(f"Similarity between '{str_a}' and '{str_b}': {sim_ab:.4f}") # Expected ~0.85
#
#     str_c = "HH"
#     str_d = "HM"
#     sim_cd = calculate_similarity_score(str_c, str_d)
#     print(f"Similarity between '{str_c}' and '{str_d}': {sim_cd:.4f}") # Expected ~0.70
#
#     str_e = "OPEN"
#     str_f = "0PEN"
#     sim_ef = calculate_similarity_score(str_e, str_f)
#     print(f"Similarity between '{str_e}' and '{str_f}': {sim_ef:.4f}") # Sim for O/0: 1 - (0.3/4) = 0.925
#
#     # Test with empty strings or list
#     print(f"Empty list test: {is_string_similar_to_any_in_list('TEST', [], 70)}") # False
#     print(f"Empty text to compare: {is_string_similar_to_any_in_list('', ['A','B'], 70)}") # False (score 0 vs non-empty)
#     print(f"Empty text vs empty text in list: {is_string_similar_to_any_in_list('', [''], 70)}") # True (score 1.0)
#     print(f"Score for empty vs empty: {calculate_similarity_score('', '')}") # 1.0
#     print(f"Score for A vs empty: {calcuglate_similarity_score('A', '')}") # 0.0
# --- End of Custom String Similarity Functions ---
