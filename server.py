from flask import Flask, render_template, request

from pymongo import MongoClient
import generate
import scraping
import openai
import os

import pyvis
from pyvis.network import Network

from utils.graph import get_collaborator_graph

openai.api_key = os.environ['OPENAI_API_KEY']


app = Flask(__name__)


@app.route('/', methods=['GET', 'POST'])
def index():
    seed_author_name = request.form.get('seed-author-name', 'Author Name')
    degree = request.form.get('degree', 1)

    name = "+".join(seed_author_name.split(' '))
    url = f'https://arxiv.org/search/?query={name}&searchtype=all&source=header'
    information = scraping.scrape.get_all_papers_info(url, 200)
    summary = generate.generate_summary(information, model='gpt4')

    bio = generate.generate_author_bio(information, summary, author_name=seed_author_name, model='gpt4')

    return render_template('index.html', seed_author_name=seed_author_name, degree=degree, answer=bio)


@app.route('/graph', methods=['GET'])
def graph():
    seed_author_name = request.args.get('seed_author_name', 'Mikołaj Kasprzak')
    degree = int(request.args.get('degree', 2))

    client = MongoClient()
    db = client['litdb']
    papers_collection = db['papers']

    net = Network(height="720px",
                  width="100%",
                  bgcolor="#222222",
                  font_color="white",
                  select_menu=True,
                  filter_menu=True,
                  cdn_resources='in_line')

    get_collaborator_graph(net, papers_collection, degree, seed_author_name)

    # net.show_buttons(filter_=['physics'])
    net.toggle_physics(True)
    net.repulsion(node_distance=500, spring_length=500)
    net.write_html('templates/node.html', open_browser=False)

    return render_template('node.html')


if __name__ == "__main__":
    app.run(debug=True)
