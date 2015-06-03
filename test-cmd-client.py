#!/usr/bin/env python

import socket
import time

TCP_IP = '192.168.1.1'
TCP_PORT = 10200
BUFFER_SIZE = 1024
MESSAGE = "{\"commande\":{\"direction\":50,\"vitesse\":50}}\n"

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect((TCP_IP, TCP_PORT))

while(1):
    s.send(MESSAGE)
    time.sleep(0.05)
s.close()
