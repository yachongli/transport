import oslo_messaging as messaging
import eventlet
import socket
import os
import ConfigParser

eventlet.monkey_patch()

from oslo_config import cfg
import oslo_messaging
import time
from manager import Manager

CONF = cfg.CONF


class MyEndpoint(Manager):
    target = oslo_messaging.Target(namespace='control', version='2.0')

    def __init__(self):
        super(MyEndpoint, self).__init__()

    def test(self, ctx, arg):
        self.t()
        return arg


real_path = os.path.split(os.path.realpath(__file__))[0]
config_file = real_path + "/compute.ini"
config = ConfigParser.ConfigParser()
config.read(config_file)
config_dict = dict(config.items('default'))


def main():
    topic = socket.gethostname()
    transport = messaging.get_transport(CONF, url='rabbit://%s:%s@%s:5672/' % (
        config_dict['rabbitmq_user'],
        config_dict['rabbitmq_pw'],
        config_dict['rabbitmq_host']
    ))
    target = oslo_messaging.Target(topic=topic, server='server1')
    endpoints = [
        # ServerControlEndpoint(),
        MyEndpoint(),
    ]
    server = oslo_messaging.get_rpc_server(transport, target, endpoints,
                                           executor='eventlet')
    try:
        server.start()
        while True:
            time.sleep(1)
    except:
        print("Stopping start_server")
    server.stop()
    server.wait()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print e
        print "exist"
