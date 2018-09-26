# -*- coding: utf-8 -*-

import oslo_messaging as messaging
import os
import ConfigParser

import base64
from oslo_config import cfg

CONF = cfg.CONF


real_path = os.path.split(os.path.realpath(__file__))[0]
config_file = real_path + "/api.ini"
config = ConfigParser.ConfigParser()
config.read(config_file)
config_dict = dict(config.items('default'))



transport = messaging.get_transport(CONF, url='rabbit://%s:%s@%s:5672/'%(
    config_dict['rabbitmq_user'],
    config_dict['rabbitmq_pw'],
    config_dict['rabbitmq_host']
))


class RpcClient(object):

    def __init__(self):
        self.ctxt = {}
        target = messaging.Target(topic='test', version='2.0', namespace='control')
        self._client = messaging.RPCClient(transport, target)

    def send_file(self, arg):
        self._client.target.topic = arg['node']
        try:
            return self._client.call(self.ctxt, 'send_file', **arg)
        except Exception as e:
            raise e

    def set_copy(self, arg):
        self._client.target.topic = arg['node']
        try:
            arg['copy'] = base64.b64encode(arg['copy'].encode("utf-8"))
            return self._client.call(self.ctxt, 'set_copy', **arg)
        except:
            raise

    def execute_command(self, arg):
        self._client.target.topic = arg['node']
        try:
            return self._client.call(self.ctxt, 'execute_command', **arg)
        except:
            raise
