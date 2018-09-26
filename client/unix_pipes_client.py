import json
import os
import time
import socket
import select
import gevent
import datetime
import threading


class UnixPipesClient(object):
    def __init__(self, vport1, vport2):
        self.vport1 = vport1
        self.vport2 = vport2
        self.pipe1 = os.open(self.vport1, os.O_RDWR|os.O_NONBLOCK)
        self.pipe2=None

        # self.pipe1 = open(self.vport1, "r")

    def _open_pipe2(self):
        self.pipe2 = os.open(self.vport2, os.O_RDONLY | os.O_NONBLOCK)
        # os.close(self.pipe2)

    def _recive_step_one(self, params):
        # send i'm ok , please start

        try:
            try:
                os.close(self.pipe2)
            except:
                pass
            self._open_pipe2()
        except Exception as e:
            print e
            params['answer'] = "no"
            params['reason'] = "can't open transport pipe"
            os.write(self.pipe1,json.dumps(params))
        else:
            params['answer'] = "ok"
            params['status'] = "wait"
            os.write(self.pipe1, json.dumps(params))
            return params


    def _recive_step_two(self,**kwargs):
        full_path = kwargs.get("path")+"/" + kwargs.get("name")
        write_file = open(full_path, "w+")
        # os.close(self.pipe2)
        print "start_recive"
        print os.path.getsize(full_path)/1024/1024
        threading.Thread(target=self.count_size, kwargs={"path":full_path}).start()
        while True:
            recv = None
            try:
                recv = os.read(self.pipe2,1024)
            except:
                pass
            if recv == "LYC":
                break
            elif recv:
                write_file.write(recv)
        print "recive end "
        os.close(self.pipe2)

    def count_size(self,**kwargs):
        last_size = os.path.getsize(kwargs['path']) / 1024 / 1024
        while True:
            time.sleep(1)
            now_size = os.path.getsize(kwargs['path']) / 1024 / 1024
            print now_size
            if now_size == last_size:
                break
            else:
                last_size = now_size


    def recive_cmd(self, params):
        if type(params) != dict:
            return
        if hasattr(self, params.get("operation")):
            getattr(self, params.get("operation"))(params)

    # def reconnect(self, params):
    #     # pipe = os.open(self.vport1, os.O_RDWR | os.O_NONBLOCK)
    #     os.write(self.pipe1,json.dumps(params))

    def transmit_file(self, params):
        file_name = params.get("name")
        file_path = params.get("path")
        file_size = params.get("size")
        if file_name and file_path and file_size:
            # prepare to recive it
            if not os.path.exists(file_path):
                os.mkdir(file_path)
            step_on_ret = self._recive_step_one(params)
            if step_on_ret:
                # gevent.spawn(self._recive_step_two,step_on_ret)
                recive_thread = threading.Thread(target=self._recive_step_two,kwargs=step_on_ret)
                recive_thread.start()
        else:
            print "file_name or file_path or file_size not yield"

    def check_recive(self):
        pass

    def start(self):

        # while True:
        a = 0
        # f= open("abc.txt","w+")
        while True:
            # f = open(self.vport1)
            recv = None
            try:
                recv = os.read(self.pipe1,1024)
            except Exception as e:
                pass
            if recv:
                # print recv
                self.recive_cmd(json.loads(recv))
                # print recv
                # f.write(recv)
            else:
                # print "no recive"
                # print datetime.datetime.now()
                time.sleep(1)

if __name__ == '__main__':
    client = UnixPipesClient(vport1="/dev/virtio-ports/org.qemu.guest_agent.0",vport2="/dev/virtio-ports/org.qemu.guest_agent.1")
    client.start()


    a="10"
