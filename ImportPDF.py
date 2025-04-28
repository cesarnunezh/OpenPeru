import fitz  # PyMuPDF
import pytesseract
import cv2
import numpy as np
from PIL import Image

# (Opcional) Define ruta a Tesseract si no está en el PATH
pytesseract.pytesseract.tesseract_cmd = r"C:/Program Files/Tesseract-OCR/tesseract.exe"

pdf_path = "C:/Users/josep/Desktop/UChicago-Archives/Vestecon/Asis_y_vot_de_la_sesión_del_13-12-2024.pdf"

doc = fitz.open(pdf_path)

# for everypage
for i, page in enumerate(doc):
    # Renderiza la página como imagen (aumentando resolución)
    pix = page.get_pixmap(dpi=300)
    img_data = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    
    # Convierte a escala de grises
    gray = cv2.cvtColor(img_data, cv2.COLOR_RGB2GRAY)

    # (Opcional) Umbralizar para mejorar OCR
    _, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)

    # Convierte imagen para OCR
    pil_img = Image.fromarray(thresh)

    # Ejecuta OCR con layout de columnas
    text = pytesseract.image_to_string(pil_img, lang="spa", config="--psm 6")  # psm 6: Assume a uniform block of text

    print(f"\n--- Página {i+1} ---\n")
    print(text)
