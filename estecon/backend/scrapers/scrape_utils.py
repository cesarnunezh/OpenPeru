import httpx
import asyncio
from typing import List, Union, Tuple
from lxml.html import HtmlElement, fromstring
from loguru import logger
from pathlib import Path
import re

def clean_string(text: str):
    """
    Cleans duplicated white spaces and new lines"""
    return " ".join(text.strip().split())

def url_to_cache_file(url: str, cache_dir: Path) -> Path:
    '''
    Convert URL to a cache file 
    '''
    # Remove https:// and replace certain characters with underscores
    cache_key = re.sub(r"^https?://", "", url)
    cache_key = re.sub(r"[^\w.-]", "_", cache_key)
    return cache_dir / f"{cache_key}.txt"

def save_ocr_txt_to_cache(text: str, cache_path: Path):
    '''
    Save txt file to OCR cache
    '''
    cache_path.parent.mkdir(parents=True, exist_ok=True) 
    cache_path.write_text(text, encoding="utf-8")
    
def xpath2(xpath_query, parse):
    result = parse.xpath(xpath_query)
    return result[0].text if result else None

def get_url_text(url:str, *args):
    if args:
        with httpx.Client(verify=False) as client:
            response = client.post(url, data = args[0])
            if response.status_code == 200:
                return response.text
    else:
        response = httpx.get(url,verify=False)
        if response.status_code == 200:
                return response.text

def parse_url(url:str, *args) -> HtmlElement:
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


async def fetch_multiple_urls_async(urls: List[Union[str, Tuple[str, dict]]]) -> List[HtmlElement]:
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