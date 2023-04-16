from typing import List
import requests
from bs4 import BeautifulSoup
from pprint import pprint

def get_arxiv_id(html: BeautifulSoup) -> str:
    author_div = html.select('span.arxivid')[0]

    arxiv_id = author_div.findChildren("a" , recursive=False)[0].text.replace('arXiv:', '', 1).strip()

    return arxiv_id


def get_title(html: BeautifulSoup) -> str:
    title = html.select('h1.title.mathjax')[0].text.replace('Title:', '', 1).strip()
    return title


def get_authors(html: BeautifulSoup) -> List[str]:
    authors = []
    author_div = html.select('div.authors')[0]

    children = author_div.findChildren("a" , recursive=False)
    for child in children:
        authors.append(child.text.strip())

    return authors

def get_abstract(html: BeautifulSoup) -> str:
    abstract = html.select('blockquote.abstract.mathjax')[0].text.replace('Abstract:', '', 1).replace('\n', '').strip()
    return abstract


def get_date(html: BeautifulSoup) -> str:
    date = html.select('div.submission-history')[0].text.split('[v1]')[1].split('(')[0].strip()
    return date


def get_info(html):
    data = {
        'id': get_arxiv_id(html),
        'title': get_title(html),
        'authors': get_authors(html),
        'abstract': get_abstract(html),
        'date': get_date(html),
    }

    return data


if __name__ == '__main__':

    url = 'https://arxiv.org/abs/1810.04805'
    data = requests.get(url)

    html = BeautifulSoup(data.text, 'html.parser')

    print(get_info(html))




