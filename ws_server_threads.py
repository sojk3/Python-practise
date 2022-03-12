import base64
from hashlib import sha1
import json
import socket
import struct
from sys import argv
import threading
from time import sleep


class WebSocket:
    def __init__(self, ip='192.168.1.20', port=8080):
        self.ip = ip
        self.port = port        
        self.soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.SOL_TCP)
        self.soc.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
        self.soc.bind((ip, port))
        self.soc.setblocking(True)
        self.soc.listen(4)        
        self.rooms = []
        self.time = 0.0
        self.soc_pool = []
        self.th_pool = []
        print(f'Listening on {ip}:{port}.')

    def handshake(self, cli:socket) -> None:
        header = str(cli.recv(512), 'utf-8')
        key_pos = header.find('Sec-WebSocket-Key: ')
        key = header[key_pos+19:key_pos+43]    
        sha1_ws = sha1(f"{key}258EAFA5-E914-47DA-95CA-C5AB0DC85B11".encode('utf-8')).digest()
        key = str(base64.b64encode(sha1_ws), 'utf-8')
        response = bytes(f"HTTP/1.1 101 Web Socket Protocol Handshake\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nWebSocket-Location: ws://{self.ip}:{self.port}\r\nSec-WebSocket-Accept: {key}\r\n\r\n", 'utf-8')
        cli.send(response)        

    def mask(self, text: bytes) -> bytes:
        length = len(text)
        if length <= 125:
            header = struct.pack('BB', 129, length) # php CC
        elif length > 125 and length < 65536:
            header = struct.pack('BBH', 129, 126, length) # CCn
        elif(length >= 65536):
            header = struct.pack('BBLL', 129, 127, length) # CCNN 
        return header + text

    def unmask(self, text: bytes) -> str:
        length = text[1] # python > 3.6
        if length == 126:
            masks = text[4:8]
            data  = text[8:]
        elif length == 127:
            masks = text[10:14]
            data  = text[14:]
        else:
            masks = text[2:6]
            data  = text[6:]
        sz = range(len(data))        
        return ''.join(chr(data[i] ^ masks[i%4]) for i in sz)
        
    def send(self, buff: str, cli: socket) -> None:        
        buff = self.mask(bytes(buff, 'utf-8'))
        cli.send(buff)
    
    def read(self, buff: bytes) -> str:    
        return self.unmask(buff)

    def cmd(self, buff):
        pass

    def client(self, cli: socket):
        self.handshake(cli)
        port = cli.getpeername()[1]
        running = True        
        for soc in self.soc_pool:
            if soc != cli:
                self.send(json.dumps({"from":"root","type":"notify","online":port}), soc)
        print(f'[{port}] Online.')
        
        while running:
            buff = cli.recv(4096)
            buff_sz = len(buff)
            if buff_sz == 6 or buff_sz < 1:
                for soc in self.soc_pool:
                    if soc != cli:
                        self.send(json.dumps({"from":"root","type":"notify","offline":port}), soc)
                cli.close()                
                self.soc_pool.remove(cli)
                print(f'[{port}] Offline.')
                running = False
                continue
            try:
                buff = json.loads(json.loads(self.unmask(buff)))
                print(buff)
                if buff['type'] != 'cmd':
                    buff = json.dumps({'from':port, 'to':0, 'type':buff['type'], 'data':buff['data']})                
                
                else:
                    pass
                
                for soc in self.soc_pool:
                    if soc != cli:
                        self.send(buff, soc)
            except json.JSONDecodeError:
                self.send(json.dumps({'from':'root', 'type':'notify', 'text':'json_error'}), cli)
        
    def run(self):
        self.running = True
        while self.running:
            cli, addr = self.soc.accept()
            client = threading.Thread(target=self.client, args=(cli,))            
            self.soc_pool.append(cli)
            client.start()
            sleep(0.010)

ws = 0
if argv.__len__() == 1:
    ws = WebSocket()
else:
    ws = WebSocket(argv[1], int(argv[2]))
ws.run()
