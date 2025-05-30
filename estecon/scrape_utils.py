import httpx
from lxml.html import HtmlElement, fromstring
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

def clean_string(text: str):
    """
    Cleans duplicated white spaces and new lines"""
    return " ".join(text.strip().split())

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
    
