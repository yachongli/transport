# this file not use , but it's useful

import logging
import os
import json
import time
from gevent import socket, monkey
from threading import Thread
from pymongo import MongoClient
import datetime

monkey.patch_all()

host = '0.0.0.0'
port = 4555
addr = (host, port)

logging.basicConfig(filename="/var/log/flag.log", level=logging.INFO, filemode='a+',
                    format=('%(asctime)s - %(levelname)s: %(message)s'))
LOG = logging.getLogger(__name__)


class SocketServer():
    def __init__(self, *args, **kwargs):
        self.queue = kwargs['queue']
        self.get_mongo()
        self.check_alive()
        self.start_server()
        self.conns = {}

    def start_server(self):
        t1 = Thread(target=self.event_queue)
        t2 = Thread(target=self.event_connect)
        t1.start()
        t2.start()

    def get_mongo(self):
        try:
            client = MongoClient("127.0.0.1")
            self.db_hb = client.ncr.heartbeat
            self.db_op = client.ncr.operation
            self.db_cp = client.ncr.clip
            self.db_cp.remove({})
            self.db_hb.remove({})
        except:
            print 'cannot connect boot_status'
            return

    def handle_request(self, conn):
        # Thread(target=self.event_queue, args=(conn)).start()
        while True:
            try:
                data = conn.recv(1024)
                if data:
                    Thread(target=self.recv_parse, args=(conn, data)).start()
            except Exception as e:
                print e
                pass
            else:
                if data:
                    pass
            time.sleep(1)
            # print "recv:", data

    def event_queue(self):
        while True:
            try:
                self.check_alive()
                if not self.queue.empty():
                    a = self.queue.get()
                    LOG.info("socket recive params from api, params=%s" % a)
                    Thread(target=self.send_parse, kwargs=(a)).start()
                time.sleep(1)
            except Exception as e:
                LOG.error("socket recive params from api, but something wrong, error:" % e.message)

    def event_connect(self):
        s = socket.socket()
        s.bind((host, port))
        s.listen(500)
        s.settimeout(1)
        while True:
            try:
                cli, addr = s.accept()
                # LOG.info("A vm was connect to socket server , %s" % addr)
                self.conns[":".join((addr[0], str(addr[1])))] = cli
                # gevent.spawn(self.handle_request, cli)
                Thread(target=self.handle_request, args=(cli,)).start()
            except Exception as e:
                print e
                pass
            time.sleep(1)
                # LOG.error("A vm was connect to socket server , but something wrong, error:%s" % e.message)

    def send_parse(self, **pa):
        host, port = None, None
        mac = pa['mac']
        he = self.db_hb.find({"mac": mac})
        operation = pa['operation']
        if he.count() > 0:
            if operation == "send_file":
                for h in he:
                    if h.get("is_send") and h['is_send']:
                        pa['error'] = "Another file is sending, please wait"
                        self._operation_error(pa)
                        LOG.warn("Another file is sending, please wait, uuid=%s, mac=%s" %
                                 (pa.get('uuid'), pa.get("mac")))
                        return
            he = self.db_hb.find({"mac": mac})
            for h in he:
                if not (h.get("is_send") and h['is_send']):
                    host = h.get("connect_address")
                    port = str(h.get("connect_port"))
                    break
            if host:
                try:
                    conn = self.conns[":".join((host, port))]
                    if hasattr(self, pa['operation']):
                        getattr(self, pa['operation'])(conn, pa)
                except Exception as e:
                    print e
                    pass
            else:
                pa['error'] = "Another file sendding, please wait"
                LOG.warn("Another file is sending, please wait, uuid=%s, mac=%s" %
                         (pa.get('uuid'), pa.get("mac")))
                self._operation_error(pa)
        else:
            pa['error'] = "No host alive"
            LOG.warn("No host alive, it may be not connect, uuid=%s, mac=%s" %
                     (pa.get('uuid'), pa.get("mac")))
            self._operation_error(pa)

    def check_alive(self):
        now_time = datetime.datetime.now()
        # all_item = self.db_hb.find()
        try:
            for item in self.db_hb.find():
                sec = (now_time - item['last_time']).seconds
                # if sec > 30:
                if sec > 100:
                    self.db_hb.remove(item)
                    LOG.warn("A host will be delete,  mac=%s" %
                             (item["mac"]))
                elif sec > 20:
                    LOG.warn("A host will be disconnectd,  mac=%s" %
                             (item["mac"]))
                    self.db_hb.update_one({"mac": item['mac'], "connect_port": item['connect_port']},
                                          {"$set": {"is_alive": False}})
        except Exception as e:
            print e

    def recv_parse(self, conn, data):
        # print data , type(data)
        try:
            data = json.loads(data)
            if data.get("uuid"):
                if hasattr(self, data['operation'] + "_back"):
                    getattr(self, data['operation'] + "_back")(conn, data)
            elif hasattr(self, data['operation']):
                getattr(self, data['operation'])(conn, data)
        except Exception as e:
            print e
            print data

    def send_file_back(self, conn, data):
        if not (data.get("error") and data['error']):
            full_path = data['s_file']
            fd = open(full_path, "rb")
            self._update_send_status(data, conn.getpeername()[1], True)
            LOG.info("send file step two running ,sending ....,uuid=%s" % data["uuid"])
            last_none = False
            while True:
                # r = os.read_fd(fd, 20480)
                r = fd.read(20480)
                if r or len(r):
                    conn.send(r)
                elif not last_none:
                    last_none = True
                else:
                    break
                time.sleep(0.00000000001)
            time.sleep(1)
            conn.send("LYC")
            LOG.info("send file step two ending, uuid=%s" % data["uuid"])
            # os.close(fd)
            fd.close()
            data['response'] = "success"
            self._operation_success(data)
            self._update_send_status(data, conn.getpeername()[1], False)
        else:
            self._operation_error(data)

    def get_copy(self, conn, data):
        self.db_cp.update_one(
            filter={"mac": data['mac']},
            update={"$set": data},
            upsert=True
        )

    def set_copy(self, conn, data):
        LOG.info("set_copy starting,uuid=%s" % data["uuid"])
        self.send(conn, data)

    def set_copy_back(self, conn, data):
        LOG.info("set_copy ending ,uuid=%s" % data["uuid"])
        if data.get("error") and data['error']:
            self._operation_error(data)
        else:
            self._operation_success(data)

    def _update_send_status(self, data, port, state):
        self.db_hb.update_one(
            filter={"mac": data['mac'], "connect_port": port},
            update={"$set": {"is_send": state}},
            upsert=True
        )

    def _operation_error(self, data):
        self.db_op.update_one(
            filter={"uuid": data['uuid']},
            update={"$set": {
                "status": "error", "error": data['error'], "response": None,
                "end_time": datetime.datetime.now()
            }},
            upsert=True
        )

    def _operation_success(self, data):
        self.db_op.update_one(
            filter={"uuid": data['uuid']},
            update={"$set": {
                "status": "completed", "error": None, "response": data.get("response"),
                "end_time": datetime.datetime.now()
            }},
            upsert=True
        )

    def send_file(self, conn, data):
        LOG.info("send_file step on starting ,uuid=%s" % data["uuid"])
        # data['uuid'] = str(uuid.uuid4())
        if not os.path.exists(data['s_file']):
            data['error'] = "Source file not exists"
            self._operation_error(data)
        else:
            self.send(conn, data)

    def get_file(self, conn, data):
        pass

    def heartbeat(self, conn, data):
        d = {
            "connect_address": conn.getpeername()[0],
            "connect_port": conn.getpeername()[1],
            "is_alive": True,
            # "is_send": False,
            "last_time": datetime.datetime.now()
        }

        data.pop("operation")
        d.update(data)
        self.db_hb.update_one(filter={"mac": data["mac"], "connect_port": d['connect_port']},
                              update={'$set': d},
                              upsert=True)

    def send(self, conn, data):
        # print "send"
        conn.sendall(json.dumps(data))

    def execute_command(self, conn, data):
        LOG.info("execute_command starting ,uuid=%s" % data["uuid"])
        # data['uuid'] = str(uuid.uuid4())
        self.send(conn, data)

    def execute_command_back(self, conn, data):
        LOG.info("execute_command ended ,uuid=%s" % data["uuid"])
        if data.get("error") and data['error']:
            self._operation_error(data)
        else:
            self._operation_success(data)
