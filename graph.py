from typing import List, Dict, Tuple, Set

from pprint import pprint
from datetime import datetime
from termcolor import cprint
from collections import Counter, defaultdict

import pymongo.results
from pymongo import MongoClient, InsertOne
from pymongo.errors import BulkWriteError

import pyvis
from pyvis.network import Network


# TODO
def get_all_papers_and_citations(collection: pymongo.collection.Collection) -> Tuple[Set[str], Dict[str, Counter]]:
    
    papers_set = set()
    citation_map = defaultdict(lambda: Counter())

    for paper in collection.find():
        paper_papers = paper['paper']
        papers_set.update(paper_papers)

        for paper in paper_papers:
            citation_map[paper].update(paper_papers)
    
    return papers_set, citation_map


# TODO
def get_papers_and_citations_within_degree(degree: int, seed_paper_name: str, 
                                        papers_set: Set[str], citation_map: Dict[str, Counter]) -> Tuple[Set[str], Dict[str, Counter]]:

    papers = [seed_paper_name]
    visited_papers = set()
    visited_citation_map = {}

    while degree != 0:
        queue_len = len(papers)

        for _ in range(queue_len):
            paper = papers.pop(0)

            visited_papers.add(paper)
            visited_citation_map[paper] = citation_map[paper]

            for citation in citation_map[paper]:
                papers.append(citation)
        
        degree -= 1

    visited_papers.update(papers)  # outer layer papers

    return visited_papers, visited_citation_map


# TODO
def get_citation_graph(net: pyvis.network.Network, collection: pymongo.collection.Collection, 
                        degree: int, seed_paper_name: str) -> None:

    papers_set, citations_map = get_all_papers_and_citations(papers_collection)

    visited_papers, visited_citations_map  = get_papers_and_citations_within_degree(degree, seed_paper_name, papers_set, citations_map)

    net.add_nodes(visited_papers)

    edge_exists = set()

    for paper, citations in visited_citations_map.items():
        for citation, weight in citations.items():
            if citation != paper and (paper, citation) not in edge_exists:
                net.add_edge(paper, citation)
                edge_exists.update([(paper, citation), (citation, paper)])  # undirected edge



def get_all_authors_and_collaborators(collection: pymongo.collection.Collection) -> Tuple[Set[str], Dict[str, Counter]]:
    
    authors_set = set()
    collaborator_map = defaultdict(lambda: Counter())

    for paper in collection.find():
        paper_authors = paper['author']
        authors_set.update(paper_authors)

        for author in paper_authors:
            collaborator_map[author].update(paper_authors)  # includes self author (will be ignored when creating edges)
    
    return authors_set, collaborator_map


def get_authors_and_collaborators_within_degree(degree: int, seed_author_name: str, 
                                                authors_set: Set[str], collaborator_map: Dict[str, Counter]) -> Tuple[Set[str], Dict[str, Counter]]:

    authors = [seed_author_name]
    visited_authors = set()
    visited_collaborator_map = {}

    while degree != 0:
        queue_len = len(authors)

        for _ in range(queue_len):
            author = authors.pop(0)

            visited_authors.add(author)
            visited_collaborator_map[author] = collaborator_map[author]

            for collaborator in collaborator_map[author]:
                authors.append(collaborator)
        
        degree -= 1

    visited_authors.update(authors)  # outer layer authors

    return visited_authors, visited_collaborator_map


def get_collaborator_graph(net: pyvis.network.Network, collection: pymongo.collection.Collection, 
                        degree: int, seed_author_name: str) -> None:

    authors_set, collaborator_map = get_all_authors_and_collaborators(papers_collection)

    visited_authors, visited_collaborator_map = get_authors_and_collaborators_within_degree(degree, seed_author_name, authors_set, collaborator_map)

    net.add_nodes(visited_authors)

    edge_exists = set()

    for author, collabs in visited_collaborator_map.items():
        for collab, weight in collabs.items():
            if collab != author and (author, collab) not in edge_exists:
                net.add_edge(author, collab)
                edge_exists.update([(author, collab), (collab, author)])  # undirected edge




if __name__ == '__main__':

    client = MongoClient()
    db = client['litdb']
    papers_collection = db['papers']

    net = Network(height="750px", 
                width="100%", 
                bgcolor="#222222", 
                font_color="white",
                select_menu=True,
                filter_menu=True)

    degree = 2
    seed_author_name = 'Mikołaj Kasprzak'
    seed_paper_name = ''

    get_collaborator_graph(net, papers_collection, degree, seed_author_name)

    # get_citation_graph(net, papers_collection, degree, seed_paper_name)


    # net.show_buttons(filter_=['physics'])
    net.toggle_physics(True)
    net.repulsion(node_distance=500, spring_length=500)
    net.show('node.html', notebook=False)
