"""Enregistre tes identifiants GENICIA++ dans le Gestionnaire d'identifiants Windows.

Ils ne sont écrits dans aucun fichier : les scripts les relisent depuis Windows.
Le mot de passe ne s'affiche pas pendant la saisie (c'est normal).

Lancement (une seule fois) :  python enregistrer_identifiants.py
"""
import getpass

import keyring

SERVICE = "GENICIA++"

identifiant = input("Identifiant GENICIA++ : ").strip()
mot_de_passe = getpass.getpass("Mot de passe GENICIA++ (invisible) : ")
keyring.set_password(SERVICE, "identifiant", identifiant)
keyring.set_password(SERVICE, identifiant, mot_de_passe)
print("Identifiants enregistrés dans le Gestionnaire d'identifiants Windows.")
