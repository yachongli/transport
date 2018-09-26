# not use

import os
import socket
import json
import time
import uuid
import gevent
from threading import Thread
import Queue

class UnixPipesMiddle(object):
    def __init__(self, server_address1, server_address2):
        self.server_address1 = server_address1
        self.server_address2 = server_address2
        self.send_count = {}
        self._set_unix_socket()
        self.connect = False
        self.queue = Queue.Queue()

    def _set_unix_socket(self):
        # self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect(self.server_address1)
        # self.sock.setblocking(False)
        # self._reconnect()

    def _reconnect(self):
        print "123"
        uid = self.uid()
        self.sock.send(json.dumps({
            "uuid": uid,
            "operation": "reconnect"
        }))
        self.send_uuid.append(uid)
        return True

    def uid(self):
        return str(uuid.uuid4())

    def _send_step_two(self, file):
        # sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(self.server_address2)
        send_fd = open(file, "r")
        print "send start"
        sock.send(send_fd.read())
        sock.send("LYC")
        send_fd.close()
        sock.close()
        print "send over"

    def _send_step_one(self, pa):
        """
        :param pa: {"path":"/xxx/xxx..", "name":"xxx.xxx","size":"23123(Bytes)"}
        :return:
        """
        a = 0
        if type(pa) != dict:
            print "not a leggal command"
            return

        # send_cmd = json.dumps(pa)
        print "handshake send_file start "
        # self.sock.sendall(open("test.txt").read())
        a += 1
        data = {
            "name": "123.txt",
            "path": "/root",
            "size": "10kb",
            "operation": "send_file"
        }
        self._send(data)
        # self.sock.sendall(json.dumps(data))
        time.sleep(1)
        print "handshake send_file stop"

    def _send(self, data, need_return=False):
        data['uuid'] = str(uuid.uuid4())
        self.sock.sendall(json.dumps(data))
        self.send_count[data['uuid']] = data

    def command_parse(self, cmd):
        if type(cmd) != dict:
            print "not a leggal command"
            return
        cmd_header = cmd.keys()[0]
        if hasattr(self, cmd_header):
            getattr(self, cmd_header)(cmd.values[0])

    def transmit(self, params=None):
        """
        :param params:
        :return:
        """
        self._send_step_one(
            {"operation": "send_file",
             "path": "/root/",
             "name": "123.txt",
             "size": "1k"
             }
        )

    def trasmit_back(self, params):
        print "handshake send_file back, start send..."
        self._send_step_two()

    def recive_file(self, params):
        pass

    def send_shell(self, params):
        pass

    def get_register(self, params):
        pass

    def edit_register(self, params):
        pass

    def add_registter(self, params):
        pass

    def cmd_socket_send(self):
        # while True:
        self.transmit()
            # print 1
            # gevent.sleep(1)

    def cmd_socket_recive(self):
        while True:
            try:
                self.sock.settimeout(1)
                recv = self.sock.recv(1024)
                self.sock.settimeout(100)
                if recv:
                    Thread(target=self.recive_parse, kwargs=json.loads(recv)).start()
            except:
                pass

    def recive_parse(self, **recv):
        if recv['uuid'] in self.send_count:
            if hasattr(self, recv['operation']) and recv.get("answer") == "ok":
                getattr(self, recv["operation"] + "_back")(recv)

    def transmit_back(self, params):
        print "handshake send_file back, start send..."
        self._send_step_two("/root/ubuntu-18.04-desktop-amd64.iso")

    def start(self):
        # gevent.spawn(self.cmd_socket_send())
        # gevent.spawn(self.cmd_socket_recive())
        t1 = Thread(target=self.cmd_socket_send)
        t2 = Thread(target=self.cmd_socket_recive)
        t1.start()
        t2.start()
        t1.join()
        t2.join()


if __name__ == '__main__':
    unix = UnixPipesMiddle(
        # server_address1="/var/lib/libvirt/qemu/channel/target/domain-centos7.0/org.qemu.guest_agent.0",
        server_address1=("127.0.0.1", 4555),
        # server_address2=("127.0.0.1", 4556)
        server_address2="/var/lib/libvirt/qemu/channel/target/domain-centos7.0/org.qemu.guest_agent.1"
        )

    unix.start()
