from typing import List, Dict, Tuple, Set

import os
import shutil
import requests
import re
from pathlib import Path
from pprint import pprint
from datetime import datetime
from termcolor import cprint
from heapq import heappush, heappop
import pickle

import pymongo.results
from pymongo import MongoClient, InsertOne
from pymongo.errors import BulkWriteError

from bs4 import BeautifulSoup

import tarfile
from tex2py import tex2py
from ratelimiter import RateLimiter
import bibtexparser


def save_checkpoint(queue_filename, visited_filename, author_queue, visited_authors):
    with open(queue_filename, 'wb') as queue_file:
        pickle.dump(author_queue, queue_file)

    with open(visited_filename, 'wb') as visited_file:
        pickle.dump(visited_authors, visited_file)


def load_checkpoint(queue_filename, visited_filename):
    try:
        with open(queue_filename, 'rb') as queue_file:
            author_queue = pickle.load(queue_file)
    except FileNotFoundError:
        author_queue = []

    try:
        with open(visited_filename, 'rb') as visited_file:
            visited_authors = pickle.load(visited_file)
    except FileNotFoundError:
        visited_authors = set()

    return author_queue, visited_authors


def get_all_papers_info(author_page: str, max_papers: int) -> List[Dict]:
    """
    Retrieves all paper metadata about a paper including the id, title, abstract, authors and date.

    :param author_page: An Arxiv url of an author's page e.g. https://arxiv.org/search/stat?searchtype=author&query=Mikołaj%20Kasprzak&abstracts=show
    :return papers: An list of Arxiv paper objects from the given author url 
    """

    start_paper = 0

    paper_ids = []
    paper_titles = []
    paper_authors = []
    paper_dates = []
    paper_abstracts = []

    papers = []

    while True:
        with rate_limiter:
            
            data = requests.get(author_page + f'&size=200&start={start_paper}')
            if data.status_code != 200:
                print(f"Status code for {author_page + f'&size=200&start={start_paper}'}: {data.status_code}")

            html = BeautifulSoup(data.text, 'html.parser')

            paper_ids_on_page = [p.text.split('\n')[0][6:] for p in html.select('p.list-title')]

            # empty page
            if len(paper_ids_on_page) == 0:
                break

            paper_title_on_page = [p.text.strip() for p in html.select('p.title.mathjax')]

            paper_authors_on_page = list([[a.contents[0].strip() for a in p.findChildren('a', recursive=False)] for p in html.select('p.authors')])

            # Get dates:
            paper_dates_on_page = html.select('.is-size-7')
            date_re = r'Submitted (?:0[1-9]|[12][0-9]|3[01])\s(?:January|February|March|April|May|June|July|August|September|October|November|December),\s(?:[12]\d{3})'
            paper_dates_on_page = [s for s in paper_dates_on_page if re.match(date_re, s.text)]
            paper_dates_on_page = [p.text[10:].split(';')[0] for p in paper_dates_on_page]
            paper_dates_on_page = [datetime.strptime(p, "%d %B, %Y") for p in paper_dates_on_page]

            paper_abstracts_on_page = [p.text.strip() for p in html.select('span.abstract-full.mathjax')]

            paper_ids += paper_ids_on_page
            paper_titles += paper_title_on_page
            paper_authors += paper_authors_on_page
            paper_dates += paper_dates_on_page
            paper_abstracts += paper_abstracts_on_page

            start_paper += 200
            
            # get all papers from the first page (<= 200) only
            break


    
    for paper_id, paper_title, paper_author, paper_abstract, paper_date in zip(paper_ids, paper_titles, paper_authors, paper_abstracts, paper_dates):

        papers.append({
            'id':  paper_id,
            'title': paper_title,
            'author': paper_author,
            'date': paper_date,
            'abstract': paper_abstract

        })
    
    return papers[:max_papers]


def download_source(paper_id: str):
    """
    Saves the source files of the arxiv paper with the given id.

    :param paper_id: An Arxiv paper idea. e.g. 1009.3896
    """

    # Download source
    source_url = f'https://arxiv.org/e-print/{paper_id}'

    with rate_limiter:
        r = requests.get(source_url)
        if r.status_code != 200:
            print(f"Status code for {source_url}: {r.status_code}")

    file_name = f'data/{paper_id}.tar.gz'
    f = open(file_name, 'wb')
    f.write(r.content)
    f.close()

    try:
        # Extract file
        tar = tarfile.open(file_name, "r:gz")
        tar.extractall(f'data/{paper_id}')
        tar.close()
    except:
        cprint(f'Tarfile: {paper_id} source cannot be downloaded/extracted', 'red')
    
    # Remove compressed file
    os.remove(file_name)


