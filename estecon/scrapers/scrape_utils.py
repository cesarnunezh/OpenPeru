import httpx
from lxml.html import HtmlElement, fromstring
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import os 
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
    
