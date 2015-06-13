#!/usr/bin/python

import time
import datetime
import threading
import subprocess
import shlex
import json
import sys
import socket
import signal
import serial
import os
import RPi.GPIO as GPIO

# GPIO capteur ultrason avant
GPIO_TRIGGER_CPT_AV = 11 # (GPIO11 - PIN)
GPIO_ECHO_CPT_AV = 8 # (GPIO8 - PIN)

# GPIO capteur ultrason arriere
GPIO_TRIGGER_CPT_AR = 22 # (GPIO22 - PIN15)
GPIO_ECHO_CPT_AR = 27 # (GPIO27 - PIN13)

# Delais entre 2 mesure d'un capteur ultrason
DELAY_MESURE = 0.05

threads = []

# Configuration en mode BCM pour les references GPIO
GPIO.setmode(GPIO.BCM)

# Gestion capteur ultrason HC-SR04 avant
class thread_ultrason_av(threading.Thread):

    def __init__(self, threadID):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.kill_received = False
        configure_ultrason(GPIO_TRIGGER_CPT_AV, GPIO_ECHO_CPT_AV)

    def run(self):
        print_infos(1, "Demarrage des mesures capteur ultrason avant")
        while not self.kill_received:
            self.mesure_ultrason()
            time.sleep(DELAY_MESURE)

        clean_ultrason()

    def mesure_ultrason(self):
        global g_distance_avant

        # Envoi d'un niveau haut de 10us pour le trigger
        GPIO.output(GPIO_TRIGGER_CPT_AV, True)
        time.sleep(0.00001)
        GPIO.output(GPIO_TRIGGER_CPT_AV, False)
        start = time.time()

        while GPIO.input(GPIO_ECHO_CPT_AV) == 0:
            start = time.time()
            time.sleep(0.0001)

        while GPIO.input(GPIO_ECHO_CPT_AV) == 1:
            stop = time.time()
            time.sleep(0.0001)

        elapsed = stop - start
        distance = (elapsed * 34000) / 2
        g_distance_avant = int(round(distance))
        print("Distance avant : " + str(g_distance_avant))


# Gestion capteur ultrason HC-SR04 arriere
class thread_ultrason_ar(threading.Thread):

    def __init__(self, threadID):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.kill_received = False
        configure_ultrason(GPIO_TRIGGER_CPT_AR, GPIO_ECHO_CPT_AR)

    def run(self):
        print_infos(1, "Demarrage des mesures capteur ultrason arriere")
        while not self.kill_received:
            self.mesure_ultrason()
            time.sleep(DELAY_MESURE)

        clean_ultrason()

    def mesure_ultrason(self):
        global g_distance_arriere

        # Envoi d'un niveau haut de 10ms pour le trigger
        GPIO.output(GPIO_TRIGGER_CPT_AR, True)
        time.sleep(0.00001)
        GPIO.output(GPIO_TRIGGER_CPT_AR, False)
        start = time.time()
        while GPIO.input(GPIO_ECHO_CPT_AR) == 0:
            start = time.time()
            time.sleep(0.0001)
        while GPIO.input(GPIO_ECHO_CPT_AR) == 1:
            stop = time.time()
            time.sleep(0.0001)
        elapsed = stop - start
        distance = (elapsed * 34000) / 2
        g_distance_arriere = int(round(distance))
        print("Distance arriere : " + str(g_distance_arriere))

# Configuration d'un capteur ultrason HC-SR04
def configure_ultrason(GPIO_TRIGGER, GPIO_ECHO):
    print_infos(2, "Configuration ultrason")

    # Configuration des PIN du raspberry
    GPIO.setup(GPIO_TRIGGER,GPIO.OUT)  # PIN Trigger
    GPIO.setup(GPIO_ECHO,GPIO.IN)      # PIN Echo
    GPIO.output(GPIO_TRIGGER, False)
    time.sleep(0.5)

# Affichage debug
def print_infos(level, msg):

    if (level == 1):
        print("**** " + msg + " ****")
    elif (level == 2):
        print("-> " + msg)
    elif (level == 3):
        print("-> !! " + msg + " !!")


# Suppression configuration GPIO des capteurs
def clean_ultrason():
    print_infos(1, "Arret mesures capteur ultrason")

def main():
    try:
        # Thread capteur ultrason avant
        thread_1 = thread_ultrason_av(0)
        thread_1.start()
        threads.append(thread_1)

        # Thread capteur ultrason arriere
        thread_2 = thread_ultrason_ar(1)
        thread_2.start()
        threads.append(thread_2)

        while(1):
            time.sleep(1)

    except KeyboardInterrupt:
        for t in threads:
            t.kill_received = True
        sys.exit(0)

    # Gestion des erreurs
    except Exception as e:
        print_infos(e.message, e.args)
        for t in threads:
            t.kill_received = True
        sys.exit(0)

if __name__ == "__main__":
    main()