def get_citations(paper_id: str) -> List[Dict[str, str]]:
    """
    Extracts the references from a paper's .bib files an arxiv paper id.

    Note: We assume that paper data are located in the 'data/{paper_id}' directory.
    """

    if not os.path.exists(f'data/{paper_id}'):
        return {}

    bib_file_names = [name for name in os.listdir(f'data/{paper_id}') if name[-4:] == '.bib']

    bib_entries = []
    for bib_file in bib_file_names:
        file_path = f'data/{paper_id}/{bib_file}'
        with open(file_path) as f:
            try:
                bib_entries += bibtexparser.load(f).entries
            except:
                cprint(f'Parsing: Bib file {bib_file} contained in {paper_id} cannot be parsed', 'red')
                continue

    tex_file_names = [name for name in os.listdir(f'data/{paper_id}') if name[-4:] == '.tex']
    citations = []
    for file_name in tex_file_names:
        file_path = f'data/{paper_id}/{file_name}'
        with open(file_path) as f:
            try:
                tex = f.read()
                re_cite = re.compile(r'\\cite.*\{(.*)\}')
                citations += re.findall(re_cite, tex)
            except:
                print(f'Read File: {file_name} contained in {paper_id} cannot be read', 'red')

    real_citations = []
    for (bib_item, entry) in zip({c['ID'] for c in bib_entries}, bib_entries):
        for citation in citations:
            if bib_item in citation:
                real_citations.append(entry)
                break

    return real_citations


def get_sections_from_paper(paper_id: str) -> Dict[str, str]:
    """
    Given a paper_id return a dict of section name to section content.

    Note:
        1. The paper source must already be downloaded.
        2. Section names are assumed to be unique. If they aren't unique only one will be kept.

    :param paper_id: An Arxiv paper idea. e.g. 1009.3896
    :return: a dict from name to content.
    """

    if not os.path.exists(f'data/{paper_id}'):
        return {}

    tex_file_names = [name for name in os.listdir(f'data/{paper_id}') if name[-4:] == '.tex']

    sections = dict()
    for file_name in tex_file_names:
        file_path = f'data/{paper_id}/{file_name}'
        with open(file_path) as f:
            try:
                tex = f.readlines()
            except:
                cprint(f'Read File: {file_name} contained in {paper_id} cannot be read', 'red')
                continue
            
            try:
                toc = tex2py(tex)
            except:
                cprint(f'Parsing: {file_name} contained in {paper_id} cannot be used by tex2py', 'red')
                continue

            if not list(toc.source.text):
                cprint(f'Parsing: the tex file {file_name} failed to parse', 'red')
                continue

            source = toc.source
            if source.find('section') == None:
                cprint(f'Parsing: the tex file {file_name} contains no sections', 'yellow')
                continue

            for section in toc.sections:
                # If a paper has several sections with the same name then this can cause problems.
                as_strs = [str(token) for token in section.descendants]
                sections[section.name] = ''.join(as_strs)

    return sections


def get_paper_obj(paper: Dict) -> Dict:
    """
    Get the paper object (add sections and citations) of the given arxiv paper, to be inserted into the database.

    :param paper: An Arxiv paper obj consisting of id, title, authors, abstract, date
    :return: A paper object consisting of id, title, authors, abstract, date, sections, citations
    """

    paper_id = paper['id']

    download_source(paper_id)
    # sections = get_sections_from_paper(paper_id)
    # paper['sections'] = sections
    citations = get_citations(paper_id)
    paper['citations'] = citations

    paper_path = f'data/{paper_id}'

    try:
        shutil.rmtree(paper_path)
    except OSError as e:
        print(f'Deletion Error: {paper_path} : {e.strerror}')
        
    return paper


def put_papers_in_database(papers: List[Dict], papers_collection: pymongo.collection.Collection) -> None:
    """
    Adds to the collection papers the paper info of all arxiv papers in the given list using a bulk write operation.

    :param papers: A list of Arxiv paper objects consisting of id, title, authors, abstract, date, sections
    :param papers_collection: collection in the database where all papers must be stored
    """

    to_insert = []
    for i, paper in enumerate(papers):
        paper_id = paper['id']
        db_paper = papers_collection.find_one({'id': paper_id})

        if not db_paper:
            paper_obj = get_paper_obj(paper)
            to_insert.append(InsertOne(paper_obj))
            # paper = papers_collection.find_one({'id': paper_id})
            # assert(papers_collection.count_documents({'id': paper_id}) == 1)

            cprint(f"{i}: {paper_obj['title']}", 'green')

    try:
        if to_insert:
            papers_collection.bulk_write(to_insert, ordered=False)
    except BulkWriteError as bwe:
        cprint(f'Database: Bulk Write Error.', 'red')


