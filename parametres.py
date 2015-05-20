#!/usr/bin/python

# GPIO capteur ultrason avant
GPIO_TRIGGER = 23
GPIO_ECHO = 24

# Delais entre 2 mesure d'un capteur ultrason
DELAY_MESURE = 0.05

# Delais entre 2 commandes de la PO
DELAY_CMD_PO = 0.01

# Identifiants servoblaster
DEV_DIRECTION = 'P1-12'     # Servo-moteur de direction
DEV_VITESSE = 'P1-11'       # Variateur de vitesse

# Adresse IP d'ecoute du serveur TCP
BIND_IP = 192.168.1.95
# Port d'ecoute du serveur TCP
CLIENT_TCP_PORT = 10200
# Taille du buffer de reception TCP
CLIENT_TCP_BUFFER_SIZE = 1024
