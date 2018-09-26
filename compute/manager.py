import os
import socket
from compute import UnixPipesMiddle
import Queue
import json
import threading
import logging

LOG = logging.getLogger(__name__)


class Manager(object):
    def __init__(self):
        # self.start_all_listen()
        self.queues = {}
        self.threadings = {}
        self.unix_mid = UnixPipesMiddle()
        self.unix_mid.start_connect_all()
        # self.start_all_listen()

    # def start_all_listen(self, *args, **kwargs):
    #     """
    #     :param channel: {"port1":"4555","port2":"4556"}
    #     :return:
    #     """
    #     # i want it from controller, bu now start by itself
    #     # while True:
    #     channels = kwargs['ports']
    #     for channel in channels:
    #         channel_name = channel['port1']
    #         self.queues[channel_name] = Queue.Queue()
    #         try:
    #             t = threading.Thread(target=UnixPipesMiddle,
    #                                  args=(channel['port1'], channel['port2'], self.queues[channel_name]))
    #             t.start()
    #             self.threadings[channel_name] = t
    #         except:
    #             del self.queues[channel_name]

    def t(self):
        self.queues.values()[0].put("123")

    def send_file(self, *args, **kwargs):
        LOG.info("send_file: rpc recive, params is %s", kwargs)
        # pa = json.loads(arg)
        # if kwargs['port1'] not in self.queues:
        #     self.start_all_listen([{"port1":kwargs['port1'],"port2":kwargs['port2']}])
        # target_port = kwargs.pop("port1")
        # self.queues[target_port].put(kwargs)
        return self.unix_mid.send_file(kwargs)

    def set_copy(self, *args, **kwargs):
        LOG.info("set_copy: rpc recive, params is %s", kwargs)
        return self.unix_mid.set_copy(kwargs)

    def execute_command(self, *args, **kwargs):
        LOG.info("execute_command: rpc recive, params is %s", kwargs)
        return self.unix_mid.execute_command(kwargs)

if __name__ == '__main__':
    manager = Manager()
    manager.test()

    # manager.start_all_listen()
