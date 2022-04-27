import socket
from sys import argv
import threading
from time import sleep
import cv2 as cv
import sounddevice as sd
import gzip
import numpy as np


addr = ('192.168.1.20', 8080)
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

run = True
sd.default.samplerate = 44100
sd.default.channels = 2
sd.default.latency = ('low', 'low')
sd.default.dtype = "int16"
sd.default.blocksize = 576
stream = cv.VideoCapture(0)
stream_lock = False
i_fps = 0
_, l_v_frame = stream.read()
_, l_v_frame = cv.imencode('.jpg', l_v_frame)
l_a_frame = ()
r_v_frame = l_v_frame
r_a_frame = ()
network_dspee = {'v': 0, 'a': 0}

def stream_send():
    global run, network_dspee
    while len(l_a_frame) == 0:
        sleep(0.5)

    while run:
        try:
            v_buff    = bytes(l_v_frame)
            a_buff    = bytes(l_a_frame)
            v_buff_sz = len(v_buff)
            a_buff_sz = len(a_buff)
            header    = f'{v_buff_sz};{a_buff_sz};'
            header    = bytes(f'{header}{(24 - len(header))*"!"}', 'ascii')
            sock.sendall(header)
            sock.sendall(v_buff)
            sock.sendall(a_buff)
            network_dspee['v']+= v_buff_sz
            network_dspee['a']+= a_buff_sz            
        except ConnectionAbortedError:
            run = False
        except ConnectionResetError:
            run = False
        sleep(0.100)

def stream_recv():
    global run, r_v_frame, r_a_frame
    while run:
        try:
            buff       = sock.recv(24, socket.MSG_WAITALL)
            offset     = buff.split(b';')
            offset_v   = int(offset[0])
            buff       = sock.recv(offset_v, socket.MSG_WAITALL)
            buff       = np.ndarray(shape=(1, offset_v), dtype=np.uint8, buffer=buff)
            r_v_frame  = cv.imdecode(buff, cv.IMREAD_UNCHANGED)
            
            offset_a   = int(offset[1])
            buff       = sock.recv(offset_a, socket.MSG_WAITALL)
            buff       = gzip.decompress(buff)
            r_a_frame  = np.ndarray(shape=(576, 2), dtype=np.uint8, buffer=buff)
        except ConnectionAbortedError:
            run = False
        except ConnectionResetError:
            run = False
        sleep(0.100)

def stream_video():
    global run, i_fps, l_v_frame
    cv.namedWindow('send')

    while run and stream.isOpened():    
        ret, frame = stream.read()
        if ret == False:
            continue
        ret, frame = cv.imencode('.jpg', frame, [cv.IMWRITE_JPEG_QUALITY, 80])
        if ret == False:
            continue
        l_v_frame = frame
        i_fps += 1
        cv.imshow('send', r_v_frame)

        if cv.waitKey(10) & 0xFF == ord('q'):
            run = False

    stream.release()
    cv.destroyAllWindows()

def callback_audio(indata, outdata, frame, status, time):    
    global l_a_frame
    l_a_frame = gzip.compress(indata, 7)
    #outdata[:]= r_a_frame

def stream_audio():
    with sd.Stream(callback=callback_audio) as stream:
        while run and stream.active:
            sleep(0.010)

def fps():
    global i_fps, network_dspee
    while run:
        v_speed = int(network_dspee['v']/1024)
        a_speed = int(network_dspee['a']/1024)
        print(f'FPS: {i_fps} | Net: (V: {v_speed}kB/s, A: {a_speed}kB/s)')
        i_fps = 0
        network_dspee['a'] = 0
        network_dspee['v'] = 0
        sleep(1)

th_video    = threading.Thread(target=stream_video)
th_audio    = threading.Thread(target=stream_audio)
th_net_recv = threading.Thread(target=stream_recv)
th_net_send = threading.Thread(target=stream_send)
th_fps      = threading.Thread(target=fps)

def run(mode = 1, ip='192.168.1.20', port=8080):
    global sock, addr
    addr = (ip, port)
    try:            
        if mode == 1:
            sock.bind(addr)
            sock.listen(4)
            client, _ = sock.accept()
            sock = client
        elif mode == 0:
            sock.connect(addr)
    except ConnectionRefusedError:
        print('Error in connection.')
        exit(0)
    
    th_audio.start()
    th_video.start()
    th_net_send.start()
    th_net_recv.start()
    th_fps.start()
    th_video.join()
    th_audio.join()
    th_net_send.join()
    th_net_recv.join()
    th_fps.join()

if len(argv) != 4:
    print(f'Usage: {argv[0]} [mode 1-server or 0-client] ip port')
    exit(0)

mode = int(argv[1])
ip   = argv[2]
port = int(argv[3])
run(mode, ip, port)
