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

# Importation des parametres du programme
from parametres import *

# Variables globales
threads = []
serveur_sock = None
g_distance_avant = 0
g_distance_arriere = 50
g_vitesse = 50
g_direction = 50
g_vitesse_max = 10
g_distance_securite = 60
flag_update_PO = 0

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

        stop = 0
        start = 0

        timeout = time.time() + 1
        while GPIO.input(GPIO_ECHO_CPT_AV) == 0 and time.time() < timeout:
            start = time.time()
            time.sleep(0.0001)

        timeout = time.time() + 1
        while GPIO.input(GPIO_ECHO_CPT_AV) == 1 and time.time() < timeout:
            stop = time.time()
            time.sleep(0.0001)

        elapsed = stop - start
        distance = (elapsed * 34000) / 2
        if (distance < 0):
            distance = 0
        g_distance_avant = int(round(distance))

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

        stop = 0
        start = 0

        timeout = time.time() + 1
        while GPIO.input(GPIO_ECHO_CPT_AR) == 0 and time.time() < timeout:
            start = time.time()
            time.sleep(0.0001)

        timeout = time.time() + 1
        while GPIO.input(GPIO_ECHO_CPT_AR) == 1 and time.time() < timeout:
            stop = time.time()
            time.sleep(0.0001)
        elapsed = stop - start
        distance = (elapsed * 34000) / 2
        if (distance < 0):
            distance = 0
        g_distance_arriere = int(round(distance))


# Gestion de reception des commandes du client TCP
class thread_client_tcp_recept(threading.Thread):

    def __init__(self, threadID, client_tcp):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.kill_received = False
        self.client_tcp = client_tcp
        print_infos(1, "Connexion client")

    def run(self):
        while not self.kill_received:
            self.reception_client_tcp()
        self.clean_client_tcp()

    def clean_client_tcp(self):
        self.client_tcp.close()
        print_infos(2, "Fermeture socket")

    def reception_client_tcp(self):
        global g_vitesse
        global g_direction
        global g_distance_securite
        global g_vitesse_max
        global flag_update_PO

        try:
            self.data = self.client_tcp.recv(1024)

            self.data_lines = self.data.split('\n')

            for self.line in self.data_lines:

                if (self.line != ''):

                    try:
                        self.decoded = json.loads(self.line)

                        if ('commande' in self.decoded): # Commande PO
                            try:
                                g_vitesse = self.decoded['commande']['vitesse']
                                g_direction = self.decoded['commande']['direction']
                                flag_update_PO = 1
                                # print(datetime.datetime.strftime(datetime.datetime.now(), '%H:%M:%S:%f') + " - Vitesse : " + str(g_vitesse) + " - Direction : " + str(g_direction) )
                                break
                            except KeyError:
                                print_infos(3, "Erreur decodage JSON commande")

                        elif ('configuration' in self.decoded): # Configuration parametres
                            try:
                                g_distance_securite = self.decoded['configuration']['distance_arret']
                                g_vitesse_max = self.decoded['configuration']['vitesse_max']
                                sv_cfg_security_distance(g_distance_securite)
                                sv_cfg_max_speed(g_vitesse_max)
                                print_infos(2, "Mise a jour configuration : \nDistance d'arret : " + str(g_distance_securite) + " \nVitesse max : " + str(g_vitesse_max) )
                            except KeyError:
                                print_infos(3, "Erreur decodage JSON configuration")

                        elif ('heartbit' in self.decoded): # Hearthbit
                            try:
                                # print_infos(2, self.decoded['heartbit'])
                                pass
                            except KeyError:
                                print_infos(3, "Erreur decodage JSON commande")

                    except ValueError:
                        print_infos(3, "Erreur parse JSON : " + self.data)

        except socket.timeout:
            print_infos(3, "Timeout reception client tcp")
            arret_voiture()
            self.kill_received = 1

        except:
            print_infos(3, "Perte de connexion client tcp")
            self.kill_received = 1

# Gestion de l'envoi des informations au client TCP
class thread_client_tcp_info(threading.Thread):

    def __init__(self, threadID, client_tcp):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.kill_received = False
        self.client_tcp = client_tcp
        print_infos(1, "Connexion client")

    def run(self):
        while not self.kill_received:
            self.envoi_infos_client_tcp()
            time.sleep(DELAY_ENVOI_INFOS)

    def envoi_infos_client_tcp(self):
        global g_distance_avant
        global g_distance_arriere
        global g_vitesse
        try:
            self.infos = "{\"informations\":{\"distance_avant\":" + str(g_distance_avant) + ",\"distance_arriere\":" + str(g_distance_arriere) + "}}\n"
            self.client_tcp.send(self.infos)
        except:
            print_infos(3, "Erreur envoi infos client tcp")
            arret_voiture()
            self.kill_received = 1


