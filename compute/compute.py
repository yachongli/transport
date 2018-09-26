import os
import socket
import json
import time
import datetime
from threading import Thread
import logging
from xml.etree import ElementTree
import libvirt
from pymongo import MongoClient
import base64
import ConfigParser
import uuid


class UnixPipesMiddle(object):
    def __init__(self):
        self.send_count = {}
        self.channels_sending = []
        self.config = self.config_parse()
        self.log = self.get_logging()
        self.connect = False
        self.channels = {}
        self.get_mongo()
        self.libvirt_conn = libvirt.open("qemu:///system")

    def config_parse(self):
        real_path = os.path.split(os.path.realpath(__file__))[0]
        config_file = real_path + "/compute.ini"
        config = ConfigParser.ConfigParser()
        config.read(config_file)
        return dict(config.items('default'))

    def get_logging(self):
        if self.config['debug'].lower() == "false":
            logging.basicConfig(filename="/var/log/transport.log", level=logging.INFO, filemode='a+',
                                format=('%(asctime)s - %(levelname)s: %(message)s'))
        else:
            logging.basicConfig(filename="/var/log/transport.log", level=logging.DEBUG, filemode='a+',
                                format=('%(asctime)s - %(levelname)s: %(message)s'))
        LOG = logging.getLogger(__name__)
        return LOG

    def start_connect_all(self):
        self.log.info("Starting to connect all alive host")
        Thread(target=self._start_connect_all).start()

    def _start_connect_all(self):
        node = socket.gethostname()
        while True:
            address = self.get_all_alive()
            try:
                for name in list(self.channels.keys()):
                    if name not in address.keys():
                        del self.channels[name]
                        self.db_hb.remove({"domain_name": name, "node": node})
                for name in address:
                    for addr in address[name]:
                        if not name in self.channels:
                            self.channels[name] = {}
                        if type(addr) != str and not self.channels[name].get("tcp"):
                            Thread(target=self._set_tcp_socket, args=(name, addr)).start()
                        elif not self.channels[name].get("unix"):
                            Thread(target=self._set_unix_socket, args=(name, addr,)).start()
            except Exception as e:
                print e
            time.sleep(2)

    def get_all_alive(self):
        address = {}
        domain_ids = self.libvirt_conn.listDomainsID()
        self.log.debug("Domains find, all id is %s" % domain_ids)
        for id in domain_ids:
            domain = self.libvirt_conn.lookupByID(id)
            domain_name = domain.name()
            domain_xml = domain.XMLDesc()
            address[domain_name] = self.parse_domain_xml(domain_xml)
            self.log.debug("Domain %s is find, address=%s" % (domain_name, address[domain_name]))
        return address

    def parse_domain_xml(self, domain_xml):
        address_list = []
        xl = ElementTree.fromstring(domain_xml)
        a = xl.getiterator("channel")
        for b in a:
            if b.attrib['type'] == "tcp":
                for child in b.getchildren():
                    if child.tag == "source":
                        host = child.attrib['host']
                        port = int(child.attrib['service'])
                        address_list.append((host, port))

        for b in a:
            if b.attrib['type'] == "unix":
                for child in b.getchildren():
                    if child.tag == "source":
                        addr = child.attrib['path']
                        address_list.append(addr)
        return address_list

    def _set_tcp_socket(self, domain, address):
        if not self.channels.get(domain):
            self.channels[domain] = {}
        if self.channels[domain].get("tcp"):
            return
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.settimeout(2)
            sock.connect(address)
            sock.settimeout(10)
        except:
            self.log.info("Tcp socket connect timeout, domain_name=%s, port=%s" % (domain, address[1]))
            pass
        else:
            self.channels[domain]["tcp"] = sock
            self.log.info("Tcp socket connect success, domain_name=%s, pipe=%s" % (domain, address[1]))
            Thread(target=self.start_listen, args=(sock,)).start()

    def _set_unix_socket(self, domain, channel_path):
        if not self.channels.get(domain):
            self.channels[domain] = {}
        if self.channels[domain].get("unix"):
            return
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        # print channel_path
        try:
            sock.settimeout(2)
            sock.connect(channel_path)
            sock.settimeout(20)
        except:
            self.log.info("Unix socket connect timeout, domain_name=%s, pipe=%s" % (domain, channel_path))
            pass
        else:
            self.channels[domain]["unix"] = sock
            self.log.info("Unix socket connect success, domain_name=%s, pipe=%s" % (domain, channel_path))
            # Thread(target=self.start_listen, args=(sock,)).start()

    def get_mongo(self):
        try:
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
            node = socket.gethostname()
            client = MongoClient(uri)
            db = client[self.config.get("mongo_db")]
            self.db_hb = db.heartbeat
            self.db_op = db.operation
            self.db_cp = db.clip
            self.db_ve = db.client_version
            self.db_cp.remove({"node": node})
            self.db_hb.remove({"node": node})
            self.db_op.update_many(
                {"status": "running", "node": node},
                {"$set": {"status": "error", "response": "Transmission is interrupted"}},
            )
            self.log.info("connect mongodb success")
        except Exception as e:
            self.log.info("can't connect to mongodb")
            return

    def heartbeat(self, conn, data):
        print data
        domain_name = None
        d = {
            "connect_address": conn.getpeername()[0],
            "connect_port": conn.getpeername()[1],
            "is_alive": True,
            # "is_send": False,
            "node": socket.gethostname(),
            "last_time": datetime.datetime.now()
        }
        for domain_name in self.channels:
            if conn in self.channels[domain_name].values():
                break
        d['domain_name'] = domain_name
        data.pop("operation")
        d.update(data)
        print d
        print data.get("version")
        version = self._get_version(d['system'])
        if version and d['version'] != version:
            Thread(target=self._update_host_file, args=(
                d['node'], d['domain_name'], d['system'], d['dir'])).start()
        self.db_hb.update_one(filter={"node": d['node'], "domain_name": d['domain_name']},
                              update={'$set': d},
                              upsert=True)
        self.log.debug("from port %s heartbeat check" % d["connect_port"])

    def _update_host_file(self, node, domain, system, file_path):
        # send upgrade file to client , node+domain ,
        host_file = self.config.get("%s_file" % system.lower())
        if host_file and os.path.exists(host_file):
            uid = str(uuid.uuid4())
            dic = {
                "uuid": uid,
                "domain_name": domain,
                "node": node,
                "system": system,
                "s_file": host_file,
                "path": file_path[0],
                "name": file_path[1],
                "operation": "send_file",
                "create_time": datetime.datetime.now()
            }
            self.db_op.insert(dic)
            dic.pop("create_time")
            if dic.get("_id"):
                dic.pop("_id")
            self.send_file(dic)
            times = 0
            while True:
                hb = self.db_op.find_one({"uuid": uid})
                if hb.get("status") == "completed":
                    break
                if times > 20 or hb.get('status') == "error":
                    return
                else:
                    times += 1
                    time.sleep(0.1)

    def _get_version(self, system):
        ve = self.db_ve.find_one()
        if ve:
            return ve.get(system)

    def start_listen(self, conn):
        while True:
            try:
                data = conn.recv(102400)
                if data:
                    Thread(target=self.recv_parse, args=(conn, data)).start()
            except Exception as e:
                pass
            else:
                if data:
                    pass
            time.sleep(1)

    def recv_parse(self, conn, data):
        self.log.debug("from %s recive %s" % (conn.getpeername()[1], data))
        try:
            data = json.loads(data)
            if data.get("uuid"):
                if hasattr(self, data['operation'] + "_back"):
                    getattr(self, data['operation'] + "_back")(conn, data)
            elif hasattr(self, data['operation']):
                try:
                    getattr(self, data['operation'])(conn, data)
                except Exception as e:
                    print e
        except Exception as e:
            self.log.info("from %s recive %s ,but error:%s" % (conn.getpeername()[1], data, e.message))

    def _get_channel_by_domain(self, domain, is_send=False):
        channels = self.channels.get(domain)
        if not channels:
            self.log.info("No host found %s" % domain)
            return None
        if is_send:
            if not channels.get("unix"):
                print datetime.datetime.now()
                domain = self.libvirt_conn.lookupByName(domain)
                domain_name = domain.name()
                domain_xml = domain.XMLDesc()
                address = self.parse_domain_xml(domain_xml)
                for addr in address:
                    if type(addr) == str:
                        self._set_unix_socket(domain_name, addr)
                print datetime.datetime.now()
            return channels.get("unix")
        else:
            return channels.get("tcp")

    def _send(self, channel, data):
        # print "send"
        try:
            channel.sendall(json.dumps(data))
        except:
            print "send_faild"
        print "send"

    def send_file(self, data):
        if data.get("s_file"):
            self.log.info("send_file step on starting ,uuid=%s" % data["uuid"])
            if data['domain_name'] in self.channels_sending:
                self.log.info(
                    "A file is already sent, please wait for its completion, then try again,uuid=%s" % data["uuid"])
                data['response'] = "A file is already sent, please wait for its completion, then try again."
                self._operation_error(data)
                return

            if not data.get("path"):
                data = self.get_path_from_heartbeat(data)

            channel = self._get_channel_by_domain(data['domain_name'])
            if channel and type(channel) != str:
                # data['uuid'] = str(uuid.uuid4())
                if not os.path.exists(data['s_file']):
                    data['response'] = "Source file not exists"
                    self._operation_error(data)
                else:
                    data['size'] = os.path.getsize(data['s_file'])
                    self._send(channel, data)
            else:
                data['response'] = "No host found"
                self.log.info(
                    "No host found. %s" %
                    data[
                        'domain_name'])
                self._operation_error(data)
                return
        elif data.get("s_text"):
            self.save_text_to_file(data)

    def get_path_from_heartbeat(self, data):
        hb = self.db_hb.find_one({
            "domain_name": data["domain_name"],
            "node": data["node"]
        })
        if hb:
            if hb['system'].lower() == "windows":
                data['path'] = "c:\\"
            else:
                data['path'] = "/tmp"
        else:
            data["path"] = "c:\\"
        return data

    def save_text_to_file(self, data):
        self.log.info("send_file step on starting ,uuid=%s" % data["uuid"])
        channel = self._get_channel_by_domain(data['domain_name'])
        if channel:
            self._send(channel, data)
        else:
            data['response'] = "No host found"
            self._operation_error(data)

    def send_file_back(self, conn, data):
        if data.get("s_file"):
            conn = self._get_channel_by_domain(data['domain_name'], is_send=True)
            if conn:
                self._send_file_back(conn, data)
            else:
                data['error'] = "The transmission pipeline is not connected successfully. Please try again later"
                self.log.info(
                    "The transmission pipeline is not connected successfully. Please try again later. %s" % data[
                        'domain_name'])
        elif data.get("s_text"):
            self._operation_success(data)

    def _send_file_back(self, conn, data):
        print data
        if not (data.get("error") and data['error']):
            try:
                full_path = data['s_file']
                fd = open(full_path, "rb")
                self.log.info("send file step two running ,sending ....,uuid=%s" % data["uuid"])
                last_none = False
                self.channels_sending.append(data['domain_name'])
                self._update_send_status(data, True)
                s = 0
                while True:
                    r = fd.read(20480)
                    if r or len(r):
                        conn.send(r)
                        s += len(r)
                    elif not last_none:
                        last_none = True
                    else:
                        break
                    # time.sleep(0.00000000001)
                time.sleep(1)
                self.log.debug("send_file end , size = %s" % s)
                # conn.send("51ELAB")
                print s
                del self.channels_sending[self.channels_sending.index(data['domain_name'])]
                self._update_send_status(data, False)
                self.log.info("send file step two ending, uuid=%s" % data["uuid"])
                fd.close()
                data['response'] = "success"
                self._operation_success(data)
            except Exception as e:
                data['response'] = e.message
                self._operation_error(data)
                del self.channels_sending[self.channels_sending.index(data['domain_name'])]
                self._update_send_status(data, False)
        else:
            data['response'] = data['error']
            data.pop("error")
            self._operation_error(data)

    # def _update_send_file_process(self):
    #     pass

    def set_copy(self, data):
        data['copy'] = base64.b64decode(data['copy'])
        self.log.info("set_copy starting,domain_name is %s,uuid=%s" % (data["domain_name"], data["uuid"]))
        channel = self._get_channel_by_domain(data['domain_name'])
        if channel:
            data['copy'] = base64.b64encode(data['copy'])
            self._send(channel, data)
        else:
            data['response'] = "No host found"
            self._operation_error(data)

    def set_copy_back(self, conn, data):
        self.log.info("set_copy ending ,uuid=%s" % data["uuid"])
        if data.get("error") and data['error']:
            data['response'] = data['error']
            data.pop("error")
            self._operation_error(data)
        else:
            self._operation_success(data)

    def execute_command(self, data):
        self.log.info("execute_command starting ,domain_name is %s,uuid=%s" % (data["domain_name"],
                                                                               data["uuid"]))
        # data['uuid'] = str(uuid.uuid4())
        channel = self._get_channel_by_domain(data['domain_name'])
        if channel:
            self._send(channel, data)
        else:
            data['response'] = "No host found"
            self._operation_error(data)

    def execute_command_back(self, conn, data):
        self.log.info("execute_command ended ,uuid=%s" % data["uuid"])
        if data.get("error") and data['error']:
            data['response'] = data['error']
            data.pop("error")
            self._operation_error(data)
        try:
            if data.get("response"):
                data['response'] = base64.b64decode(data['response'])
            self._operation_success(data)
        except Exception as e:
            print e

    def get_copy(self, conn, data):
        domain_name = None
        node = None
        pername = conn.getpeername()[1]
        for channel in self.channels:
            tcp_channels = self.channels[channel].get("tcp")
            if tcp_channels and pername == tcp_channels.getpeername()[1]:
                domain_name = channel
                node = socket.gethostname()
        data["paste_info"] = base64.b64decode(data["paste_info"])
        if domain_name:
            data['domain_name'] = domain_name
            data['node'] = node
            data['ip'] = socket.gethostbyname(data['node'])
            self.db_cp.update_one(
                filter={"domain_name": domain_name, "node": node},
                update={"$set": data},
                upsert=True
            )

    def send_parse(self, **cmd):
        if type(cmd) != dict:
            print "not a leggal command"
            return
        cmd_header = cmd['operation']
        if hasattr(self, cmd_header):
            getattr(self, cmd_header)(cmd)

    def _update_send_status(self, data, state=False):
        try:
            self.db_hb.update_one(
                filter={"domain_name": data['domain_name'], "node": data['node']},
                update={"$set": {"is_send": state}},
                upsert=True
            )
        except Exception as e:
            print e

    def _operation_error(self, data):
        self.log.debug("operation was error, %s" % data.get("response"))
        try:
            self.db_op.update_one(
                filter={"uuid": data['uuid']},
                update={"$set": {
                    "status": "error", "response": data["response"],
                    "end_time": datetime.datetime.now()
                }},
                upsert=True
            )
        except Exception as e:
            print e.message

    def _operation_success(self, data):
        self.log.debug("operation was success, %s" % data.get("response"))
        try:
            self.db_op.update_one(
                filter={"uuid": data['uuid']},
                update={"$set": {
                    "status": "completed", "response": data.get("response"),
                    "end_time": datetime.datetime.now()
                }},
                upsert=True
            )
        except Exception as e:
            print e.message


if __name__ == '__main__':
    unix = UnixPipesMiddle()
    unix.start_connect_all()
#
