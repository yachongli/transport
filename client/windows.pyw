# encoding=utf8
import sys

reload(sys)
sys.setdefaultencoding('utf8')

import json
import os
import time
import threading
from threading import Thread
import win32file
import os
import platform
import socket
import uuid
import win32event, win32pipe
import pywintypes
import pyperclip
import base64
import subprocess
import shutil
import getpass
import psutil


def reboot_self():
    cmd = sys.executable + " " + '"' + os.path.realpath(sys.argv[0]) + '"' + ' ' + str(os.getpid())
    print cmd
    # ret = os.system(cmd)
    subprocess.Popen(cmd)


def confirm_transport(func):
    def _confirm_transport(*args, **kwargs):
        print kwargs
        recive_file = os.path.realpath("\\".join([args[2]['path'], args[2]['name']])).decode("utf-8").encode("gbk")
        print recive_file
        my_file = str(os.path.realpath(sys.argv[0]))
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
                reboot_self()

    return _confirm_transport


class VportClient(object):
    def __init__(self, vport1, vport2):
        self.vport1 = vport1
        self.vport2 = vport2
        # self.on_recie = False
        # self.heat_beat_back = False
        self.start_recv()
        self.version = 1.0
        self.heart_beat()
        self.get_copy()
        win32file.CloseHandle(self.channel2)

    # def start_recv(self):
    #     Thread(self._start_recv()).start()

    def start_recv(self):
        # if os.path.exists(self.vport1):
        self.open_channel1()
        self.open_channel2()

        if self.channel1 and self.channel2:
            self.t1 = Thread(target=self.start_recv1)
            self.t1.start()
        # if self.channel2 and not self.t2:
        #     self.t2 = Thread(target=self.start_recv2)
        #     self.t2.start()

    def open_channel1(self):
        try:
            self.channel1 = win32file.CreateFile(self.vport1,
                                                 win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                                                 0, None,
                                                 win32file.OPEN_ALWAYS, win32file.FILE_FLAG_OVERLAPPED, None)
            self.channel1_over = pywintypes.OVERLAPPED()
            evt = win32event.CreateEvent(None, 1, 0, None)
            self.channel1_over.hEvent = evt
        except Exception as e:
            self.channel1 = None

    def open_channel2(self):
        try:
            self.channel2 = win32file.CreateFile(self.vport2,
                                                 win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                                                 win32file.FILE_SHARE_WRITE, None,
                                                 win32file.OPEN_EXISTING, win32file.FILE_FLAG_OVERLAPPED, None)
            self.channel2_over = pywintypes.OVERLAPPED()
            evt = win32event.CreateEvent(None, 1, 0, None)
            self.channel2_over.hEvent = evt
        except Exception as e:
            if e.winerror == 5:
                self.open_channel2()
            print e.message
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
                hb['dir'] = os.path.split(os.path.realpath(sys.argv[0]).decode("gbk").encode("utf-8"))
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
            full_path = pa.get("path") + "\\" + pa.get("name")
            write_file = open(full_path, "wb")
            print "start_recive"
            print os.path.getsize(full_path) / 1024 / 1024
            threading.Thread(target=self.count_size, kwargs=({"channel": channel, "path": full_path})).start()
            s = 0
            buffer = win32file.AllocateReadBuffer(2048)
            error_count = 0
            while True:
                recv = ""
                try:
                    hr, data = win32file.ReadFile(self.channel2, buffer, self.channel2_over)
                    rc = win32event.WaitForSingleObject(self.channel2_over.hEvent, 1000)
                    if rc != win32event.WAIT_OBJECT_0:
                        error_count += 1
                        print error_count
                        if error_count > 3:
                            break
                        else:
                            time.sleep(0.001)
                            continue
                    size = win32file.GetOverlappedResult(self.channel2, self.channel2_over, 1)
                    recv = data[:size]
                    s += size
                except Exception as e:
                    time.sleep(0.1)
                    pass
                if recv == "51ELAB":
                    break
                else:
                    error_count = 0
                    write_file.write(recv)
                    if s == pa['size']:
                        break
                        # time.sleep(0.00000000001)
            print s
            print "recive end "
            write_file.close()
            win32file.CloseHandle(self.channel2)
        except Exception as e:
            pa['error'] = e.message
            win32file.CloseHandle(self.channel2)
            self._return(self.channel1, pa)

    def save_text_to_file(self, channel, pa):
        try:
            full_path = pa.get("path") + "\\" + pa.get("name")
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
            self._return(channel, params)
            self.open_channel2()
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
                pyperclip.copy(copy.encode("gbk"))
            else:
                pyperclip.copy("")
        except Exception as e:
            params['error'] = e.message
        else:
            params['response'] = "success"
        self._return(channel, params)

    def _return(self, channel, params):
        overlap = pywintypes.OVERLAPPED()
        win32file.WriteFile(channel, json.dumps(params), overlap)

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
        times = 0
        while True:
            try:
                buffer = win32file.AllocateReadBuffer(1024)
                hr, data = win32file.ReadFile(self.channel1, buffer, self.channel1_over)
                size = win32file.GetOverlappedResult(self.channel1, self.channel1_over, 1)
                red = data[:size]
                print red
                red = json.loads(red)
                self.recive_cmd(self.channel1, red)
            except Exception as e:
                print e
                pass
            time.sleep(1)

    def start_recv2(self):
        while True:
            try:
                buffer = win32file.AllocateReadBuffer(1024)
                hr, data = win32file.ReadFile(self.channel2, buffer, self.channel2_over)
                size = win32file.GetOverlappedResult(self.channel1, self.channel1_over, 1)
                red = data[:size]
                red = json.loads(red)
                print red
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
    try:
        if len(sys.argv) == 2:
            os.kill(int(sys.argv[1]), 9)
        time.sleep(1)
        client = VportClient(vport1=r"\\.\Global\org.qemu.guest_agent.0", vport2=r"\\.\Global\org.qemu.guest_agent.1")
    except Exception as e:
        print e
    # client.start_recv1()