# Gestion de la partie operative
class thread_commande_PO(threading.Thread):

    def __init__(self, threadID):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.kill_received = False
        print_infos(1, "Demarrage gestion commande PO")

    def run(self):
        global flag_update_PO

        while not self.kill_received:
            if (flag_update_PO == 1):
                self.gestion_PO()
                time.sleep(0.0001)
                flag_update_PO = 0
            else:
                time.sleep(0.0001)
        print_infos(1, "Arret commande PO")

    def gestion_PO(self):

        # Gestion de la vitesse
        if (g_vitesse > 50 and g_distance_avant <= g_distance_securite) or (g_vitesse < 50 and g_distance_arriere <= g_distance_securite):
            # Detection obstacle avant ou arriere : arret
            if (g_distance_avant <= g_distance_securite):
                print_infos(2, "Obstacle detecte : Capteur avant = " + str(g_distance_avant))
            elif (g_distance_arriere <= g_distance_securite):
                print_infos(2, "Obstacle detecte : Capteur arriere = " + str(g_distance_arriere))
            self.vitesse_to_write = DEV_VITESSE + '=50%'
        else:
            # Calcul des vitesses max marche avant / arriere
            self.vitesse_max_ar = 50 - (g_vitesse_max / 2)
            self.vitesse_max_av = (g_vitesse_max / 2) + 50

            # Marche avant bridee
            if (g_vitesse > self.vitesse_max_av):
                self.vitesse_to_write = DEV_VITESSE + '=' + str(self.vitesse_max_av) + '%'
            # Marche arriere bridee
            elif (g_vitesse < self.vitesse_max_ar):
                self.vitesse_to_write = DEV_VITESSE + '=' + str(self.vitesse_max_ar) + '%'
            # Fonctionnement normal
            else:
                self.vitesse_to_write = DEV_VITESSE + '=' + str(g_vitesse) + '%'


        # Gestion de la direction
        self.direction_to_write = DEV_DIRECTION + '=' + str(g_direction) + '%'

        # print_infos(2, "Direction : " + self.direction_to_write + " Vitesse : " + self.vitesse_to_write)

        # Commande de la vitesse
        self.dev = open("/dev/servoblaster", "w")
        self.dev.write(self.vitesse_to_write + "\n")
        self.dev.close()

        # Commande de la direction
        self.dev = open("/dev/servoblaster", "w")
        self.dev.write(self.direction_to_write + "\n")
        self.dev.close()

        time.sleep(DELAY_CMD_PO)

# Configuration d'un capteur ultrason HC-SR04
def configure_ultrason(GPIO_TRIGGER, GPIO_ECHO):
    print_infos(2, "Configuration ultrason")

    # Configuration des PIN du raspberry
    GPIO.setup(GPIO_TRIGGER,GPIO.OUT)  # PIN Trigger
    GPIO.setup(GPIO_ECHO,GPIO.IN)      # PIN Echo
    GPIO.output(GPIO_TRIGGER, False)
    time.sleep(0.5)

# Suppression configuration GPIO des capteurs
def clean_ultrason():
    print_infos(1, "Arret mesures capteur ultrason")

# Gestion de l'arret du programme principal et des threads
def kill():
    print("")
    print_infos(1, "Arret du programme serveur")
    stop_servoblaster()
    # Fermeture du socket TCP
    serveur_sock.close()
    # Arret de l'ensemble des threads
    for t in threads:
        t.kill_received = True
    GPIO.cleanup()
    # Arret du programme principal
    sys.exit(0)

def arret_voiture():
    global g_vitesse
    g_vitesse = 50

# Demarrage du programme de gestion du servo-moteur et du variateur de vitesse
def launch_servoblaster():
    print_infos(1, "Demarrage de servoblaster")
    cmd = "servod --min=" + str(MIN_US_SB) + "us --max=" + str(MAX_US_SB)
    cmd += "us --p1pins=" + str(GPIO_DIRECTION) + "," + str(GPIO_VITESSE)
    args = shlex.split(cmd)
    print( subprocess.call(args) )

