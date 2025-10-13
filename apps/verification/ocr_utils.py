import re
import os
import logging
import tempfile
from typing import Dict, Optional

logger = logging.getLogger(__name__)

try:
    import pytesseract
    from PIL import Image
    import cv2
    import numpy as np
    OCR_AVAILABLE = True
except ImportError as e:
    logger.warning(f"OCR libraries not available: {str(e)}")
    OCR_AVAILABLE = False
    np = None
    cv2 = None
    pytesseract = None
    Image = None


def is_ocr_available() -> bool:
    """Check if OCR libraries are installed and available"""
    if not OCR_AVAILABLE:
        return False
    
    _configure_tesseract_path()
    
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _configure_tesseract_path():
    """Configure Tesseract path for Windows"""
    if OCR_AVAILABLE and pytesseract is not None:
        try:
            pytesseract.get_tesseract_version()
        except Exception:
            import platform
            if platform.system() == 'Windows':
                possible_paths = [
                    r'C:\Users\Sahina1001\AppData\Local\Programs\Tesseract-OCR\tesseract.exe',
                    r'C:\Program Files\Tesseract-OCR\tesseract.exe',
                    r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe'
                ]
                
                for path in possible_paths:
                    if os.path.exists(path):
                        pytesseract.pytesseract.tesseract_cmd = path
                        logger.info(f"Configured Tesseract path: {path}")
                        break


def extract_pan_from_image(file_path: str) -> Dict[str, any]:
    if not OCR_AVAILABLE:
        return {
            "success": False,
            "pan_number": None,
            "message": "OCR libraries not installed. Please install pytesseract and opencv-python.",
            "confidence": None
        }

    _configure_tesseract_path()

    try:
        file_path = get_file_from_storage(file_path)

        if not os.path.exists(file_path):
            return {
                "success": False,
                "pan_number": None,
                "message": f"File not found: {file_path}",
                "confidence": None
            }

        logger.info(f"Starting OCR extraction for file: {file_path}")
        image = cv2.imread(file_path)

        if image is None:
            return {
                "success": False,
                "pan_number": None,
                "message": "Unable to read image file. File may be corrupted or in unsupported format.",
                "confidence": None
            }

        processed_image = preprocess_image(image)
        custom_config = r"--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        text = pytesseract.image_to_string(processed_image, config=custom_config)

        logger.info(f"OCR extracted text: {text[:200]}")
        pan_number = extract_pan_pattern(text)

        if pan_number:
            return {
                "success": True,
                "pan_number": pan_number,
                "message": f"PAN number successfully extracted: {pan_number}",
                "confidence": 0.85
            }
        else:
            alt_processed = preprocess_image_alternative(image)
            text_alt = pytesseract.image_to_string(alt_processed, config=custom_config)
            pan_number = extract_pan_pattern(text_alt)

            if pan_number:
                return {
                    "success": True,
                    "pan_number": pan_number,
                    "message": f"PAN number successfully extracted: {pan_number}",
                    "confidence": 0.75
                }
            else:
                return {
                    "success": False,
                    "pan_number": None,
                    "message": "Unable to extract PAN number from document. Please ensure the image is clear and properly oriented.",
                    "confidence": None
                }

    except Exception as e:
        logger.error(f"Error during OCR extraction: {str(e)}", exc_info=True)
        return {
            "success": False,
            "pan_number": None,
            "message": f"Error processing image: {str(e)}",
            "confidence": None
        }



def preprocess_image(image):
    if not OCR_AVAILABLE or cv2 is None:
        raise ImportError("OpenCV not available")
    
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
    
    thresh = cv2.adaptiveThreshold(
        denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )
    
    height, width = thresh.shape
    if width < 1000:
        scale_factor = 1000 / width
        new_width = int(width * scale_factor)
        new_height = int(height * scale_factor)
        thresh = cv2.resize(thresh, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
    
    return thresh


def preprocess_image_alternative(image):
    if not OCR_AVAILABLE or cv2 is None or np is None:
        raise ImportError("OpenCV or NumPy not available")
    
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    filtered = cv2.bilateralFilter(gray, 9, 75, 75)
    
    _, thresh = cv2.threshold(filtered, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    kernel = np.ones((2, 2), np.uint8)
    opening = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)
    
    return opening


def extract_pan_pattern(text: str) -> Optional[str]:
    text = text.upper().replace(' ', '').replace('\n', '').replace('\t', '')
    
    pan_pattern = r'[A-Z]{5}[0-9]{4}[A-Z]{1}'
    
    matches = re.findall(pan_pattern, text)
    
    if matches:
        pan = matches[0]
        if validate_pan_structure(pan):
            return pan
        else:
            logger.warning(f"PAN structure validation failed for: {pan}")
            return pan
    
    return None


def validate_pan_structure(pan: str) -> bool:
    if len(pan) != 10:
        return False
    
    if not re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$', pan):
        return False
    
    valid_types = ['P', 'C', 'H', 'F', 'A', 'T', 'B', 'L', 'J', 'G']
    if pan[3] not in valid_types:
        logger.warning(f"4th character '{pan[3]}' not in standard PAN types")
    
    return True


def get_file_from_storage(file_path: str) -> str:
    from django.conf import settings

  
    if "amazonaws.com" in file_path or getattr(settings, "DEFAULT_FILE_STORAGE", "").endswith("S3Boto3Storage"):
        try:
            import boto3

            if "https://" in file_path:
                parts = file_path.replace("https://", "").split("/")
                bucket = parts[0].split(".")[0]
                key = "/".join(parts[1:])
            else:
                bucket = settings.AWS_STORAGE_BUCKET_NAME
                key = file_path.lstrip("/")

            s3 = boto3.client(
                "s3",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_S3_REGION_NAME
            )

            file_ext = os.path.splitext(key)[1]
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=file_ext)
            s3.download_file(bucket, key, temp_file.name)

            logger.info(f"Downloaded S3 file to: {temp_file.name}")
            return temp_file.name

        except Exception as e:
            logger.error(f"Error downloading from S3: {str(e)}")
            raise

    possible_paths = []
    
    if file_path.startswith('/'):
        relative_path = file_path.lstrip('/')
    else:
        relative_path = file_path
    
    possible_paths.append(os.path.join(settings.MEDIA_ROOT, relative_path))
    
    if '/uploads/documents/' in file_path:
        filename = os.path.basename(file_path)
        import_path = os.path.join(settings.MEDIA_ROOT, 'import')
        if os.path.exists(import_path):
            for root, dirs, files in os.walk(import_path):
                if filename in files:
                    possible_paths.append(os.path.join(root, filename))
    
    if os.path.isabs(file_path):
        possible_paths.append(file_path)
    
    for full_path in possible_paths:
        full_path = os.path.normpath(full_path)
        logger.info(f"Looking for file at: {full_path}")
        
        if os.path.exists(full_path):
            logger.info(f"Found file at: {full_path}")
            return full_path
    
    attempted_paths = [os.path.normpath(p) for p in possible_paths]
    raise FileNotFoundError(f"File not found. Attempted paths: {attempted_paths}")

def cleanup_temp_file(file_path: str):
    try:
        if file_path and os.path.exists(file_path) and '/tmp' in file_path:
            os.remove(file_path)
            logger.info(f"Cleaned up temporary file: {file_path}")
    except Exception as e:
        logger.warning(f"Failed to clean up temp file {file_path}: {str(e)}")

