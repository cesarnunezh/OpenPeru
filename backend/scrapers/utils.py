import httpx
import asyncio
from lxml.html import HtmlElement, fromstring
from loguru import logger
from pathlib import Path
import re
import pytesseract
import fitz
from io import BytesIO
from PIL import Image
import numpy as np
import cv2
import os
import shutil


def _configure_tesseract() -> None:
    """
    Configure pytesseract in an environment-agnostic way.

    Priority:
    1. TESSERACT_CMD env var (if set)
    2. `tesseract` found in PATH
    3. Raise a clear error if not found
    """
    cmd_from_env = os.getenv("TESSERACT_CMD")
    if cmd_from_env:
        pytesseract.pytesseract.tesseract_cmd = cmd_from_env
        return

    cmd_from_path = shutil.which("tesseract")
    if cmd_from_path:
        pytesseract.pytesseract.tesseract_cmd = cmd_from_path
        return

    raise RuntimeError(
        "Tesseract binary not found. Install it and either make it available on PATH "
        "or set the TESSERACT_CMD environment variable to its full path."
    )


# Run once on import
_configure_tesseract()

DEFAULT_TIMEOUT = httpx.Timeout(connect=10.0, read=60.0, write=30.0, pool=10.0)

BROWSER_LIKE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}


def normalize_text(txt: str | None) -> str:
    if not txt:
        return ""
    # collapse whitespace and lowercase
    return re.sub(r"\s+", " ", txt).strip().lower()


def clean_string(text: str):
    """
    Cleans duplicated white spaces and new lines"""
    return " ".join(text.strip().split())


def extract_text_from_page(page):
    """
    Extract text from a single PDF page using Tesseract OCR.
    Args:
        page: A PyMuPDF page object.
    """
    pix = page.get_pixmap(dpi=300)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
        pix.height, pix.width, pix.n
    )
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)
    pil_img = Image.fromarray(thresh)
    text = pytesseract.image_to_string(pil_img, lang="spa", config="--psm 6")
    return text


def render_pdf(pdf_url: str) -> str:
    """
    Extract text from a PDF file using PyMuPDF and Tesseract OCR.
    """
    response = get_url(pdf_url)
    response.raise_for_status()  # Ensure we raise an error for bad responses
    pdf_file = BytesIO(response.content)
    pdf_text = ""
    with fitz.open(stream=pdf_file, filetype="pdf") as pdf:
        for page in pdf:
            pdf_text += " " + extract_text_from_page(page)
    return pdf_text


def url_to_cache_file(url: str, cache_dir: Path) -> Path:
    """
    Convert URL to a cache file
    """
    # Remove https:// and replace certain characters with underscores
    cache_key = re.sub(r"^https?://", "", url)
    cache_key = re.sub(r"[^\w.-]", "_", cache_key)
    return cache_dir / f"{cache_key}.txt"


def save_ocr_txt_to_cache(text: str, cache_path: Path):
    """
    Save txt file to OCR cache
    """
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(text, encoding="utf-8")


def xpath2(xpath_query, parse):
    result = parse.xpath(xpath_query)
    return result[0].text if result else None


def get_url(
    url: str,
    data: str | None = None,
    timeout: httpx.Timeout = DEFAULT_TIMEOUT,
    verify: bool = True,
) -> httpx.Response:
    method = "POST" if data is not None else "GET"
    try:
        with httpx.Client(
            headers=BROWSER_LIKE_HEADERS,
            timeout=timeout,
            follow_redirects=True,
            verify=verify,
            http2=True,
        ) as client:
            if method == "POST":
                response = client.post(url, data=data)
            else:
                response = client.get(url)

        if response.is_success:
            return response

        if response.status_code == 403:
            logger.warning(
                f"403 Forbidden fetching {url}.: Likely WAF/permissions issue. Check headers, cookies, IP, and rate limits."
            )
        else:
            logger.warning(f"Non-200 response fetching {url}: {response.status_code}")
        return None

    except (httpx.RequestError, httpx.TimeoutException) as e:
        logger.warning(f"Request error for {url}: {e}")
        return None


def get_cong_website(profile_content: str) -> str | None:
    parse = fromstring(profile_content)
    website = parse.xpath('//*[@class="web"]/span[2]/a/@href')
    return website[0] if website else None


def get_url_text(url: str, data: str | None = None) -> str | None:
    try:
        response = get_url(url, data)
        return response.text
    except (AttributeError, TypeError) as e:
        logger.warning(f"Request error: {e}")
        return None


def parse_url(url: str, *args) -> HtmlElement | None:
    """
    Returns the html of the url parse ready to use
    """
    if args:
        return fromstring(get_url_text(url, args[0]))
    else:
        return fromstring(get_url_text(url))


async def get_url_text_async(client: httpx.AsyncClient, url: str, data: dict = None):
    """
    Async GET or POST using a shared client
    """
    try:
        if data:
            response = await client.post(url, data=data)
        else:
            response = await client.get(url)

        if response.status_code == 200:
            return response.text
    except httpx.HTTPError as e:
        logger.info(f"Error fetching {url}: {e}")
        return None


async def fetch_multiple_urls_async(
    urls: list[str | tuple[str, dict]],
) -> list[HtmlElement]:
    """
    Fetch multiple URLs concurrently.
    urls: list of either string (GET) or (url, data_dict) tuples (POST)
    Returns list of HtmlElement objects
    """
    async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
        tasks = []

        for item in urls:
            if isinstance(item, tuple):  # POST request
                url, data = item
                tasks.append(get_url_text_async(client, url, data))
            else:  # GET request
                tasks.append(get_url_text_async(client, item))

        html_responses = await asyncio.gather(*tasks)
        return [fromstring(html) for html in html_responses if html]
