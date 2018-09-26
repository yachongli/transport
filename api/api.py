from flask import Flask, abort, request
from manager_rpc import Manager
import logging
import json

app = Flask(__name__)
try:
    manager = Manager()
except:
    raise

logging.basicConfig(filename="/var/log/trasnport.log", level=logging.INFO, filemode='a+',
                    format=('%(asctime)s - %(levelname)s: %(message)s'))
LOG = logging.getLogger(__name__)


@app.route('/send_file', methods=['POST'])
def send_file():
    LOG.info("Flask method %s", "send_file")
    if request.get_data():
        body = json.loads(request.get_data())
    elif not request.json:
        abort(400)
        body = request.json
    LOG.info("Flask method %s, request body is %s " % ("send_file", body))
    return manager.send_file(body)


@app.route('/get_file', methods=['POST'])
def get_file():
    # not use
    LOG.info("Flask method %s", "get_file")
    if request.get_data():
        body = json.loads(request.get_data())
    elif not request.json:
        abort(400)
        body = request.json
    LOG.info("Flask method %s, request body is %s " % ("get_file", body))
    return manager.get_file(body)


@app.route('/set_copy', methods=['POST'])
def set_copy():
    LOG.info("Flask method %s", "set_copy")
    if request.get_data():
        body = json.loads(request.get_data())
    elif not request.json:
        abort(400)
        body = request.json
    LOG.info("Flask method %s, request body is %s " % ("set_copy", body))
    return manager.set_copy(body)


@app.route('/get_copy', methods=['POST'])
def get_copy():
    # not use
    LOG.info("Flask method %s", "get_copy")
    if request.get_data():
        body = json.loads(request.get_data())
    elif not request.json:
        abort(400)
        body = request.json
    LOG.info("Flask method %s, request body is %s " % ("get_copy", body))
    return manager.get_copy(body)


@app.route('/execute_command', methods=['POST'])
def execute_command():
    LOG.info("Flask method %s", "execute_command")
    if request.get_data():
        body = json.loads(request.get_data())
    elif not request.json:
        abort(400)
        body = request.json
    LOG.info("Flask method %s, request body is %s " % ("execute_command", body))
    return manager.execute_command(body)


# @app.route("/start_listen", methods=['POST'])
# def start_listen():
#     manager.start_listen()
#
#
# @app.route("/start_all_listen", methods=['POST'])
# def start_all_listen():
#     if not request.json:
#         abort(400)
#     body = request.json
#     manager.start_all_listen(body)
#     return json.dumps({})


if __name__ == '__main__':
    LOG.info("api server start")
    app.run(host='0.0.0.0', port=5001, debug=True)
