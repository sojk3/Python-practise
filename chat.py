import gzip
from sys import argv
import sounddevice as sd
import socket


sd.default.channels = 2
sd.default.samplerate = 44100
sd.default.dtype = 'int16'
sd.default.latency = ('low', 'low')
IP, PORT = "192.168.1.20", 8080
soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.SOL_TCP)
cli, addr = (0, 0)
soc.setblocking(True)
stream_obj = None

def comm_callback(indata, outdata, frame, time, status):
    try:
        if argv[1] == '1':
            cli.send(gzip.compress(indata, 9))
            buff = cli.recv(4096)
            outdata [:]= gzip.decompress(buff)            
        else:
            buff = cli.recv(4096)
            outdata [:]= gzip.decompress(buff)
            cli.send(gzip.compress(indata, 9))
    except ConnectionResetError:
        print(f"Client offline.")
        stream_obj.close()
        return

def init():
    with sd.RawStream(callback=comm_callback) as stream:
        global stream_obj
        stream_obj = stream
        while stream.active:
            sd.sleep(10)            

if len(argv) == 4:
    IP = argv[2]
    PORT = int(argv[3])
    if argv[1] == '1':   
        soc.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
        soc.bind((IP, PORT))
        soc.listen(1)
        print(f'Listening -> {IP}:{PORT}')
        cli, addr = soc.accept()       
        print(f'Client connected -> [{addr[1]}]')
            
    if argv[1] == '0':        
        soc.connect((IP, PORT))
        cli = soc
        print(f'Connected -> {IP}:{PORT}')

    init()

else:
    print('Usage: chat.py [1-server, 2-client] ip port.')
