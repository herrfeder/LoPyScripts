import socket
import struct
from network import LoRa
import os
import time
import math
# A basic package header, B: 1 byte for the deviceId, B: 1 byte for the pkg size, %ds: Formated string for string
_LORA_PKG_FORMAT = "!BB%ds"
# A basic ack package, B: 1 byte for the deviceId, B: 1 bytes for the pkg size, B: 1 byte for the Ok (200) or error messages
_LORA_PKG_ACK_FORMAT = "BBB"

DEBUG = 1
pkg_length = {1:20,2:40,3:60}
bandwith = {1:LoRa.BW_125KHZ,2:LoRa.BW_250KHZ,3:LoRa.BW_500KHZ}

class NanoNode(object):

    def __init__(self,device_id, cmd="",mode="rx",basemode="",pingpong="",bandw=2,sf=8):

        self.basemode = ""
        self.mode = ""

        if pingpong=="A":
            self.pingpong = "A"
        if pingpong=="B":
            self.pingpong = "B"

        if basemode == "orx":
            self.basemode= "orx"
            self.mode = "rx"
        elif basemode == "otx":
            self.basemode= "otx"
            self.mode = "tx"
        elif basemode == "":
            if mode == "rx":
                self.mode = "rx"
            elif mode == "tx":
                self.mode = "tx"

        self.bandwith = bandwith[bandw] 
        self.pkg_len = pkg_length[bandw]
        self.sf = sf


        self.last_recv_buffer =  []
        self.last_device_id = ""

        self.to_send_buffer = []

        self.device_id = device_id
        self.cmd_chain = []
        if cmd:
            self.cmd_chain.append(cmd)

    def ping_pong(self):
        
        lora = LoRa(mode=LoRa.LORA, frequency=863000000)
        s = socket.socket(socket.AF_LORA, socket.SOCK_RAW)
        s.setblocking(False)

        if self.pingpong == "A":


            while True:
                if s.recv(64) == b'Ping':
                    print("Ping")
                    s.send('Pong')
                    time.sleep(5)

        if self.pingpong == "B":
            while True:
                s.send('Ping')
                time.sleep(5)


    def set_up_rx(self):

        self.lora = LoRa (  mode = LoRa.LORA,
                            #frequency = 868100000, 
                            power_mode = LoRa.ALWAYS_ON, 
                            tx_power = 14, 
                            bandwidth = self.bandwith,
                            sf = self.sf) 
                            #preamble = 8, 
                            #coding_rate = LoRa.CODING_4_8)

        self.loso = socket.socket(socket.AF_LORA, socket.SOCK_RAW)
        self.loso.setblocking(False)
        self.pdeb("Setted up RX")
        time.sleep(3)
    def set_up_tx(self):

        self.lora = LoRa (  mode = LoRa.LORA,
                            #frequency = 868100000, 
                            power_mode = LoRa.ALWAYS_ON, 
                            tx_power = 14,
                            bandwidth = self.bandwith,
                            sf = self.sf)
                            #preamble = 8, 
                            #coding_rate = LoRa.CODING_4_8)

        self.loso = socket.socket(socket.AF_LORA, socket.SOCK_RAW)
        self.loso.setblocking(False)
        self.pdeb("Setted up TX")
        time.sleep(3)

    def pdeb(self,message):
        if DEBUG == 1:
            print("%s DEBUG: %s"%(self.mode,message))

    def run(self):


        while(True):
            if self.mode == "rx":
                self.receive_mode()
            if self.mode == "tx":
                self.transmit_mode()

    def receive_mode(self):
                msg = ""
                self.set_up_rx()
                while(True):
                    result = self.receive()
                    if result == 2:
                        msg += self.msg
                        self.send("ack",self.cb_output_payload)
                        time.sleep(1)
                    if result == 1:
                        msg += self.msg
                        self.out_msg(msg,self.last_device_id)
                        self.send("ack",self.cb_output_payload)
                        time.sleep(1)
                        self.mode = "tx"
                        time.sleep(1)
                        break

    def out_msg(self,msg,device_id):
        print("### DEVICE %d ###"%(device_id))
        for line in msg.split("\n"):
            print("%s"%(line))
        print("### END ###")
        


    def transmit_mode(self):
                self.set_up_tx()
                cmd = []
                if self.basemode == "otx":
                    cmd.append(input("Give cmd to execute:"))
                while(True): 
                    to_send = ""
                    if len(self.to_send_buffer)>0:
                        to_send = self.to_send_buffer.pop(0)
                        self.pdeb("There is something in the send_buffer")
                    elif cmd:
                        to_send = cmd.pop()
                    elif len(self.cmd_chain)>0:
                        to_send = self.cmd_chain.pop()
                        self.pdeb("There is something in the commandchain")

                    if to_send:
                        self.send(to_send,self.cb_output_payload)
                        print("sent:")
                        print(to_send)
                        waiting_answ = True
                        while(waiting_answ):
                            recv_msg = self.loso.recv(256)
                            if (len(recv_msg) > 0):

                                device_id, pkg_len, ack = struct.unpack(_LORA_PKG_ACK_FORMAT, recv_msg) 
                                
                                #last_recv_len = recv_msg[1]
                                #device_id, pkg_len, msg = struct.unpack(_LORA_PKG_FORMAT % last_recv_len, recv_msg)

                                if (device_id == self.device_id):
                                    if (ack == 200):
                                        waiting_answ = False
                                        # If the uart = machine.UART(0, 115200) and os.dupterm(uart) are set in the boot.py this print should appear in the serial port
                                        self.pdeb("Got ACK")
                                    else:
                                        waiting_answ = False
                                        # If the uart = machine.UART(0, 115200) and os.dupterm(uart) are set in the boot.py this print should appear in the serial port
                                        print("Message Failed")
                    else:
                        self.mode = "rx"
                        break


    def create_packets(self,msg):
        pkt_list = []

        for i in range(0,int(math.ceil(len(msg)/self.pkg_len))+1):

            if not (((i+1)*self.pkg_len) > len(msg)):
                print(i*self.pkg_len)
                print((i+1)*self.pkg_len)
                pkt = msg[(i*self.pkg_len):(i+1)*self.pkg_len]
                pkt += "_part_"
                pkt_list.append(pkt)
            else:
                pkt = msg[(i*self.pkg_len):-1]
                pkt += "_fini_"
                pkt_list.append(pkt)
                return pkt_list

        
    def interpret_cmd(self,msg,cb=""):
        output = ""
        if msg == b'ls':
            dirs = os.listdir()
            dirs = '\n'.join(dirs)
            output = dirs
        if output != "":
            output = self.create_packets(output)
            self.to_send_buffer.extend(output)

        if cb != "":
            cb(output,self.cb_output_payload)

    def send(self, msg="", cb=""):
        if cb != "":
            self.loso.send(cb(msg))
        else:
            self.loso.send(msg)
        if msg == "ack":
            self.pdeb("finished ACK")
        else:
            self.pdeb("finished sending")


    def cb_output_payload(self,msg):

        if msg == "ack":
            pkg = struct.pack(_LORA_PKG_ACK_FORMAT, self.last_device_id, 1, 200)
        else:
            pkg = struct.pack(_LORA_PKG_FORMAT % len(msg), self.device_id,len(msg),msg)
        return pkg

    def cb_send_i2c(self, cb=""):
        pass

    # need second receive function for partial receiving of bigger data chunks

    def receive(self):
        last_recv = self.loso.recv(200)
        if (len(last_recv) > 2):
            last_recv_len = last_recv[1]
            self.last_device_id, pkg_len, self.msg = struct.unpack(_LORA_PKG_FORMAT % last_recv_len, last_recv)
            self.interpret_cmd(self.msg)
            self.msg = self.msg.decode("UTF-8")
            if self.msg.endswith("_part_"):
                self.msg = str(self.msg).replace("_part_","")
                return 2
            else:
                self.msg = str(self.msg).replace("_fini_","")
                return 1


