from server import SocketServer
import Queue
import os
import json
import datetime
import socket
from threading import Thread
from uuid import uuid4
from pymongo import MongoClient
import logging
import ConfigParser

logging.basicConfig(filename="/var/log/flag.log", level=logging.INFO, filemode='a+',
                    format=('%(asctime)s - %(levelname)s: %(message)s'))
LOG = logging.getLogger(__name__)


class Manager(object):
    def __init__(self):
        self.check_port_exise()
        self.start_tcp_server()
        self.config = self._config_parse()
        self._get_mongo()

    def _config_parse(self):
        real_path = os.path.split(os.path.realpath(__file__))[0]
        config_file = real_path + "/api.ini"
        config = ConfigParser.ConfigParser()
        config.read(config_file)
        config_dict = dict(config.items('default'))
        return config_dict

    def _get_mongo(self):
        if self.config.get("mongo_host"):
            host = self.config.get("mongo_host")
        else:
            host = "127.0.0.1"
        if self.config.get("mongo_user"):
            user = self.config.get("mongo_user")
            passwd = self.config.get("mongo_passwd")
            uri = "mongodb://%s:%s@%s/%s" % (user, passwd, host, self.config.get("mongo_db"))
        else:
            uri = "mongodb://%s" % (host)
        client = MongoClient(uri)
        db = client[self.config.get("mongo_db")]
        self.db_op = db.operation

    def start_tcp_server(self):
        self.queue = Queue.Queue()
        Thread(target=SocketServer, kwargs={"queue": self.queue}).start()
        # Process(target=SocketServer, kwargs={"queue": self.queue}).start()
        # while True:
        #     if not self.queue.empty():
        #         q = self.queue.get()
        #         if q == False:
        #             raise Exception("port already used")

    def send_file(self, pa):
        pa['operation'] = "send_file"
        pa['uuid'] = str(uuid4())
        pa['status'] = "running"
        pa['create_time'] = datetime.datetime.now()
        self.db_op.update_one(
            filter={"mac": pa['mac'], "uuid": pa['uuid']},
            update={"$set": pa},
            upsert=True
        )
        pa['create_time'] = str(pa['create_time'])
        try:
            LOG.info("send_file was called, put on to socket server params=%s" % json.dumps(pa))
            self.queue.put(pa)
        except Exception as e:
            print e
        return json.dumps(pa)

    def get_file(self, pa):
        pa['operation'] = "get_file"
        pa['uuid'] = str(uuid4())
        pa['status'] = "running"
        pa['create_time'] = datetime.datetime.now()
        self.db_op.update_one(
            filter={"mac": pa['mac'], "uuid": pa['uuid']},
            update={"$set": pa},
            upsert=True
        )
        pa['create_time'] = str(pa['create_time'])
        LOG.info("get_file was called, put on to socket server params=%s" % json.dumps(pa))
        self.queue.put(pa)
        # self.queue.put(pa)
        return json.dumps(pa)

    def check_port_exise(self, port=4555):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.connect(("127.0.0.1", port))
            s.shutdown(2)
            raise Exception("port was occupy")
        except:
            pass

    def get_copy(self, pa):
        pa['uuid'] = str(uuid4())
        pa['status'] = "running"
        pa['operation'] = "get_copy"
        pa['create_time'] = datetime.datetime.now()
        self.db_op.update_one(
            filter={"mac": pa['mac'], "uuid": pa['uuid']},
            update={"$set": pa},
            upsert=True
        )
        LOG.info("get_copy was called, put on to socket server params=%s" % json.dumps(pa))
        pa['create_time'] = str(pa['create_time'])
        self.queue.put(pa)
        return json.dumps(pa)

    def set_copy(self, pa):
        pa['uuid'] = str(uuid4())
        pa['status'] = "running"
        pa['operation'] = "set_copy"
        pa['create_time'] = datetime.datetime.now()
        self.db_op.update_one(
            filter={"mac": pa['mac'], "uuid": pa['uuid']},
            update={"$set": pa},
            upsert=True
        )
        LOG.info("set_copy was called, put on to socket server params=%s" % json.dumps(pa))
        pa['create_time'] = str(pa['create_time'])
        self.queue.put(pa)
        return json.dumps(pa)

    def execute_command(self, pa):
        pa['uuid'] = str(uuid4())
        pa['status'] = "running"
        pa['create_time'] = datetime.datetime.now()
        pa['operation'] = "execute_command"
        self.db_op.update_one(
            filter={"mac": pa['mac'], "uuid": pa['uuid']},
            update={"$set": pa},
            upsert=True
        )
        if not pa.get("need_return"):
            pa["need_return"] = False
        elif pa["need_return"] == 1:
            pa["need_return"] = True
        else:
            pa["need_return"] = False
        pa['create_time'] = str(pa['create_time'])
        LOG.info("execute_command was called, put on to socket server params=%s" % json.dumps(pa))
        self.queue.put(pa)
        return json.dumps(pa)
