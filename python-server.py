#!/usr/bin/python

import time
import threading
import subprocess
import shlex
import json
import sys
import socket
import signal
import RPi.GPIO as GPIO

# Importation des paramètres du programme
import parametres

# Variables globales
threads = []
p_servoblaster = None
g_distance = 0
g_distance_securite = 30
g_vitesse = 50
g_vitesse_max = 60
g_direction = 50

# Configuration du socket pour le client TCP
serveur_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
serveur_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

# Gestion d'un capteur ultrason HC-SR04
class thread_ultrason(threading.Thread):

    def __init__(self, threadID):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.kill_received = False
        self.configure_ultrason()

    def run(self):
        while not self.kill_received:
            self.mesure_ultrason()
        self.clean_ultrason()

    def configure_ultrason(self):
        # print("Configuration ultrason")
        # Configuration en mode BCM pour les references GPIO
        GPIO.setmode(GPIO.BCM)
        # Configuration des PIN du raspberry
        GPIO.setup(GPIO_TRIGGER,GPIO.OUT)  # PIN Trigger
        GPIO.setup(GPIO_ECHO,GPIO.IN)      # PIN Echo
        GPIO.output(GPIO_TRIGGER, False)
        time.sleep(0.5)

    def mesure_ultrason(self):
        global g_distance
        # Envoi d'un niveau haut de 10ms pour le trigger
        GPIO.output(GPIO_TRIGGER, True)
        time.sleep(0.00001)
        GPIO.output(GPIO_TRIGGER, False)
        start = time.time()
        while GPIO.input(GPIO_ECHO)==0:
            start = time.time()

        while GPIO.input(GPIO_ECHO)==1:
            stop = time.time()
        elapsed = stop - start
        distance = (elapsed * 34000) / 2
        g_distance = int(round(distance))
        time.sleep(DELAY_MESURE)

    def clean_ultrason(self):
        # print("Arret mesures ultrason")
        GPIO.cleanup()

# Gestion d'un client TCP
class thread_client_tcp(threading.Thread):

    def __init__(self, threadID, client_tcp):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.kill_received = False
        self.client_tcp = client_tcp
        # print("Connexion client")

    def run(self):
        while not self.kill_received:
            self.reception_client_tcp()
        self.clean_client_tcp()

    def reception_client_tcp(self):
        global g_vitesse
        global g_direction
        global g_distance_securite
        global g_vitesse_max

        self.data = self.client_tcp.recv(CLIENT_TCP_BUFFER_SIZE)

        try:
            self.decoded = json.loads(self.data)

            if ('commande' in self.decoded): # Commande PO
                try:
                    g_vitesse = self.decoded['commande']['vitesse']
                    g_direction = self.decoded['commande']['direction']
                    # print("Vitesse : " + str(g_vitesse) + " - Direction : " + str(g_direction) )
                except KeyError:
                    print("Erreur decodage JSON commande")

            elif ('configuration' in self.decoded): # Configuration parametres
                try:
                    g_distance_securite = self.decoded['configuration']['distance_arret']
                    g_vitesse_max = self.decoded['configuration']['vitesse_max']
                    sv_cfg_security_distance()
                    sv_cfg_max_speed()
                except KeyError:
                    print("Erreur decodage JSON configuration")

        except ValueError:
            print("Erreur parse JSON")

    def clean_client_tcp(self):
        print("Arret serveur tcp")
        self.client_tcp.close()

# Gestion de la partie operative
class thread_commande_PO(threading.Thread):

    def __init__(self, threadID):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.kill_received = False

    def run(self):
        while not self.kill_received:
            self.gestion_PO()

    def gestion_PO(self):

        if (g_distance > g_distance_securite):
            if (g_vitesse <= g_vitesse_max):
                self.vitesse_to_write = DEV_VITESSE + '=' + str(g_vitesse) + '%'
            else:
                self.vitesse_to_write = g_vitesse_max
        else:
            self.vitesse_to_write = DEV_VITESSE + '=50%'

        self.direction_to_write = DEV_DIRECTION + '=' + str(g_direction) + '%'

        # print("Direction : " + self.direction_to_write)
        # print("Vitesse : " + self.vitesse_to_write)

        self.dev = open("/dev/servoblaster", "w")
        self.dev.write(self.vitesse_to_write + "\n")
        self.dev.close()

        self.dev = open("/dev/servoblaster", "w")
        self.dev.write(self.direction_to_write + "\n")
        self.dev.close()

        time.sleep(DELAY_CMD_PO)

# Gestion de l'arret du programme principal et des threads
def kill():
    # Fermeture du socket TCP
    serveur_sock.close()
    # Arret du programme servoblaster
    p_servoblaster.send_signal(signal.SIGTERM)
    # Arret de l'ensemble des threads
    for t in threads:
        t.kill_received = True
    # Arret du programme principal
    sys.exit(0)

# Demarrage du programme de gestion du servo-moteur et du variateur de vitesse
def launch_servoblaster():
    global p_servoblaster
    cmd = "servod --min=" + str(MIN_US_SB) + "us --max=" + str(MAX_US_SB)
    cmd += "us --p1pins=" + str(GPIO_DIRECTION) + "," + str(GPIO_VITESSE)
    args = shlex.split(cmd)
    p_servoblaster = subprocess.Popen(args)

# Enregistrement de la modification du parametre de distance de securite
def sv_cfg_security_distance():
    global g_distance_max

    # Lecture du fichier de configuration
    cfg_file = open("cfg.json", "r")
    data = json.load(cfg_file)
    cfg_file.close()

    # Mise a jour du parametre de distance de securite
    data["configuration"]["distance_max"] = g_distance_max

    # Sauvegarde de la modification
    cfg_file = open("cfg.json", "w")
    json.dump(data, cfg_file)
    cfg_file.close()

# Enregistrement de la modification du parametre de vitesse max
def sv_cfg_max_speed():
    global g_vitesse_max

    # Lecture du fichier de configuration
    cfg_file = open("cfg.json", "r")
    data = json.load(cfg_file)
    cfg_file.close()

    # Mise a jour du parametre de distance de securite
    data["configuration"]["vitesse_max"] = g_vitesse_max

    # Sauvegarde de la modification
    cfg_file = open("cfg.json", "w")
    json.dump(data, cfg_file)
    cfg_file.close()

# Gestion du signal kill pour terminer le programme et les threads
def signal_kill(signal, frame):
    print "Arret du programme"
    kill()

def main():
    try:
        signal.signal(signal.SIGTERM, signal_kill)

        # Demarrage du programme servoblaster
        launch_servoblaster()

        # Mise en ecoute du serveur TCP
        serveur_sock.bind((BIND_IP, CLIENT_TCP_PORT))
        serveur_sock.listen(1)

        # Thread capteur ultrason avant
        thread_1 = thread_ultrason(1)
        thread_1.start()
        threads.append(thread_1)

        # Thread de gestion de la partie operative
        thread_2 = thread_commande_PO(2)
        thread_2.start()
        threads.append(thread_2)

        while(1):
            # Thread pour la gestion d'un client TCP
            (client_tcp, addr) = serveur_sock.accept()
            thread_3 = thread_client_tcp(3, client_tcp)
            thread_3.start()
            threads.append(thread_3)

    except KeyboardInterrupt:
        print "Ctrl-c : Arret du programme"
        kill()

    # Gestion des erreurs
    except Exception as e:
        print(e.message, e.args)
        kill()

if __name__ == "__main__":
    main()
