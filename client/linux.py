import json
import os
import time
import threading
from threading import Thread
import socket
import platform
import uuid
import pyperclip
import subprocess
import base64
import sys
import shutil
import getpass
import psutil

def reboot_self():
    cmd = sys.executable + " " + '"' + os.path.realpath(sys.argv[0])+ '"' + ' ' + str(os.getpid())
    print cmd
    ret = os.system(cmd)


def confirm_transport(func):
    def _confirm_transport(*args, **kwargs):
        # print args
        recive_file = os.path.realpath("/".join([args[2]['path'], args[2]['name']]))
        print recive_file
        my_file = os.path.realpath(sys.argv[0])
        print my_file
        if my_file == recive_file:
            shutil.copyfile(my_file, my_file + ".bak")
            print "copy_file"
        func(*args, **kwargs)
        size = args[2]["size"]
        if my_file == recive_file:
            if os.path.getsize(my_file) != size:
                print "my_size", os.path.getsize(my_file)
                print "size", size
                shutil.copyfile(my_file + ".bak", my_file)
                os.remove(my_file + ".bak")
            else:
                os.remove(my_file + ".bak")
                os.close(args[0].channel1)
                reboot_self()
    return _confirm_transport


class VportClient(object):
    def __init__(self, vport1, vport2):
        self.vport1 = vport1
        self.vport2 = vport2
        self.start_recv()
        self.version = 1.0
        self.heart_beat()
        os.close(self.channel2)

    def start_recv(self):
        self.open_channel1()
        self.open_channel2()
        if self.channel1 and self.channel2:
            self.t1 = Thread(target=self.start_recv1)
            self.t1.start()

    def open_channel1(self):
        if os.path.exists(self.vport1):
            self.channel1 = os.open(self.vport1, os.O_RDWR | os.O_NONBLOCK)
            self.channel1_on_trans = False
            # Thread(target=self.start_recv1).start()
        else:
            self.channel1 = None

    def open_channel2(self):
        if os.path.exists(self.vport2):
            self.channel2 = os.open(self.vport2, os.O_RDWR | os.O_NONBLOCK)
            self.channel2_on_trans = False
            # Thread(target=self.start_recv2).start()
        else:
            self.channel2 = None

    def heart_beat(self):
        Thread(target=self._heart_beat).start()

    def _heart_beat(self):
        if self.channel1 and self.channel2:
            hb = {}
            hb['hostname'] = socket.getfqdn(socket.gethostname())
            hb['operation'] = "heartbeat"
            while True:
                all_interface = self._get_mac_address()
                # hb['cpu'] = psutil.cpu_count()
                hb['all_interface'] = all_interface
                if all_interface:
                    hb["mac"] = all_interface.keys()[0]
                    hb['ip'] = all_interface[hb["mac"]]
                else:
                    hb["mac"] = None
                    hb['ip'] = None
                hb['version'] = self.version
                hb['user'] = getpass.getuser()
                hb['dir'] = os.path.split(os.path.abspath(sys.argv[0]))
                hb['system'] = platform.system()
                try:
                    if self.channel1:
                        self._return(self.channel1, hb)
                    # if self.channel2:
                    #     self._return(self.channel2, hb)
                except Exception as e:
                    print e
                time.sleep(15)

    def _get_ip(self):
        return "127.0.0.1"

    def _get_mac_address(self):
        try:
            if hasattr(psutil, "net_if_addrs"):
                macs = {}
                all_interfaces = psutil.net_if_addrs()
                for inet in all_interfaces:
                    if inet != "lo":
                        mac, ip = None, None
                        for a in all_interfaces[inet]:
                            if a.family == -1 or a.family == 17:
                                mac = a.address.lower().replace("-", ":")
                            if a.family == 2:
                                ip = a.address
                        if mac and ip:
                            macs[mac] = ip
            else:
                macs = self._get_mac_address_1()
        except:
            macs = self._get_mac_address_1()
        return macs

    def _get_mac_address_1(self):
        mac = uuid.UUID(int=uuid.getnode()).hex[-12:]
        mac = ":".join([mac[e:e + 2] for e in range(0, 11, 2)])
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("www.baidu.com", 0))
            ip = s.getsockname()[0]
        except:
            ip = None
        return {mac: ip}

    @confirm_transport
    def save_to_file(self, channel, pa):
        try:
            full_path = pa.get("path") + "/" + pa.get("name")
            write_file = open(full_path, "wb")
            print "start_recive"
            print os.path.getsize(full_path) / 1024 / 1024
            threading.Thread(target=self.count_size, kwargs=({"channel": channel, "path": full_path})).start()
            s = 0
            error_count = 0
            while True:
                recv = ""
                try:
                    recv = os.read(channel, 1024)
                    s += len(recv)
                except Exception as e:
                    pass
                if recv == "LYC" or len(recv) == 3:
                    break
                elif not len(recv):
                    error_count += 1
                    time.sleep(0.2)
                    if error_count >= 10:
                        print error_count
                        break
                elif recv or len(recv):
                    error_count = 0
                    write_file.write(recv)
                # time.sleep(0.00000000001)
            print s
            print "recive end "
            os.close(channel)
            self.channel2 = None
            write_file.close()
        except Exception as e:
            pa['error'] = e.message
            os.close(channel)
            self.channel2 = None
            self._return(self.channel1, pa)

    def save_text_to_file(self, channel, pa):
        try:
            full_path = pa.get("path") + "/" + pa.get("name")
            write_file = open(full_path, "wb")
            write_file.write(pa['s_text'])
        except Exception as e:
            pa['error'] = e.message
            self._return(channel, pa)

    def count_size(self, **kwargs):
        last_size = os.path.getsize(kwargs['path']) / 1024 / 1024
        times = 0
        while True:
            time.sleep(1)
            now_size = os.path.getsize(kwargs['path']) / 1024 / 1024
            print now_size
            if now_size == last_size:
                break
            else:
                last_size = now_size

    def recive_cmd(self, channel, params):
        if hasattr(self, params.get("operation")):
            print params.get("operation")
            try:
                # getattr(self, params.get("operation"))(channel, params)
                Thread(target=getattr(self, params.get("operation")), args=(channel, params)).start()
            except Exception as e:
                params['error'] = e.message
                self._return(channel, params)

    def send_file(self, channel, params):
        file_name = params.get("name")
        file_path = params.get("path")
        file_size = params.get("size")
        if file_name and file_path and file_size:
            # prepare to recive it
            if not os.path.exists(file_path):
                params['error'] = "Target path not exist"
                self._return(channel, params)
        else:
            params['error'] = "file_name or file_path or file_size not yield"
            self._return(channel, params)
        if params.get("s_file"):
            self.open_channel2()
            self._return(channel, params)
            time.sleep(1)
            Thread(target=self.save_to_file, args=(self.channel2, params,)).start()
        elif params.get("s_text"):
            self.save_text_to_file(channel, params)

    def set_copy(self, channel, params):
        copy = params.get("copy")
        try:
            if copy:
                copy = base64.b64decode(copy)
                # os.popen("xclip -i %s" % copy)
                pyperclip.copy(copy)
            else:
                pyperclip.copy("")
        except Exception as e:
            params['error'] = e.message
        else:
            params['response'] = "success"
        self._return(channel, params)

    def _return(self, channel, params):
        os.write(channel, json.dumps(params))

    def get_copy(self):
        Thread(target=self._clip_monitor).start()

    def _clip_monitor(self, ):
        if self.channel1:
            last_paste = pyperclip.paste()
            channel = self.channel1
            while True:
                now_paste = pyperclip.paste()
                if last_paste != now_paste:
                    mac = self._get_mac_address().keys()[0]
                    self._return(channel,
                                 {
                                     "operation": "get_copy",
                                     "mac": mac,
                                     "paste_info": base64.b64encode(now_paste)
                                 }
                                 , )
                    last_paste = now_paste
                time.sleep(1)

    def start_recv1(self):
        while True:
            try:
                red = os.read(self.channel1, 1024)
                if red:
                    red = json.loads(red)
                    self.recive_cmd(self.channel1, red)
            except Exception as e:
                # print e
                pass
            time.sleep(1)

    def start_recv2(self):
        while True:
            try:
                red = os.read(self.channel2, 1024)
                if red:
                    red = json.loads(red)
                    self.recive_cmd(self.channel2, red)
            except:
                pass
            time.sleep(1)

    def execute_command(self, channel, params):
        Thread(target=self._execute_command, args=(channel, params,)).start()

    def _execute_command(self, channel, params):
        try:
            print "execute_command"
            ret = subprocess.Popen(params['cmd'], shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            if params.get("need_return") == True:
                params['response'] = base64.b64encode(
                    str([x.decode("gbk").encode("utf-8") for x in ret.stdout.readlines()]))

        except Exception as e:
            params["error"] = e.message
        self._return(channel, params)


if __name__ == '__main__':
    if len(sys.argv) == 2:
        os.kill(int(sys.argv[1]), 9)
        time.sleep(1)
    client = VportClient(vport1="/dev/virtio-ports/org.qemu.guest_agent.0",
                         vport2="/dev/virtio-ports/org.qemu.guest_agent.1")