def stop_servoblaster():
    print_infos(1, "Arret de servoblaster")
    cmd = "kill $(pidof servod)"
    os.system(cmd)

# Enregistrement de la modification du parametre de distance de securite
def sv_cfg_security_distance(val_to_save):

    try:
        # Lecture du fichier de configuration
        cfg_file = open("cfg.json", "r")
        data = json.load(cfg_file)
        cfg_file.close()

        # Mise a jour du parametre de distance de securite
        data["configuration"]["distance_max"] = val_to_save

        # Sauvegarde de la modification
        cfg_file = open("cfg.json", "w")
        json.dump(data, cfg_file)
        cfg_file.close()
    except:
        print_infos(3, "Erreur lors de l'ouverture du fichier de configuration")

# Enregistrement de la modification du parametre de vitesse max
def sv_cfg_max_speed(val_to_save):

    try:
        # Lecture du fichier de configuration
        cfg_file = open("cfg.json", "r")
        data = json.load(cfg_file)
        cfg_file.close()

        # Mise a jour du parametre de distance de securite
        data["configuration"]["vitesse_max"] = val_to_save

        # Sauvegarde de la modification
        cfg_file = open("cfg.json", "w")
        json.dump(data, cfg_file)
        cfg_file.close()
    except:
        print_infos(3, "Erreur lors de l'ouverture du fichier de configuration")

# Affichage debug
def print_infos(level, msg):

    if (level == 1):
        print("**** " + msg + " ****")
    elif (level == 2):
        print("-> " + msg)
    elif (level == 3):
        print("-> !! " + msg + " !!")

# Chargement de la configuration du systeme
def load_config():

    global g_vitesse_max
    global g_distance_max

    try:
        print_infos(1, "Chargement des parametres")
        # Lecture du fichier de configuration
        cfg_file = open("cfg.json", "r")
        data = json.load(cfg_file)
        cfg_file.close()

        # Mise a jour des parametres
        g_vitesse_max = data["configuration"]["vitesse_max"]
        g_distance_max = data["configuration"]["distance_max"]

        print_infos(2, "Parametres du systeme :\n-Vitesse max : " + str(g_vitesse_max) + "\n-Distance max : " + str(g_distance_max))

    except:
        print_infos(3, "Erreur lors de l'ouverture du fichier de configuration")

# Gestion du signal kill pour terminer le programme et les threads
def signal_kill(signal, frame):
    kill()

def signal_init_done():
    global g_direction
    global flag_update_PO

    flag_update_PO = 1

    for x in range(50, 100, 5):
        g_direction = x
        time.sleep(0.02)
    for x in range(100, 0, -5):
        g_direction = x
        time.sleep(0.02)
    for x in range(0, 50, 5):
        g_direction = x
        time.sleep(0.02)

    flag_update_PO = 0

def main():
    try:
        global serveur_sock

        signal.signal(signal.SIGTERM, signal_kill)

        # Chargement de la configuration
        load_config()

        # Demarrage du programme servoblaster
        launch_servoblaster()

        # Configuration du socket pour le client TCP
        serveur_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        serveur_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # Mise en ecoute du serveur TCP
        serveur_sock.bind((BIND_IP, CLIENT_TCP_PORT))
        serveur_sock.listen(1)

        # Thread capteur ultrason avant
        thread_1 = thread_ultrason_av(1)
        thread_1.start()
        threads.append(thread_1)

        # Thread capteur ultrason arriere
        thread_2 = thread_ultrason_ar(2)
        thread_2.start()
        threads.append(thread_2)

        # Thread de gestion de la partie operative
        thread_3 = thread_commande_PO(3)
        thread_3.start()
        threads.append(thread_3)

        signal_init_done()

        while(1):
            # Attente du client TCP
            (client_tcp, addr) = serveur_sock.accept()
            client_tcp.settimeout(TIMEOUT_CLIENT_TCP)

            # Thread pour la gestion de reception des commandes du client TCP
            thread_4 = thread_client_tcp_recept(4, client_tcp)
            thread_4.start()
            threads.append(thread_4)

            # Thread pour la gestion de l'envoi des informations au client TCP
            thread_5 = thread_client_tcp_info(5, client_tcp)
            thread_5.start()
            threads.append(thread_5)

    except KeyboardInterrupt:
        kill()

    # Gestion des erreurs
    except Exception as e:
        print_infos(e.message, e.args)
        kill()

if __name__ == "__main__":
    main()
