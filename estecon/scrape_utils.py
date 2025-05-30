import httpx
import lxml.html
from lxml.html import HtmlElement

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

def parse_url(url:str, *args) -> lxml.html.HtmlElement:
    """
    Returns the html of the url parse ready to use
    """
    if args:
        return lxml.html.fromstring(get_url_text(url, args[0]))
    else:
        return lxml.html.fromstring(get_url_text(url))