from typing import List, Dict

import pymongo.results
import requests
from bs4 import BeautifulSoup
from pprint import pprint
from pymongo import MongoClient
from datetime import datetime
from os import remove
import tarfile
from tex2py import tex2py
from termcolor import cprint
from os import listdir

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
        authors.append({'name': child.text.strip(), 'author_page': child.attrs['href']})

    return authors

def get_abstract(html: BeautifulSoup) -> str:
    abstract = html.select('blockquote.abstract.mathjax')[0].text.replace('Abstract:', '', 1).replace('\n', '').strip()
    return abstract


def get_date(html: BeautifulSoup) -> datetime:
    timestamp = html.select('div.submission-history')[0].text.split('[v1]')[1].split('(')[0].strip()
    return datetime.strptime(timestamp, '%a, %d %b %Y %H:%M:%S %Z')


def get_info(html):
    data = {
        'id': get_arxiv_id(html),
        'title': get_title(html),
        'authors': get_authors(html),
        'abstract': get_abstract(html),
        'date': get_date(html),
    }

    return data


def put_paper_in_database(paper_id: str) -> pymongo.results.InsertOneResult:
    """
    Adds to the collection papers the paper info of the arxiv paper with id paper_id.

    :param paper_id: An Arxiv paper idea. e.g. 1009.3896
    :return: A MongoDB InsertOneResult object.
    """

    url = f'https://arxiv.org/abs/{paper_id}'
    data = requests.get(url)
    html = BeautifulSoup(data.text, 'html.parser')
    paper = get_info(html)

    download_source(paper_id)
    sections = get_sections_from_paper(paper_id)
    paper['sections'] = sections

    insert_result = db['papers'].insert_one(paper)
    return insert_result

def download_source(paper_id: str):
    """
    Saves the source files of the arxiv paper with the given id.

    :param paper_id: An Arxiv paper idea. e.g. 1009.3896
    """

    # Download source
    source_url = f'https://arxiv.org/e-print/{paper_id}'
    r = requests.get(source_url)
    file_name = f'data/{paper_id}.tar.gz'
    f = open(file_name, 'wb')
    f.write(r.content)
    f.close()

    # Extract file
    tar = tarfile.open(file_name, "r:gz")
    tar.extractall(f'data/{paper_id}')
    tar.close()

    # Remove compressed file
    remove(file_name)


def get_sections_from_paper(paper_id: str) -> Dict[str, str]:
    """
    Given a paper_id return a dict of section name to section content.

    Note:
        1. The paper source must already be downloaded.
        2. Section names are assumed to be unique. If they aren't unique only one will be kept.

    :param paper_id: An Arxiv paper idea. e.g. 1009.3896
    :return: a dict from name to content.
    """

    tex_file_names = [name for name in listdir(f'data/{paper_id}') if name[-4:] == '.tex']

    sections = dict()
    for file_name in tex_file_names:
        file_path = f'data/{paper_id}/{file_name}'
        with open(file_path) as f:
            tex = f.readlines()
            toc = tex2py(tex)

            if not list(toc.source.text):
                cprint(f'the tex file {file_name} failed to parse\n', 'red')
                continue

            source = toc.source
            if source.find('section') == None:
                cprint(f'the tex file {file_name} contains no sections', 'yellow')
                continue

            for section in toc.sections:
                # If a paper has several sections with the same name then this can cause problems.
                as_strs = [str(token) for token in section.descendants]
                sections[section.name] = ''.join(as_strs)
            print()

    return sections

if __name__ == '__main__':
    paper_id = '1009.3896'

    client = MongoClient()
    db = client['litdb']
    paper = db['papers'].find_one({'id': paper_id})

    if not paper:
        put_paper_in_database(paper_id)
        paper = db['papers'].find_one({'id': paper_id})
        assert(db['papers'].count_documents({'id': paper_id}) == 1)

    print(paper)