def get_num_papers_of_collaborator(collaborators: List[str], author_queue: List[str], visited_authors: Set[str]) -> Dict[str, int]:
    """
    Returns the number of papers of each author in the given list

    :param collaborators: A list of author names
    :return author_reputation: A dictionary of 'author name' -> number of papers
    """

    collaborator_reputation = {}
    author_base_url = 'https://arxiv.org/search/stat?searchtype=author&query='

    for collaborator in collaborators:
        if collaborator in visited_authors or collaborator in author_queue:
            continue

        with rate_limiter:
            author_url = author_base_url + '%20'.join(collaborator.split(' '))  # replace spaces with %20 for url
            data = requests.get(author_url)
            if data.status_code != 200:
                print(f"Status code for {author_url}: {data.status_code}")

            html = BeautifulSoup(data.text, 'html.parser')

            try:
                # e.g. Showing 1–8 of 8 results for collaborator: Wynne, G
                paper_count = html.select_one('h1.is-clearfix').contents[0].strip().split(' ')[3]

                if paper_count is not None:
                    collaborator_reputation[collaborator] = int(paper_count)
            except:
                cprint(f"Parsing: Could not retrieve collaborator {collaborator}'s paper count", 'red')
                continue

    return collaborator_reputation


def scrape(author_queue: List[str], visited_authors: Set[str], max_papers_per_author: int) -> None:
    """
    Core scraping function
        1. Gets all papers and corresponding collaborators from the given author_url
        2. Scrapes and stores all papers in the database
        3. Appends collaborators in the author_queue based on reputation (number of publications)

    :param author_queue: Priority queue with entries of the form (reputation, (author_name, author_url))
    :param visited_authors: Set of author names that have already been scraped
    """

    while len(author_queue) > 0:
        author_name = author_queue.pop(0)
        if author_name not in visited_authors:
            break

    # replace spaces with %20 for url
    author_url = 'https://arxiv.org/search/stat?searchtype=author&abstracts=show&query=' + '%20'.join(author_name.split(' '))

    cprint(f'\nscraping papers of {author_name}', 'blue')

    try:
        papers = get_all_papers_info(author_url, max_papers_per_author)
    except:
        cprint(f'Scraping Error: {author_url} cannot be scraped', 'red')
        return

    put_papers_in_database(papers, papers_collection)

    collaborators = set([author_name for paper in papers for author_name in paper['author']])

    for collaborator_name in collaborators:
        if collaborator_name not in visited_authors and collaborator_name not in author_queue:
            author_queue.append(collaborator_name)

    visited_authors.add(author_name)

    save_checkpoint(queue_filename, visited_filename, author_queue, visited_authors)



if __name__ == '__main__':
    MAX_AUTHORS_TO_SCRAPE = 10
    MAX_PAPERS_PER_AUTHOR = 100

    data_path = 'data'

    try:
        shutil.rmtree(data_path)
    except OSError as e:
        print(f'Deletion Error: {data_path} : {e.strerror}')

    Path(data_path).mkdir(parents=True, exist_ok=True)

    rate_limiter = RateLimiter(max_calls=1, period=15)
    client = MongoClient()
    db = client['litdb']

    # remove later
    # db.drop_collection('papers')

    papers_collection = db['papers']

    # print(papers_collection.find_one({'id': '2302.12419'}))

    papers_collection.create_index('id', unique=True, background=True)

    queue_filename = 'author_queue.pickle'
    visited_filename = 'visited_authors.pickle'
    # os.remove(queue_filename)
    # os.remove(visited_filename)

    author_queue, visited_authors = load_checkpoint(queue_filename, visited_filename)

    if not len(author_queue):
        # seed_author_name = 'Michael I. Jordan'
        seed_author_name = 'Mikołaj Kasprzak'
        # seed_author_name = 'David Yarowsky'

        author_queue.append(seed_author_name)
        visited_authors.add(seed_author_name)
        save_checkpoint(queue_filename, visited_filename, author_queue, visited_authors)

    i = 0
    while len(author_queue) and MAX_AUTHORS_TO_SCRAPE > 0:
        
        if i % 1 == 0:
            collection_size = db.command('collstats', 'papers')['size']
            cprint(f'Database size is {collection_size / (10 ** 6)}Mb', 'yellow')

        scrape(author_queue, visited_authors, MAX_PAPERS_PER_AUTHOR)
        MAX_AUTHORS_TO_SCRAPE -= 1
        i += 1