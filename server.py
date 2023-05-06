from flask import Flask, render_template, request

from pymongo import MongoClient

import pyvis
from pyvis.network import Network

from utils.graph import get_collaborator_graph


app = Flask(__name__)


@app.route('/', methods=['GET', 'POST'])
def index():
    seed_author_name = request.form.get('seed-author-name', 'Author Name')
    degree = request.form.get('degree', 1)
    question = request.form.get('question')

    if question == None or question == '':
        answer = ''

    else:
        answer = "Lorem Ipsum is simply dummy text of the printing and typesetting industry. Lorem Ipsum has been the industry's standard dummy text ever since the 1500s, when an unknown printer took a galley of type and scrambled it to make a type specimen book. It has survived not only five centuries, but also the leap into electronic typesetting, remaining essentially unchanged. It was popularised in the 1960s with the release of Letraset sheets containing Lorem Ipsum passages, and more recently with desktop publishing software like Aldus PageMaker including versions of Lorem Ipsum."

    return render_template('index.html', seed_author_name=seed_author_name, degree=degree, question=question, answer=answer)


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
