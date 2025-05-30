import pandas as pd
from pathlib import Path
from config import URL
from typing import NamedTuple
from scrape_utils import parse_url
import re
import time

class Congresista(NamedTuple):
    id: str
    nombre:str
    votos: int
    periodo: str
    partido: str
    bancada: str
    dist_electoral: str
    condicion: str
    website: str 

def get_dict_periodos(url: str) -> list:
    parse = parse_url(url)
    periodos = parse.xpath('//*[@name="idRegistroPadre"]/option')
    return {elem.text: elem.get('value') for elem in periodos}

def get_links_congres(url: str, params:dict) -> list:
    parse = parse_url(url, params)
    links = parse.xpath('//*[@class="congresistas"]//tr//td//*[@class="conginfo"]/@href')
    return [elem for elem in links]

def xpath2(xpath_query, parse):
    result = parse.xpath(xpath_query)
    return result[0].text if result else None

def get_cong_info(base_url: str, cong_link: str, periodo: str) -> Congresista:
    parse = parse_url(base_url + cong_link)
    search = re.search(r"(?<=id=)\d+", cong_link)
    if search:
        id = search.group()
    return Congresista(
        id = id,
        nombre = xpath2('//*[@class="nombres"]/span[2]',parse),
        votos = xpath2('//*[@class="votacion"]/span[2]',parse),
        periodo = periodo,
        partido = xpath2('//*[@class="grupo"]/span[2]',parse),
        bancada = xpath2('//*[@class="bancada"]/span[2]',parse),
        dist_electoral = xpath2('//*[@class="representa"]/span[2]',parse),
        condicion = xpath2('//*[@class="condicion"]/span[2]',parse),
        website = parse.xpath('//*[@class="web"]/span[2]/a/@href')[0]
        )

def get_cong_list(base_url: str) -> list[Congresista]:
    dict_periodos = get_dict_periodos(base_url)
    final_lst = []
    for periodo, valor in dict_periodos.items():
        if valor != '13':
            continue
        link_lst = get_links_congres(base_url, {'idRegistroPadre': valor})
        for link in link_lst:
            final_lst.append(get_cong_info(base_url, link, periodo))
    return final_lst

if __name__ == '__main__':
    path = Path('./data/congresistas.csv')
    if not path.exists():
        congresistas_df = pd.DataFrame(get_cong_list(URL['congresistas']))
        congresistas_df.to_csv(path)