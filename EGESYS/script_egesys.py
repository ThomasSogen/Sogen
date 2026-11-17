import sys
import os
import re
import json
import copy
from datetime import datetime, timedelta
from moteur_egesys import (connexion_egesys, deconnexion_egesys, soumettre_page_webdev, uploader_fichier_webdev,
                          selectionner_ligne_table, chercher_lignes_table, valeurs_zones_repetees,
                          telecharger_fichier_webdev, lire_table_webdev, executer_evenement_ajax)
import config_egesys
from journal_egesys import ajouter_au_journal, client_de

ACTIVITE_PAR_DEFAUT = "0"   # Recherche client : d'abord les clients inactifs (case "Clients Actifs" décochée)...
ACTIVITE_SECOURS = {"0": "1", "1": "0"}  # ...puis l'autre catégorie si personne n'est trouvé
TABLE_CLIENTS = "A12"       # Tableau des résultats de la recherche (page "Gestion des clients")

DOSSIER_SCRIPTS = os.path.dirname(os.path.abspath(__file__))
# Dossier des duplicatas : EGESYS_FACTURES permet à workflow.py de les récupérer pour les ranger dans completed/
DOSSIER_FACTURES = os.environ.get('EGESYS_FACTURES') or os.path.join(DOSSIER_SCRIPTS, 'factures')
# Fichier JSON des résultats ordre par ordre (facultatif, utilisé par workflow.py)
FICHIER_RESULTATS = os.environ.get('EGESYS_RESULTATS', '')
# Verrou partagé : une seule connexion EGESYS à la fois (workflow et lancement manuel ne peuvent pas se chevaucher)
FICHIER_VERROU = os.path.join(config_egesys.DOSSIER_LOCAL, 'connexion_egesys.lock')  # %LOCALAPPDATA%\EGESYS
ATTENTE_VERROU = 900  # secondes
AGENT_NOTES = '39'  # Liste "Agent" de la page Note : GINESTE Thomas (relevé le 06/11/2026, cartes/note_creation.json)


#dictionnaire de correspondance entre les civilités textuelles et leurs codes numériques dans EGESYS
# Valeurs relues dans EGESYS le 16/11/2026 (liste A208 inchangée : 38 options). Règle SOGEN depuis novembre 2026 : les
# civilités de personne ne s'utilisent plus, une personne = "ENTREPRISE INDIVIDUELLE". Elles restent dans la liste
# EGESYS (MADAME 18, MADEMOISELLE 19, MESSIEURS 20, MONSIEUR 21, MONSIEUR / MADAME 22, MONSIEUR (NON UTILISE) 23,
# VEUVE 38) mais sont volontairement absentes d'ici : ni l'agent ni le script ne peuvent plus les écrire.
MAPPING_CIVILITE = {
    "" : "1", "ASSOCIATION": "2", "CAT": "3", "CHAMBRE": "4", "COMMUNEAUTE": "5",
    "COOPERATIVE": "6", "E.A.R.L.": "7", "EIRL": "8", "ELEVAGE": "9",
    "ENTREPRISE INDIVIDUELLE": "10", "ESAT": "11", "E.U.R.L.": "12",
    "G.A.E.C.": "13", "G.F.A.": "14", "G.I.E.": "15", "INDIVISION": "16",
    "LYCEE ENSEI. PROF. AGRICOLE": "17", "ORGANISME": "24", "S.C.E.A.": "25",
    "SICA": "26", "SOCIETE": "27", "SOCIÉTÉ ANONYME": "28", 
    "SOCIETE ANONYME ETABLISSEMENT": "29", "SOCIETE CIVILE": "30", 
    "SOCIETE CIVILE AGRICOLE": "31", "SOCIÉTÉ CIVILE EXPLOITATION": "32", 
    "SOCIETE CIVILE LAITIERE": "33", "SOCIETE DE FAIT": "34", 
    "SOCIETE PAR ACTION SIMPLIFIEE": "35", "SOC RESP LIMITEE": "36", 
    "S.T.E.F.": "37"
}

MAPPING_MODE_REGLEMENT = {
    "CHEQUES": "2", "ESPECES": "3", "PRELEVEMENTS": "4", 
    "TRAITES": "5", "VIREMENT SOGEN": "6", "VIREMENTS": "7"
}

MAPPING_ECHEANCES = {  # Relevé sur la page "Modèles de regroupement" le 29/10/2026 (cartes/modele_regroupement_creation.json)
    "CHEQUE A RECEPTION": "2", "PRELEVEMENT AU 02": "3", "PRELEVEMENT AU 05": "4",
    "PRELEVEMENT AU 10": "5", "PRELEVEMENT AU 11": "6", "PRELEVEMENT AU 15": "7",
    "PRELEVEMENT AU 20": "8", "PRELEVEMENT AU 22": "9", "PRELEVEMENT AU 23": "10",
    "PRELEVEMENT AU 25": "11", "PRELEVEMENT AU 30": "12"
}

MAPPING_COMPTE_GENERAL = {
    "411000 ---- Clients": "2", 
    "41110000 ---- Clients Ventes Biens ou PS": "3", 
    "450000 ---- Collectif organismes": "4", 
    "453100 ---- COLLECTIF ADHERENTS": "5", 
    "45310000 ---- COLLECTIF ADHERENTS": "6", 
    "46700000 ---- Compte debiteur ou crediteur": "7"
}

MAPPING_MODELE = {
    "TOUTES FAMILLES": "2",
    "IA": "3",
    "DOSES DIVERS": "4", 
    "MINERAL": "5"
}

MAPPING_FAMILLE_DOCUMENT = {  # Relevé sur la page "Document" le 02/11/2026 (cartes/document_creation.json)
    "CONTRATS": "2",
    "DOCUMENTS SOGEN": "3"
}

# On associe le nom de l'action de l'IA au bon dictionnaire
ROUTAGE_TRADUCTIONS = {
    "modifier_civilite_client": MAPPING_CIVILITE,
    "modifier_mode_reglement": MAPPING_MODE_REGLEMENT,
    "modifier_echeance": MAPPING_ECHEANCES,
    "modifier_compte": MAPPING_COMPTE_GENERAL,
    "modifier_modele": MAPPING_MODELE
}


# ==========================================
# 1. LE MOTEUR : voir moteur_egesys.py
# ==========================================

# ==========================================
# 2. LE CATALOGUE (Vos recettes de navigation)
# ==========================================
# C'est la seule partie du code que vous modifierez à l'avenir.

CATALOGUE_ACTIONS = {
    "modifier_activite_client": [
        {"requete": {'WD_BUTTON_CLICK_': 'M3'}, "audit": {"titre_page": "Gestion des clients"}},
        {"requete": {'A24': '{activite_actuelle}', 'A28': '{code_client}', 'A29': '{nom_client}', 'WD_BUTTON_CLICK_': 'A27'}, "audit": {"champs_modifies": {'A28': '{code_client}', 'A29': '{nom_client}'}, "ignorer_vides": True}},
        {"requete": {'WD_BUTTON_CLICK_': 'A4'}, "audit": {}},
        {"requete": {'A197': '{activite}', 'WD_BUTTON_CLICK_': 'A4'}, "audit": {"champs_modifies": {'A197': '{activite}'}}}
    ],
    "modifier_civilite_client": [
        {"requete": {'WD_BUTTON_CLICK_': 'M3'}, "audit": {"titre_page": "Gestion des clients"}},
        {"requete": {'A24': '{activite_actuelle}', 'A28': '{code_client}', 'A29': '{nom_client}', 'WD_BUTTON_CLICK_': 'A27'}, "audit": {"champs_modifies": {'A28': '{code_client}', 'A29': '{nom_client}'}, "ignorer_vides": True}},
        {"requete": {'WD_BUTTON_CLICK_': 'A4'}, "audit": {}},
        # La liste A208 a un traitement serveur au changement (onchange = _JAEE(_PAGE_,'A208',47,...)) : c'est lui qui
        # mémorise la civilité côté serveur. Sans lui, "Enregistrer" (A4) réenregistre l'ancienne valeur (constaté le
        # 16/11/2026 : page renvoyée avec la nouvelle valeur, mais MONSIEUR toujours en base).
        {"requete": {'A208': '{civilite}', 'WD_BUTTON_CLICK_': 'A4'},
         "evenements_ajax": [{"alias": 'A208', "evenement": 47}],
         "audit": {"champs_modifies": {'A208': '{civilite}'}}},
        # Contrôle en base : nouvelle recherche du client, la colonne Civilité (A16) du tableau doit avoir changé
        {"requete": {'WD_BUTTON_CLICK_': 'M3'}, "audit": {"titre_page": "Gestion des clients"}},
        {"requete": {'A24': '{activite_actuelle}', 'A28': '{code_client}', 'A29': '{nom_client}', 'WD_BUTTON_CLICK_': 'A27'},
         "audit": {"ligne_presente": {"table": "A12", "critere": {'A16': '{civilite_libelle}'}}}},
    ],
    "modifier_nom_client": [
        {"requete": {'WD_BUTTON_CLICK_': 'M3'}, "audit": {"titre_page": "Gestion des clients"}},
        {"requete": {'A24': '{activite_actuelle}', 'A28': '{code_client}', 'A29': '{nom_client}', 'WD_BUTTON_CLICK_': 'A27'}, "audit": {"champs_modifies": {'A28': '{code_client}', 'A29': '{nom_client}'}, "ignorer_vides": True}},
        {"requete": {'WD_BUTTON_CLICK_': 'A4'}, "audit": {}},
        {"requete": {'A8': '{nom}', 'WD_BUTTON_CLICK_': 'A4'}, "audit": {"champs_modifies": {'A8': '{nom}'}}}
    ],
    "modifier_prenom_client": [
        {"requete": {'WD_BUTTON_CLICK_': 'M3'}, "audit": {"titre_page": "Gestion des clients"}},
        {"requete": {'A24': '{activite_actuelle}', 'A28': '{code_client}', 'A29': '{nom_client}', 'WD_BUTTON_CLICK_': 'A27'}, "audit": {"champs_modifies": {'A28': '{code_client}', 'A29': '{nom_client}'}, "ignorer_vides": True}},
        {"requete": {'WD_BUTTON_CLICK_': 'A4'}, "audit": {}},
        {"requete": {'A196': '{prenom}', 'WD_BUTTON_CLICK_': 'A4'}, "audit": {"champs_modifies": {'A196': '{prenom}'}}}
    ],
    "modifier_responsable_client": [
        {"requete": {'WD_BUTTON_CLICK_': 'M3'}, "audit": {"titre_page": "Gestion des clients"}},
        {"requete": {'A24': '{activite_actuelle}', 'A28': '{code_client}', 'A29': '{nom_client}', 'WD_BUTTON_CLICK_': 'A27'}, "audit": {"champs_modifies": {'A28': '{code_client}', 'A29': '{nom_client}'}, "ignorer_vides": True}},
        {"requete": {'WD_BUTTON_CLICK_': 'A4'}, "audit": {}},
        {"requete": {'A209': '{responsable}', 'WD_BUTTON_CLICK_': 'A4'}, "audit": {"champs_modifies": {'A209': '{responsable}'}}}
    ],
    "modifier_adresse_client": [
        {"requete": {'WD_BUTTON_CLICK_': 'M3'}, "audit": {"titre_page": "Gestion des clients"}},
        {"requete": {'A24': '{activite_actuelle}', 'A28': '{code_client}', 'A29': '{nom_client}', 'WD_BUTTON_CLICK_': 'A27'}, "audit": {"champs_modifies": {'A28': '{code_client}', 'A29': '{nom_client}'}, "ignorer_vides": True}},
        {"requete": {'WD_BUTTON_CLICK_': 'A4'}, "audit": {}},
        {"requete": {'A198': '{adresse}', 'A200': '{code_postal}', 'A214': '{ville}', 'WD_BUTTON_CLICK_': 'A4'}, "audit": {"champs_modifies": {'A198': '{adresse}', 'A200': '{code_postal}', 'A214': '{ville}'}}}
    ],
    "modifier_mail_client": [
        {"requete": {'WD_BUTTON_CLICK_': 'M3'}, "audit": {"titre_page": "Gestion des clients"}},
        {"requete": {'A24': '{activite_actuelle}', 'A28': '{code_client}', 'A29': '{nom_client}', 'WD_BUTTON_CLICK_': 'A27'}, "audit": {"champs_modifies": {'A28': '{code_client}', 'A29': '{nom_client}'}, "ignorer_vides": True}},
        {"requete": {'WD_BUTTON_CLICK_': 'A4'}, "audit": {}},
        {"requete": {'A205': '{mail}', 'WD_BUTTON_CLICK_': 'A4'}, "audit": {"champs_modifies": {'A205': '{mail}'}}}
    ],
    "modifier_telephone_fixe_client": [
        {"requete": {'WD_BUTTON_CLICK_': 'M3'}, "audit": {"titre_page": "Gestion des clients"}},
        {"requete": {'A24': '{activite_actuelle}', 'A28': '{code_client}', 'A29': '{nom_client}', 'WD_BUTTON_CLICK_': 'A27'}, "audit": {"champs_modifies": {'A28': '{code_client}', 'A29': '{nom_client}'}, "ignorer_vides": True}},
        {"requete": {'WD_BUTTON_CLICK_': 'A4'}, "audit": {}},
        {"requete": {'A203': '{telephone_fixe}', 'WD_BUTTON_CLICK_': 'A4'}, "audit": {"champs_modifies": {'A203': '{telephone_fixe}'}}}
    ],
    "modifier_telephone_portable_client": [
        {"requete": {'WD_BUTTON_CLICK_': 'M3'}, "audit": {"titre_page": "Gestion des clients"}},
        {"requete": {'A24': '{activite_actuelle}', 'A28': '{code_client}', 'A29': '{nom_client}', 'WD_BUTTON_CLICK_': 'A27'}, "audit": {"champs_modifies": {'A28': '{code_client}', 'A29': '{nom_client}'}, "ignorer_vides": True}},
        {"requete": {'WD_BUTTON_CLICK_': 'A4'}, "audit": {}},
        {"requete": {'A204': '{telephone_portable}', 'WD_BUTTON_CLICK_': 'A4'}, "audit": {"champs_modifies": {'A204': '{telephone_portable}'}}}
    ],
    "modifier_mail_comptable_client": [
        {"requete": {'WD_BUTTON_CLICK_': 'M3'}, "audit": {"titre_page": "Gestion des clients"}},
        {"requete": {'A24': '{activite_actuelle}', 'A28': '{code_client}', 'A29': '{nom_client}', 'WD_BUTTON_CLICK_': 'A27'}, "audit": {"champs_modifies": {'A28': '{code_client}', 'A29': '{nom_client}'}, "ignorer_vides": True}},
        {"requete": {'WD_BUTTON_CLICK_': 'A4'}, "audit": {}},
        {"requete": {'A206': '{mail_comptable}', 'WD_BUTTON_CLICK_': 'A4'}, "audit": {"champs_modifies": {'A206': '{mail_comptable}'}}}
    ],
    "ajouter_modèle_de_reglement_client": [
        {"requete": {'WD_BUTTON_CLICK_': 'M3'}, "audit": {"titre_page": "Gestion des clients"}},
        {"requete": {'A24': '{activite_actuelle}', 'A28': '{code_client}', 'A29': '{nom_client}', 'WD_BUTTON_CLICK_': 'A27'}, "audit": {"champs_modifies": {'A28': '{code_client}', 'A29': '{nom_client}'}, "ignorer_vides": True}},
        {"requete": {'WD_BUTTON_CLICK_': 'A4'}, "audit": {}},
        {"requete": {'WD_BUTTON_CLICK_': 'A324'}, "audit": {"titre_page": "Modèles de regroupement"}},
        {
            "requete": {
                'A6': '{date_d_application}',
                'A12': '{mode_de_reglement}',
                'A50': '{echeance}',
                'A43': '{compte general}',
                'A54': '{compte auxiliaire}',   # Lecture seule : vide = valeur affichée (ex: 4531GUITAE)
                'A7': '{domiciliation}',
                'A9': '{domiciliation_2}',      # 2e ligne de domiciliation
                'A16': '{iban_1}',
                'A24': '{iban_2}',
                'A25': '{iban_3}',
                'A27': '{iban_4}',
                'A28': '{iban_5}',
                'A29': '{iban_6}',
                'A30': '{iban_7}',
                'A26': '{bic}',
                'A31': '{rum}',                 # 15 caractères maximum
                # Ligne n°1 de la zone répétée A14 (le "name" WebDev diffère de l'id : zrl_1_A17 → zrl_1_A35)
                'zrl_1_A35': '{modèle}',
                'zrl_1_A20': '01',              # Champs masqués de la ligne : valeurs par défaut de la page
                'zrl_1_A18': '1,00',
                'WD_BUTTON_CLICK_': 'A3'
            },
            "conserver_valeurs_actuelles": True,
            "audit": {"titre_page": "Gestion des clients"}
        },
        # "Valider" n'ajoute la date qu'en mémoire dans la fiche : c'est "Enregistrer" (A4) qui l'écrit en base
        {"requete": {'WD_BUTTON_CLICK_': 'A4'}, "audit": {"titre_page": "Gestion des clients"}},
        # Relecture : le tableau affiché juste après "Valider" n'est pas une preuve d'enregistrement,
        # on rouvre donc la fiche pour vérifier ce qu'EGESYS a réellement enregistré.
        {"requete": {'WD_BUTTON_CLICK_': 'M3'}, "audit": {"titre_page": "Gestion des clients"}},
        {"requete": {'A24': '{activite_actuelle}', 'A28': '{code_client}', 'A29': '{nom_client}', 'WD_BUTTON_CLICK_': 'A27'}, "audit": {"champs_modifies": {'A28': '{code_client}', 'A29': '{nom_client}'}, "ignorer_vides": True}},
        {
            "requete": {'WD_BUTTON_CLICK_': 'A4'},
            "audit": {"ligne_presente": {"table": "A308", "critere": {"Date d'application": '{date_d_application}'}}}
        }
    ],
    "modifier_modèle_de_reglement_client": [
        {"requete": {'WD_BUTTON_CLICK_': 'M3'}, "audit": {"titre_page": "Gestion des clients"}},
        {"requete": {'A24': '{activite_actuelle}', 'A28': '{code_client}', 'A29': '{nom_client}', 'WD_BUTTON_CLICK_': 'A27'}, "audit": {"champs_modifies": {'A28': '{code_client}', 'A29': '{nom_client}'}, "ignorer_vides": True}},
        {"requete": {'WD_BUTTON_CLICK_': 'A4'}, "audit": {}},
        {
            # Sélection AJAX de la date d'application dans le tableau A308, puis bouton "Modification"
            "selection_ligne": {"table": "A308", "critere": {"Date d'application": '{date_cible}'}},
            "requete": {'WD_BUTTON_CLICK_': 'A325'},
            "audit": {"titre_page": "Modèles de regroupement", "champs_modifies": {'A6': '{date_cible}'}}
        },
        {
            # Tout champ vide dans l'ordre garde sa valeur actuelle (conserver_valeurs_actuelles)
            "requete": {
                'A6': '',                       # Date d'application : lecture seule
                'A54': '',                      # Compte auxiliaire : lecture seule
                'A12': '{mode_de_reglement}',
                'A50': '{echeance}',
                'A43': '{compte general}',
                'A7': '{domiciliation}',
                'A9': '{domiciliation_2}',
                'A16': '{iban_1}',
                'A24': '{iban_2}',
                'A25': '{iban_3}',
                'A27': '{iban_4}',
                'A28': '{iban_5}',
                'A29': '{iban_6}',
                'A30': '{iban_7}',
                'A26': '{bic}',
                'A31': '{rum}',
                'zrl_1_A35': '{modèle}',        # Ligne de modèle n°1 de la zone répétée A14
                'zrl_1_A13': '',                # Champs masqués calculés par EGESYS : renvoyés inchangés
                'zrl_1_A20': '',
                'zrl_1_A18': '',
                'WD_BUTTON_CLICK_': 'A3'
            },
            "conserver_valeurs_actuelles": True,
            "audit": {"titre_page": "Gestion des clients"}
        },
        # "Valider" ne modifie la fiche qu'en mémoire : "Enregistrer" (A4) écrit en base
        {"requete": {'WD_BUTTON_CLICK_': 'A4'}, "audit": {"titre_page": "Gestion des clients"}},
        # Relecture : on rouvre la date d'application et on compare chaque champ fourni dans l'ordre
        {"requete": {'WD_BUTTON_CLICK_': 'M3'}, "audit": {"titre_page": "Gestion des clients"}},
        {"requete": {'A24': '{activite_actuelle}', 'A28': '{code_client}', 'A29': '{nom_client}', 'WD_BUTTON_CLICK_': 'A27'}, "audit": {"champs_modifies": {'A28': '{code_client}', 'A29': '{nom_client}'}, "ignorer_vides": True}},
        {"requete": {'WD_BUTTON_CLICK_': 'A4'}, "audit": {}},
        {
            "selection_ligne": {"table": "A308", "critere": {"Date d'application": '{date_cible}'}},
            "requete": {'WD_BUTTON_CLICK_': 'A325'},
            "audit": {
                "titre_page": "Modèles de regroupement",
                "ignorer_vides": True,
                "champs_modifies": {
                    'A12': '{mode_de_reglement}', 'A50': '{echeance}', 'A43': '{compte general}',
                    'A7': '{domiciliation}', 'A9': '{domiciliation_2}',
                    'A16': '{iban_1}', 'A24': '{iban_2}', 'A25': '{iban_3}', 'A27': '{iban_4}',
                    'A28': '{iban_5}', 'A29': '{iban_6}', 'A30': '{iban_7}',
                    'A26': '{bic}', 'A31': '{rum}', 'zrl_1_A35': '{modèle}'
                }
            }
        }
    ],
    "ajouter_document_client": [
        {"requete": {'WD_BUTTON_CLICK_': 'M3'}, "audit": {"titre_page": "Gestion des clients"}},
        {"requete": {'A24': '{activite_actuelle}', 'A28': '{code_client}', 'A29': '{nom_client}', 'WD_BUTTON_CLICK_': 'A27'}, "audit": {"champs_modifies": {'A28': '{code_client}', 'A29': '{nom_client}'}, "ignorer_vides": True}},
        {"requete": {'WD_BUTTON_CLICK_': 'A4'}, "audit": {}},
        {"requete": {'WD_BUTTON_CLICK_': 'A153'}, "audit": {"titre_page": "Document"}},
        {
            "requete": {
                'A6': '{libellé}',              # Obligatoire (contrôle "Nom incorrect" du bouton Valider)
                'A11': '{famille}',             # Famille document (MAPPING_FAMILLE_DOCUMENT)
                'WD_BUTTON_CLICK_': 'A3'        # Bouton "Valider"
            },
            "upload_webdev": {
                'A7': '{chemin}'                # A7 est le bouton Upload HTML5 (envoi AJAX, remplit A9)
            },
            "audit": {"titre_page": "Gestion des clients"}
        },
        # "Enregistrer" (A4) de la fiche client, comme pour les modèles de règlement
        {"requete": {'WD_BUTTON_CLICK_': 'A4'}, "audit": {"titre_page": "Gestion des clients"}},
        # Relecture : la famille du document doit apparaître dans les documents du client
        {"requete": {'WD_BUTTON_CLICK_': 'M3'}, "audit": {"titre_page": "Gestion des clients"}},
        {"requete": {'A24': '{activite_actuelle}', 'A28': '{code_client}', 'A29': '{nom_client}', 'WD_BUTTON_CLICK_': 'A27'}, "audit": {"champs_modifies": {'A28': '{code_client}', 'A29': '{nom_client}'}, "ignorer_vides": True}},
        {
            "requete": {'WD_BUTTON_CLICK_': 'A4'},
            "audit": {"ligne_presente": {"table": "A143", "critere": {'A145': '{libellé}'}}}
        }
    ],
    "modifier_document_client": [
        {"requete": {'WD_BUTTON_CLICK_': 'M3'}, "audit": {"titre_page": "Gestion des clients"}},
        {"requete": {'A24': '{activite_actuelle}', 'A28': '{code_client}', 'A29': '{nom_client}', 'WD_BUTTON_CLICK_': 'A27'}, "audit": {"champs_modifies": {'A28': '{code_client}', 'A29': '{nom_client}'}, "ignorer_vides": True}},
        {"requete": {'WD_BUTTON_CLICK_': 'A4'}, "audit": {}},
        {
            "selection_ligne": {"table": "A143", "critere": {'A145': '{libelle_cible}'},
                                "evenement_ajax": {"alias": "A156", "evenement": "16"}},  # Le clic sur un document déclenche aussi A156 en AJAX
            "requete": {'WD_BUTTON_CLICK_': 'A154'},
            "audit": {"titre_page": "Document", "champs_modifies": {'A6': '{libelle_cible}'}}
        },
        {
            "requete": {
                'A6': '{libellé}',              # Nouveau libellé (vide = inchangé)
                'A11': '{famille}',             # Nouvelle famille (vide = inchangée)
                'WD_BUTTON_CLICK_': 'A3'
            },
            "conserver_valeurs_actuelles": True,
            "upload_webdev": {
                'A7': '{chemin}'                # Remplace le fichier si un nouveau fichier est fourni
            },
            "audit": {"titre_page": "Gestion des clients"}
        },
        {"requete": {'WD_BUTTON_CLICK_': 'A4'}, "audit": {"titre_page": "Gestion des clients"}},
        # Relecture
        {"requete": {'WD_BUTTON_CLICK_': 'M3'}, "audit": {"titre_page": "Gestion des clients"}},
        {"requete": {'A24': '{activite_actuelle}', 'A28': '{code_client}', 'A29': '{nom_client}', 'WD_BUTTON_CLICK_': 'A27'}, "audit": {"champs_modifies": {'A28': '{code_client}', 'A29': '{nom_client}'}, "ignorer_vides": True}},
        {
            "requete": {'WD_BUTTON_CLICK_': 'A4'},
            "audit": {"ligne_presente": {"table": "A143", "critere": {'A145': '{libellé}'}}}
        }
    ],
    "supprimer_document_client": [
        {"requete": {'WD_BUTTON_CLICK_': 'M3'}, "audit": {"titre_page": "Gestion des clients"}},
        {"requete": {'A24': '{activite_actuelle}', 'A28': '{code_client}', 'A29': '{nom_client}', 'WD_BUTTON_CLICK_': 'A27'}, "audit": {"champs_modifies": {'A28': '{code_client}', 'A29': '{nom_client}'}, "ignorer_vides": True}},
        {"requete": {'WD_BUTTON_CLICK_': 'A4'}, "audit": {}},
        {
            # Sélection du document puis bouton "Suppression" (la confirmation n'existe que côté navigateur)
            "selection_ligne": {"table": "A143", "critere": {'A145': '{libelle_cible}'},
                                "evenement_ajax": {"alias": "A156", "evenement": "16"}},  # Le clic sur un document déclenche aussi A156 en AJAX
            "requete": {'WD_BUTTON_CLICK_': 'A155'},
            "audit": {"titre_page": "Gestion des clients"}
        },
        {"requete": {'WD_BUTTON_CLICK_': 'A4'}, "audit": {"titre_page": "Gestion des clients"}},
        # Relecture
        {"requete": {'WD_BUTTON_CLICK_': 'M3'}, "audit": {"titre_page": "Gestion des clients"}},
        {"requete": {'A24': '{activite_actuelle}', 'A28': '{code_client}', 'A29': '{nom_client}', 'WD_BUTTON_CLICK_': 'A27'}, "audit": {"champs_modifies": {'A28': '{code_client}', 'A29': '{nom_client}'}, "ignorer_vides": True}},
        {
            "requete": {'WD_BUTTON_CLICK_': 'A4'},
            "audit": {"ligne_absente": {"table": "A143", "critere": {'A145': '{libelle_cible}'}}}
        }
    ],
    "ajouter_note_client": [
        {"requete": {'WD_BUTTON_CLICK_': 'M3'}, "audit": {"titre_page": "Gestion des clients"}},
        {"requete": {'A24': '{activite_actuelle}', 'A28': '{code_client}', 'A29': '{nom_client}', 'WD_BUTTON_CLICK_': 'A27'}, "audit": {"champs_modifies": {'A28': '{code_client}', 'A29': '{nom_client}'}, "ignorer_vides": True}},
        # Fiche ouverte : lecture (sans modification) de l'adresse mail du client (A205). Sert après un duplicata de
        # facture : les factures sont envoyées au client à cette adresse (champ "client" de result/<nom>.json).
        {"requete": {'WD_BUTTON_CLICK_': 'A4'}, "audit": {}, "lire": {'A205': 'mail_client'}},
        {"requete": {'WD_BUTTON_CLICK_': 'A177'}, "audit": {"titre_page": "Note"}},
        {
            "requete": {
                'A11': '{sujet}',
                'A35': '{date_de_rappel}',
                'A197': '{confidentiel}',
                'A23': '{message}',
                'A28': AGENT_NOTES,  # Agent (opérateur) de la note
                'WD_BUTTON_CLICK_': 'A3' # Le bouton "Valider l'importation"
            },
            "upload_webdev": {
                'A29': '{piece_jointe}' # A29 est le bouton Upload HTML5 (envoi AJAX, remplit A9)
            },
            "audit": {
                "titre_page": "Gestion des clients",
                "ligne_presente": {"table": "A160", "critere": {'Sujet': '{sujet}'}}
            }
        }
    ],
    "modifier_note_client": [
        {"requete": {'WD_BUTTON_CLICK_': 'M3'}, "audit": {"titre_page": "Gestion des clients"}},
        {"requete": {'A24': '{activite_actuelle}', 'A28': '{code_client}', 'A29': '{nom_client}', 'WD_BUTTON_CLICK_': 'A27'}, "audit": {"champs_modifies": {'A28': '{code_client}', 'A29': '{nom_client}'}, "ignorer_vides": True}},
        {"requete": {'WD_BUTTON_CLICK_': 'A4'}, "audit": {}},
        {
            # Sélection AJAX de la note dans le tableau A160, puis bouton "Modification"
            "selection_ligne": {"table": "A160", "critere": {'Sujet': '{sujet_cible}', 'Date': '{date_cible}'}},
            "requete": {'WD_BUTTON_CLICK_': 'A178'},
            "audit": {"titre_page": "Note", "champs_modifies": {'A11': '{sujet_cible}'}}
        },
        {
            "requete": {
                'A11': '{sujet}',
                'A35': '{date_de_rappel}',
                'A197': '{confidentiel}',
                'A23': '{message}',
                'WD_BUTTON_CLICK_': 'A3'
            },
            "conserver_valeurs_actuelles": True, # Un champ vide dans l'ordre garde la valeur actuelle de la note
            "upload_webdev": {
                'A29': '{piece_jointe}' # Remplace la pièce jointe si un fichier est fourni
            },
            "audit": {
                "titre_page": "Gestion des clients",
                "ligne_presente": {"table": "A160", "critere": {'Sujet': '{sujet}'}}
            }
        }
    ],
    "supprimer_note_client": [
        {"requete": {'WD_BUTTON_CLICK_': 'M3'}, "audit": {"titre_page": "Gestion des clients"}},
        {"requete": {'A24': '{activite_actuelle}', 'A28': '{code_client}', 'A29': '{nom_client}', 'WD_BUTTON_CLICK_': 'A27'}, "audit": {"champs_modifies": {'A28': '{code_client}', 'A29': '{nom_client}'}, "ignorer_vides": True}},
        {"requete": {'WD_BUTTON_CLICK_': 'A4'}, "audit": {}},
        {
            # Sélection AJAX de la note puis bouton "Suppression" (la confirmation n'existe que côté navigateur)
            "selection_ligne": {"table": "A160", "critere": {'Sujet': '{sujet_cible}', 'Date': '{date_cible}'}},
            "requete": {'WD_BUTTON_CLICK_': 'A179'},
            "audit": {
                "titre_page": "Gestion des clients",
                "ligne_absente": {"table": "A160", "critere": {'Sujet': '{sujet_cible}', 'Date': '{date_cible}'}}
            }
        }
    ],
    # Gestion des Ventes > Factures : duplicata PDF de la 1re facture validée correspondant aux critères (la plus récente)
    # ⚠️ Pages sensibles : ne jamais cliquer A77/A65/A23/A85 (Factures) ni A10 (Détail = envoi au client par mail)
    "telecharger_facture_client": [
        {"requete": {'WD_BUTTON_CLICK_': 'M3'}, "audit": {"titre_page": "Gestion des clients"}},
        # A2 = "page précédente" (pas "accueil") : on remonte l'historique jusqu'au Menu Général (2 clics après la
        # connexion, davantage après d'autres factures : jusqu'à 15 clics, simple navigation sans risque)
        {"remonter_jusqu_a": {"bouton": 'A2', "titre_page": "Menu Général", "max_clics": 15}},
        {"requete": {'WD_BUTTON_CLICK_': 'I35'}, "audit": {"titre_page": "Factures"}},
        # Tous les filtres sont envoyés (vides si non demandés) : le serveur garde sinon ceux de la recherche précédente.
        # Dates et montant TTC : plages calculées par preparer_donnees. A51 = '2' : seule "Validée en Compta (V,M)" cochée.
        {"requete": {'A15': '{code_client}', 'A22': '{nom_client}', 'A53': '{numero_facture}',
                     'A16': '{date_realisation_du}', 'A17': '{date_realisation_au}',
                     'A60': '{date_etat_du}', 'A62': '{date_etat_au}',
                     'A67': '{montant_min}', 'A73': '{montant_max}',
                     'A51': '2', 'WD_BUTTON_CLICK_': 'A27'},
         # Une seule facture doit correspondre aux critères du mail, sinon aucune n'est sélectionnée (arrêt).
         # Sans aucun critère de facture : la plus récente (1re ligne) est acceptée.
         "audit": {"titre_page": "Factures",
                   "ligne_unique": {"table": "A31", "critere": {'Etat': 'V', 'A49': '{numero_facture}'},
                                    "element": "facture",
                                    "premiere_si_vides": ['numero_facture', 'date_realisation', 'date_etat', 'montant'],
                                    "criteres_affiches": ['nom_client', 'code_client', 'numero_facture', 'date_realisation',
                                                          'date_etat', 'montant'],
                                    "colonnes_affichees": {"N°": 'A49', "Date": 'Dt Fac', "Date d'état": 'Dt Etat',
                                                           "TTC": 'TTC'}}}},
        {"requete": {'WD_BUTTON_CLICK_': 'A11'},
         "audit": {"titre_page": "Facture Detail", "champs_modifies": {'A11': '{numero_facture}'}, "ignorer_vides": True}},
        # Duplicata : le serveur écrit le chemin du PDF dans A57 ; fichier = facture_<n° client>_<n° facture>.pdf
        {"requete": {'WD_BUTTON_CLICK_': 'A3'}, "audit": {"titre_page": "Facture Detail"},
         "telechargement": {"champ": "A57", "dossier": DOSSIER_FACTURES, "prefixe": "facture_",
                            "nom": ['A20', 'A11'], "extension": ".pdf"}}
    ],
    # Toutes les factures validées d'une période (ex : un mois) : la recherche liste les factures, puis chacune est
    # téléchargée par la recette "telecharger_facture_client" avec son numéro exact (une facture à la fois).
    "telecharger_factures_client": [
        {"requete": {'WD_BUTTON_CLICK_': 'M3'}, "audit": {"titre_page": "Gestion des clients"}},
        {"remonter_jusqu_a": {"bouton": 'A2', "titre_page": "Menu Général", "max_clics": 15}},
        {"requete": {'WD_BUTTON_CLICK_': 'I35'}, "audit": {"titre_page": "Factures"}},
        # Seule la période (date de facture, bornes incluses) filtre ; les autres filtres sont vidés.
        {"requete": {'A15': '{code_client}', 'A22': '{nom_client}', 'A53': '',
                     'A16': '{periode_du}', 'A17': '{periode_au}',
                     'A60': '', 'A62': '', 'A67': '', 'A73': '',
                     'A51': '2', 'WD_BUTTON_CLICK_': 'A27'},
         "audit": {"titre_page": "Factures"},
         # Pour chaque facture validée trouvée : recette d'une facture avec son numéro. Arrêt sans rien télécharger
         # si aucune facture, si plus de "max" factures, ou si les factures appartiennent à plusieurs clients.
         "pour_chaque_ligne": {"table": "A31", "critere": {'Etat': 'V'}, "colonne": 'A49', "colonne_client": 'A12',
                               "action": "telecharger_facture_client", "dossier": "facture", "variable": "numero_facture",
                               "max": 30, "element": "facture",
                               "criteres_affiches": ['nom_client', 'code_client', 'periode_du', 'periode_au'],
                               "colonnes_affichees": {"N°": 'A49', "Client": 'A12', "Date": 'Dt Fac', "TTC": 'TTC'}}},
    ],
}

# ==========================================
# 3. L'EXÉCUTION (Le rôle de l'Agent IA)
# Note de suivi ajoutée automatiquement sur la fiche après chaque modification réussie : action → sujet de la note.
# Les {variables} viennent de l'ordre. Les actions sur les notes n'ajoutent pas de note (ce serait une note sur une note).
# Factures : la note liste les duplicatas récupérés ; le n° de facture et le code client viennent des PDF enregistrés.
NOTES_DE_SUIVI = {
    "telecharger_facture_client": "Duplicata facture {numero_facture}",
    "telecharger_factures_client": "Duplicatas factures du {periode_du} au {periode_au}",
    "modifier_civilite_client": "Modification civilité",
    "modifier_nom_client": "Modification nom",
    "modifier_prenom_client": "Modification prénom",
    "modifier_responsable_client": "Modification responsable",
    "modifier_adresse_client": "Modification adresse",
    "modifier_mail_client": "Modification mail",
    "modifier_telephone_fixe_client": "Modification téléphone fixe",
    "modifier_telephone_portable_client": "Modification téléphone portable",
    "modifier_mail_comptable_client": "Modification mail comptable",
    "ajouter_modèle_de_reglement_client": "Nouveau modèle de règlement au {date_d_application}",
    "modifier_modèle_de_reglement_client": "Correction modèle de règlement du {date_cible}",
    "ajouter_document_client": "Ajout document {libellé}",
    "modifier_document_client": "Modification document {libelle_cible}",
    "supprimer_document_client": "Suppression document {libelle_cible}",
}
DOSSIERS_MODIFIES = ("nouvelle_valeur_client", "modèle_de_reglement", "document")  # Valeurs tracées dans la note
LIBELLES_NOTE = {
    "civilite": "Civilité", "prenom": "Prénom", "telephone_fixe": "Téléphone fixe", "telephone_portable": "Téléphone portable",
    "mail_comptable": "Mail comptable", "bic": "BIC", "iban": "IBAN", "rum": "RUM", "echeance": "Échéance",
    "mode_de_reglement": "Mode de règlement", "modèle": "Famille de produits", "compte general": "Compte général",
    "domiciliation": "Banque", "domiciliation_2": "Agence", "date_d_application": "Date d'application",
    "libellé": "Libellé", "chemin": "Fichier", "famille": "Famille",
}

# ==========================================

# Ordre reçu de l'agent IA
ordre_ia = {
    "action": "ajouter_note_client",
    "activite_actuelle": "0",
    "nom_client": "guitton",
    "nouvelle_valeur_client" : {
        "activite": "", 
        "civilite": "", 
        "nom": "", 
        "prenom": "", 
        "responsable": "", 
        "adresse": "", 
        "code_postal": "", 
        "ville": "", 
        "email": "",
        "telephone_fixe": "",
        "telephone_portable": "",
        "mail": "",
        "mail_comptable": "",
    },
    "modèle_de_reglement": {
        "date_d_application": "01/01/2001",
        "mode_de_reglement": "ESPECES",
        "echeance": "PRELEVEMENT AU 20",
        "compte general": "45310000 ---- COLLECTIF ADHERENTS",
        "compte auxiliaire": "",
        "modèle": "MINERAL",
        "domiciliation": "France",
        "iban" : "FR7612345678901234567890123",
        "bic" : "TESTFRPP",
        "rum" : "RUMTEST20261029ABCDEF",
    },
    "document": {
        "libellé": "test",
        "chemin" : "test.pdf"
    },
    "note": {
        "sujet": "test2",
        "date_de_rappel": "30/10/2026",
        "piece_jointe": "test.pdf",
        "confidentiel": "0",
        "message": "test test test"
    }
}

# ==========================================
# 1. L'INTERCEPTEUR INTELLIGENT (Gère les sous-dossiers)
# ==========================================

def traduire(dico, cle, mapping):
    """Remplace la valeur lisible (ex: 'ESPECES') par l'identifiant WebDev (ex: '3').
    Une valeur inconnue arrête le script au lieu d'envoyer n'importe quoi au serveur."""
    valeur = dico.get(cle)
    if not valeur or valeur in mapping.values():
        return
    if valeur not in mapping:
        sys.exit(f"🛑 ERREUR : '{valeur}' n'est pas une valeur connue pour '{cle}'. Valeurs possibles : {list(mapping)}")
    dico[cle] = mapping[valeur]

def preparer_donnees(ordre):
    """Traduit les listes déroulantes, découpe l'IBAN, puis aplatit l'ordre en un seul dictionnaire."""
    # 0. Identification du client : par son nom (A29), son code client (A28), ou les deux
    ordre.setdefault("nom_client", "")
    ordre.setdefault("code_client", "")
    # Case "Clients Actifs" de la recherche : "1" = actifs, "0" = inactifs. "" = non précisé dans le mail : on cherche
    # d'abord parmi les inactifs, puis parmi les actifs si personne n'est trouvé (voir rechercher_client_autre_activite)
    activite = str(ordre.get("activite_actuelle", "")).strip()
    if activite not in ("", "0", "1"):
        sys.exit(f"🛑 ERREUR : activite_actuelle = '{activite}' (attendu : '1' client actif, '0' inactif, '' non précisé).")
    ordre["activite_actuelle"] = activite or ACTIVITE_PAR_DEFAUT
    ordre["activite_automatique"] = not activite  # True : l'autre catégorie sera essayée si le client n'est pas trouvé
    ordre["code_client"] = str(ordre["code_client"]).replace(" ", "")
    if not ordre["nom_client"] and not ordre["code_client"] and not ordre.get("facture", {}).get("numero_facture"):
        sys.exit("🛑 ERREUR : L'ordre doit identifier le client par 'nom_client' ou 'code_client'.")
    if ordre["code_client"] and not re.fullmatch(r'\d{7,8}', ordre["code_client"]):
        sys.exit(f"🛑 ERREUR : Le code client '{ordre['code_client']}' est invalide (7 ou 8 chiffres attendus).")

    # A. Traduction de la fiche client
    if "nouvelle_valeur_client" in ordre:
        # Libellé gardé pour le contrôle en base (colonne Civilité du tableau de recherche)
        civilite_libelle = ordre["nouvelle_valeur_client"].get("civilite", "")
        traduire(ordre["nouvelle_valeur_client"], "civilite", MAPPING_CIVILITE)
        ordre["civilite_libelle"] = {v: k for k, v in MAPPING_CIVILITE.items()}.get(civilite_libelle, civilite_libelle)

    # Traduction de la famille de document
    if "document" in ordre:
        traduire(ordre["document"], "famille", MAPPING_FAMILLE_DOCUMENT)

    # B. Traduction du modèle de règlement
    if "modèle_de_reglement" in ordre:
        reglement = ordre["modèle_de_reglement"]
        traduire(reglement, "mode_de_reglement", MAPPING_MODE_REGLEMENT)
        traduire(reglement, "echeance", MAPPING_ECHEANCES)
        traduire(reglement, "compte general", MAPPING_COMPTE_GENERAL)  # Attention à l'espace dans la clé
        traduire(reglement, "modèle", MAPPING_MODELE)
        print("🔄 Traductions des listes déroulantes effectuées.")

        if len(reglement.get("rum", "")) > 15:
            sys.exit(f"🛑 ERREUR : Le RUM '{reglement['rum']}' dépasse 15 caractères (limite EGESYS).")

        # C. Découpage de l'IBAN (7 blocs de 4, vides si pas d'IBAN)
        iban_brut = reglement.get("iban", "").replace(" ", "").upper()
        if iban_brut:
            # Contrôle avant envoi : 27 caractères (IBAN français = 7 blocs EGESYS) et clé de contrôle modulo 97
            iban_numerique = ''.join(str(int(c, 36)) for c in iban_brut[4:] + iban_brut[:4]) if iban_brut.isalnum() else ''
            if len(iban_brut) != 27 or not iban_brut.startswith('FR') or not iban_numerique or int(iban_numerique) % 97 != 1:
                sys.exit(f"🛑 ERREUR : L'IBAN '{reglement['iban']}' est invalide (IBAN français de 27 caractères attendu, clé de contrôle vérifiée).")
        blocs_iban = [iban_brut[i:i+4] for i in range(0, len(iban_brut), 4)]
        for i in range(7):
            reglement[f"iban_{i+1}"] = blocs_iban[i] if i < len(blocs_iban) else ""

    # ==========================================
    # 2. L'APLATISSEUR DE DONNÉES (Pour simplifier le Catalogue)
    # ==========================================
    # On fusionne tous les sous-dossiers en un seul dictionnaire plat.
    # Ainsi, vous pouvez écrire simplement '{iban_1}' ou '{bic}' dans le catalogue.
    donnees_plates = dict(ordre)
    for sous_dossier in ("nouvelle_valeur_client", "modèle_de_reglement", "document", "note", "note_cible", "document_cible",
                         "facture", "factures"):
        donnees_plates.update(ordre.get(sous_dossier, {}))
    donnees_plates.update(plages_recherche_facture(ordre.get("facture", {})))
    if "factures" in ordre:
        controler_periode(ordre["factures"])
    # Pour une modification, un sujet non fourni reste celui de la note ciblée
    if not donnees_plates.get("sujet") and donnees_plates.get("sujet_cible"):
        donnees_plates["sujet"] = donnees_plates["sujet_cible"]
    # Idem pour le libellé d'un document modifié
    if not donnees_plates.get("libellé") and donnees_plates.get("libelle_cible"):
        donnees_plates["libellé"] = donnees_plates["libelle_cible"]
    return donnees_plates

MARGE_JOURS_FACTURE = 3        # Date citée dans le mail ± 3 jours
MARGE_MONTANT_FACTURE = 0.01   # Montant TTC cité ± 1 % (au moins 1 €) : la recherche EGESYS exige une plage

def plages_recherche_facture(facture):
    """Transforme les valeurs approximatives du mail en plages de recherche EGESYS (vides si non fournies)."""
    plages = {}
    for champ in ("date_realisation", "date_etat"):
        valeur = facture.get(champ, "").strip()
        du = au = ""
        if valeur:
            try:
                jour = datetime.strptime(valeur, "%d/%m/%Y")
            except ValueError:
                sys.exit(f"🛑 ERREUR : La date '{valeur}' ({champ}) doit être au format JJ/MM/AAAA.")
            du = (jour - timedelta(days=MARGE_JOURS_FACTURE)).strftime("%d/%m/%Y")
            au = (jour + timedelta(days=MARGE_JOURS_FACTURE)).strftime("%d/%m/%Y")
        plages[f"{champ}_du"], plages[f"{champ}_au"] = du, au
    valeur = re.sub(r'[\s€\u00a0]', '', facture.get("montant", "")).replace(',', '.')
    plages["montant_min"] = plages["montant_max"] = ""
    if valeur:
        try:
            montant = float(valeur)
        except ValueError:
            sys.exit(f"🛑 ERREUR : Le montant '{facture['montant']}' n'est pas un nombre.")
        marge = max(1.0, montant * MARGE_MONTANT_FACTURE)
        plages["montant_min"] = f"{max(0.0, montant - marge):.2f}".replace('.', ',')
        plages["montant_max"] = f"{montant + marge:.2f}".replace('.', ',')
    plages["numero_facture"] = facture.get("numero_facture", "").replace(' ', '')
    if plages["numero_facture"] and not plages["numero_facture"].isdigit():
        sys.exit(f"🛑 ERREUR : Le numéro de facture '{facture['numero_facture']}' doit être composé de chiffres.")
    return plages

def controler_periode(factures):
    """Période d'une demande de plusieurs factures : deux dates JJ/MM/AAAA obligatoires, début ≤ fin."""
    dates = {}
    for champ in ("periode_du", "periode_au"):
        valeur = str(factures.get(champ, "")).strip()
        if not valeur:
            sys.exit(f"🛑 ERREUR : La période des factures est incomplète ('{champ}' vide).")
        try:
            dates[champ] = datetime.strptime(valeur, "%d/%m/%Y")
        except ValueError:
            sys.exit(f"🛑 ERREUR : La date '{valeur}' ({champ}) doit être au format JJ/MM/AAAA.")
    if dates["periode_du"] > dates["periode_au"]:
        sys.exit(f"🛑 ERREUR : La période des factures commence après sa fin ({factures['periode_du']} > {factures['periode_au']}).")

def _valeur_lisible(champ, valeur):
    valeur = str(valeur).strip()
    if champ == "iban" and len(valeur.replace(" ", "")) > 8:  # IBAN masqué dans la note
        brut = valeur.replace(" ", "")
        return f"{brut[:4]}…{brut[-4:]}"
    if champ in ("chemin", "piece_jointe"):
        return os.path.basename(valeur)
    return valeur

def lignes_modification(ordre_original, anciennes_valeurs):
    """Une ligne par valeur modifiée : « ancienne » → « nouvelle » (ou seulement « nouvelle » si l'ancienne est inconnue).
    Sert à la note de suivi et à la colonne "Modification" du journal Excel."""
    lignes = []
    for dossier in DOSSIERS_MODIFIES + ("note",):
        for champ, nouvelle in ordre_original.get(dossier, {}).items():
            if not str(nouvelle).strip():
                continue  # Champ non modifié
            libelle = LIBELLES_NOTE.get(champ, champ.replace("_", " ").capitalize())
            ancienne = anciennes_valeurs.get(champ, "").strip()
            if ancienne and ancienne != str(nouvelle).strip():
                lignes.append(f"{libelle} : « {_valeur_lisible(champ, ancienne)} » → « {_valeur_lisible(champ, nouvelle)} »")
            else:
                lignes.append(f"{libelle} : « {_valeur_lisible(champ, nouvelle)} »")
    if ordre_original.get("action") == "supprimer_document_client":
        lignes.append(f"Document supprimé : « {ordre_original.get('document_cible', {}).get('libelle_cible', '')} »")
    if ordre_original.get("action") == "supprimer_note_client":
        lignes.append(f"Note supprimée : « {ordre_original.get('note_cible', {}).get('sujet_cible', '')} »")
    return lignes

def factures_des_fichiers(fichiers):
    """[(code client, n° de facture)] d'après les noms des duplicatas : facture_<code client>_<n° facture>.pdf."""
    factures = []
    for chemin in fichiers:
        trouve = re.fullmatch(r'facture_(\d+)_(\d+)\.pdf', os.path.basename(chemin))
        if trouve:
            factures.append((trouve.group(1), trouve.group(2)))
    return factures

def note_de_suivi(ordre_original, anciennes_valeurs, fichiers=()):
    """Ordre "ajouter_note_client" qui décrit la modification réussie (sujet, ancien → nouveau, motif).
    fichiers : PDF récupérés par l'ordre (duplicatas de facture), listés dans la note."""
    action = ordre_original["action"]
    if action not in NOTES_DE_SUIVI:
        return None
    plates = dict(ordre_original)
    for dossier in DOSSIERS_MODIFIES + ("document_cible", "facture", "factures"):
        plates.update(ordre_original.get(dossier, {}))
    code_client, nom_client = ordre_original.get("code_client", ""), ordre_original.get("nom_client", "")
    factures = factures_des_fichiers(fichiers)
    if action in ("telecharger_facture_client", "telecharger_factures_client"):
        if not factures:
            return None  # Rien de récupéré : pas de note
        plates["numero_facture"] = factures[0][1]
        # Client désigné par son code exact, lu sur la facture (la demande peut ne donner que le n° de facture)
        code_client, nom_client = factures[0][0], ""
        lignes = [f"Duplicata(s) de facture récupéré(s) automatiquement (agent EGESYS) le {datetime.now():%d/%m/%Y à %H:%M}."]
        lignes += [f"- Facture n° {numero}" for _, numero in factures]
    else:
        lignes = [f"Modification enregistrée automatiquement (agent EGESYS) le {datetime.now():%d/%m/%Y à %H:%M}."]
        lignes += [f"- {ligne}" for ligne in lignes_modification(ordre_original, anciennes_valeurs)]
    sujet = NOTES_DE_SUIVI[action].format_map({k: v for k, v in plates.items() if isinstance(v, str)})[:60]
    if ordre_original.get("justification"):
        lignes.append(f"Motif (extrait du mail) : « {ordre_original['justification']} »")
    # Après un changement de nom, le client se retrouve sous son nouveau nom
    nouveau_nom = ordre_original.get("nouvelle_valeur_client", {}).get("nom", "") if action == "modifier_nom_client" else ""
    return {
        "action": "ajouter_note_client",
        "justification": "Note de suivi automatique",
        "activite_actuelle": ordre_original.get("activite_actuelle", ""),  # Remplacée par celle où le client a été trouvé
        "code_client": code_client,
        "nom_client": nouveau_nom.lower() or nom_client,
        "note": {"sujet": sujet, "message": "\n".join(lignes), "confidentiel": "0", "date_de_rappel": "", "piece_jointe": ""},
    }

def formater(modele, donnees_plates):
    """'{nom}' → valeur de l'ordre. Une donnée absente de l'ordre arrête le script avec un message clair."""
    try:
        return modele.format(**donnees_plates)
    except KeyError as cle:
        sys.exit(f"🛑 ERREUR : La donnée {cle} est absente de l'ordre, alors que la recette en a besoin ('{modele}').")

# ==========================================
# 3. L'EXÉCUTION DE LA BOUCLE
# ==========================================

def executer_recette(ordre, session, url_courante, soup_courante, etat):
    """Joue la recette du catalogue correspondant à ordre['action'] et retourne la page finale."""
    if ordre.get("action") not in CATALOGUE_ACTIONS:
        sys.exit(f"🛑 ERREUR : Action inconnue '{ordre.get('action')}'. Actions possibles : {list(CATALOGUE_ACTIONS)}")
    champs_modifies = {champ for dossier in DOSSIERS_MODIFIES for champ in ordre.get(dossier, {})}
    donnees_plates = preparer_donnees(ordre)
    recette = CATALOGUE_ACTIONS[ordre["action"]]
    etat['anciennes_valeurs'] = {}  # Valeurs affichées AVANT modification, pour la note de suivi
    print(f"--- DÉBUT DE LA MISSION : {ordre['action']} ---")

    for index, etape in enumerate(recette, start=1):

        # Remontée par le bouton "page précédente" jusqu'à la page voulue (nombre de clics variable)
        if "remonter_jusqu_a" in etape:
            cible = etape["remonter_jusqu_a"]
            print(f"\n--- ÉTAPE {index}/{len(recette)} ---")
            for _ in range(cible["max_clics"]):
                titre_actuel = soup_courante.title.string if soup_courante.title else ""
                if cible["titre_page"].lower() in titre_actuel.lower():
                    break
                print(f"🖱️ Clic sur le bouton : {cible['bouton']} (depuis '{titre_actuel.strip()}')")
                reponse, soup_courante = soumettre_page_webdev(session, url_courante, soup_courante,
                                                              {'WD_BUTTON_CLICK_': cible['bouton']})
                url_courante = reponse.url
                etat['url'], etat['soup'] = url_courante, soup_courante
            titre_actuel = soup_courante.title.string if soup_courante.title else ""
            if cible["titre_page"].lower() not in titre_actuel.lower():
                print(f"🛑 ERREUR DE NAVIGATION : '{cible['titre_page']}' non atteint après {cible['max_clics']} clics (page '{titre_actuel}').")
                sys.exit("Arrêt de sécurité.")
            print("✅ Navigation confirmée.")
            continue

        # 1. PRÉPARATION DE LA REQUÊTE
        payload_final = {}
        for cle, valeur_brute in etape["requete"].items():
            if isinstance(valeur_brute, str) and '{' in valeur_brute:
                # On utilise le dictionnaire aplati pour le formatage
                payload_final[cle] = formater(valeur_brute, donnees_plates)
            else:
                payload_final[cle] = valeur_brute

        # Modification : un champ vide dans l'ordre reprend la valeur actuellement affichée
        if etape.get("conserver_valeurs_actuelles"):
            valeurs_zr = valeurs_zones_repetees(str(soup_courante))  # Lignes de zones répétées (générées en JS)
            for cle, valeur in payload_final.items():
                if valeur == '' and cle in valeurs_zr:
                    payload_final[cle] = valeurs_zr[cle]
                    continue
                if valeur != '' or cle.startswith('WD_'):
                    continue
                balises = soup_courante.find_all(['input', 'select', 'textarea'], {'name': cle})
                for balise in balises:
                    if balise.name == 'select':
                        option_choisie = balise.find('option', selected=True)
                        payload_final[cle] = option_choisie.get('value', '') if option_choisie else ''
                    elif balise.name == 'textarea':
                        payload_final[cle] = balise.get_text()
                    elif (balise.get('type') or '').lower() in ('checkbox', 'radio'):
                        if balise.has_attr('checked'):
                            payload_final[cle] = balise.get('value', '')
                    elif (balise.get('type') or '').lower() != 'hidden':
                        payload_final[cle] = balise.get('value', '')

        print(f"\n--- ÉTAPE {index}/{len(recette)} ---")

        # 2. RÉCAPITULATIF AVANT ENVOI
        donnees_utiles = {k: v for k, v in payload_final.items() if not k.startswith('WD_')}
        if donnees_utiles:
            print(f"📤 Envoi des données : {donnees_utiles}")
        else:
            print(f"🖱️ Clic sur le bouton : {payload_final.get('WD_BUTTON_CLICK_', 'Inconnu')}")


        # --- NOUVEAU : PRÉPARATION DU FICHIER ---
        fichiers_finaux = None
        if "upload" in etape:
            fichiers_finaux = {}
            for champ, chemin_brut in etape["upload"].items():
                chemin_formatte = formater(chemin_brut, donnees_plates)
                print(f"📁 Préparation de l'upload pour {chemin_formatte}")
                # On ouvre le fichier en mode Lecture Binaire ('rb')
                try:
                    fichiers_finaux[champ] = open(chemin_formatte, 'rb')
                except FileNotFoundError:
                    sys.exit(f"🛑 ERREUR : Le fichier {chemin_formatte} est introuvable sur le disque.")

        # --- UPLOAD AJAX (champs Upload HTML5 WebDev) : envoyé avant le clic ---
        if "upload_webdev" in etape:
            for champ, chemin_brut in etape["upload_webdev"].items():
                chemin_formatte = formater(chemin_brut, donnees_plates)
                if not chemin_formatte:
                    continue  # Pas de pièce jointe demandée
                if not os.path.isfile(chemin_formatte):
                    sys.exit(f"🛑 ERREUR : Le fichier {chemin_formatte} est introuvable sur le disque.")
                print(f"📁 Upload WebDev de {chemin_formatte} via {champ}")
                champs_maj = uploader_fichier_webdev(session, url_courante, soup_courante, champ, chemin_formatte)
                payload_final.update(champs_maj)
                print(f"✅ Fichier reçu par le serveur : {champs_maj}")

        # --- SÉLECTION D'UNE LIGNE DE TABLEAU (AJAX) : avant le clic sur Modification / Suppression ---
        if "selection_ligne" in etape:
            table = etape["selection_ligne"]["table"]
            critere = {col: formater(val, donnees_plates) for col, val in etape["selection_ligne"]["critere"].items()}
            numero = selectionner_ligne_table(session, url_courante, soup_courante, table, critere,
                                              etape["selection_ligne"].get("evenement_ajax"))
            print(f"👉 Ligne {numero + 1} du tableau {table} sélectionnée ({critere})")

        # --- TRAITEMENTS SERVEUR "AU CHANGEMENT" (AJAX) : ce que le navigateur déclenche quand on modifie un champ ---
        for evenement in etape.get("evenements_ajax", []):
            valeurs = {cle: valeur for cle, valeur in payload_final.items() if not cle.startswith('WD_')}
            executer_evenement_ajax(session, url_courante, soup_courante, evenement["alias"], evenement["evenement"], valeurs)
            print(f"⚡ Traitement « au changement » de {evenement['alias']} exécuté côté serveur.")

        # Mémorise la valeur affichée de chaque champ modifié, avant de l'envoyer (pour la note de suivi)
        for cle, valeur_brute in etape["requete"].items():
            variable = re.fullmatch(r'\{([^{}]+)\}', valeur_brute) if isinstance(valeur_brute, str) else None
            if not variable or variable.group(1) not in champs_modifies or variable.group(1) in etat['anciennes_valeurs']:
                continue
            balise = soup_courante.find(['input', 'select', 'textarea'], {'name': cle})
            if balise is None:
                continue
            if balise.name == 'select':
                option_choisie = balise.find('option', selected=True)
                ancienne = option_choisie.get_text(strip=True) if option_choisie else ''
            else:
                ancienne = balise.get_text() if balise.name == 'textarea' else balise.get('value', '')
            etat['anciennes_valeurs'][variable.group(1)] = '' if ancienne.strip('-') == '' else ancienne

        # 3. EXÉCUTION
        reponse, soup_courante = soumettre_page_webdev(session, url_courante, soup_courante, payload_final, fichiers_finaux)
        url_courante = reponse.url
        etat['url'], etat['soup'] = url_courante, soup_courante  # Pour la déconnexion en cas d'arrêt

        # Très important pour ne pas bloquer les fichiers sur votre ordinateur
        if fichiers_finaux:
            for fichier_ouvert in fichiers_finaux.values():
                fichier_ouvert.close()

        # Recherche d'un client (case "Clients Actifs" A24) : personne dans cette catégorie → l'autre catégorie
        if etape["requete"].get('A24') == '{activite_actuelle}':
            url_courante, soup_courante = rechercher_client_autre_activite(payload_final, donnees_plates, session,
                                                                           url_courante, soup_courante, etat)

        # 4. L'AUDIT DE SÉCURITÉ POST-ACTION
        audit = etape.get("audit", {})

        if "champs_modifies" in audit:
            valeurs_zr = valeurs_zones_repetees(str(soup_courante))
            for champ, valeur_attendue_brute in audit["champs_modifies"].items():

                # On utilise également le dictionnaire aplati pour vérifier
                valeur_attendue = formater(str(valeur_attendue_brute), donnees_plates) if isinstance(valeur_attendue_brute, str) else str(valeur_attendue_brute)
                if valeur_attendue == '' and audit.get("ignorer_vides"):
                    continue  # Champ non fourni dans l'ordre : sa valeur a été conservée, rien à vérifier

                balise = soup_courante.find(['input', 'select'], {'name': champ})

                if not balise and champ in valeurs_zr:
                    if valeurs_zr[champ] != valeur_attendue:
                        print(f"🛑 ÉCHEC D'ÉCRITURE : Le champ {champ} contient '{valeurs_zr[champ]}' au lieu de '{valeur_attendue}'.")
                        sys.exit("Arrêt de sécurité.")
                    print(f"✅ SUCCÈS : Le champ {champ} a bien enregistré la valeur '{valeur_attendue}'.")
                elif balise:
                    valeur_reelle = ""
                    if balise.name == 'input':
                        valeur_reelle = balise.get('value', '')
                    elif balise.name == 'select':
                        option_choisie = balise.find('option', selected=True)
                        valeur_reelle = option_choisie.get('value', '') if option_choisie else ''

                    if valeur_reelle == valeur_attendue:
                        print(f"✅ SUCCÈS : Le champ {champ} a bien enregistré la valeur '{valeur_reelle}'.")
                    else:
                        print(f"🛑 ÉCHEC D'ÉCRITURE : Le champ {champ} contient '{valeur_reelle}' au lieu de '{valeur_attendue}'.")
                        sys.exit("Arrêt de sécurité.")
                else:
                    print(f"⚠️ ATTENTION : Le champ {champ} a disparu de l'écran après le clic.")

        if "titre_page" in audit:
                titre_actuel = soup_courante.title.string if soup_courante.title else ""
                if audit["titre_page"].lower() not in titre_actuel.lower():
                    print(f"🛑 ERREUR DE NAVIGATION : On attendait une page avec '{audit['titre_page']}', mais on est sur '{titre_actuel}'.")
                    sys.exit("Arrêt de sécurité.")
                else:
                    print("✅ Navigation confirmée.")

        for type_audit in ("ligne_presente", "ligne_absente"):
            if type_audit in audit:
                table = audit[type_audit]["table"]
                critere = {col: formater(val, donnees_plates) for col, val in audit[type_audit]["critere"].items()}
                trouvees, _ = chercher_lignes_table(str(soup_courante), table, critere)
                if (type_audit == "ligne_presente") != bool(trouvees):
                    print(f"🛑 ÉCHEC D'ÉCRITURE : {len(trouvees)} ligne(s) {critere} dans le tableau {table} ({type_audit} attendue).")
                    sys.exit("Arrêt de sécurité.")
                print(f"✅ SUCCÈS : Tableau {table} vérifié ({type_audit} : {critere}).")

        # Recherche qui doit désigner UNE seule ligne : 0 ou plusieurs résultats → arrêt sans rien sélectionner
        if "ligne_unique" in audit:
            unique = audit["ligne_unique"]
            critere = {col: formater(val, donnees_plates) for col, val in unique["critere"].items()}
            trouvees, lignes = chercher_lignes_table(str(soup_courante), unique["table"], critere)
            element = unique.get("element", "ligne")
            sans_critere = all(not donnees_plates.get(champ) for champ in unique.get("premiere_si_vides", []))
            if trouvees and (len(trouvees) == 1 or sans_critere):
                print(f"✅ SUCCÈS : {element} trouvée" + (" (la plus récente, aucun critère précis)" if len(trouvees) > 1 else "") + ".")
            else:
                filtres = {k: donnees_plates[k] for k in unique.get("criteres_affiches", []) if donnees_plates.get(k)}
                if not trouvees:
                    print(f"🛑 AUCUNE {element.upper()} ne correspond aux critères {filtres}.")
                else:
                    print(f"🛑 {len(trouvees)} {element.upper()}S correspondent aux critères {filtres} :")
                    for i in trouvees[:20]:
                        print("   - " + " | ".join(f"{titre} {lignes[i].get(col, '')}"
                                                  for titre, col in unique.get("colonnes_affichees", {}).items()))
                print(f"   Par sécurité, aucune {element} n'est sélectionnée : précisez les critères (numéro, date, montant).")
                sys.exit("Arrêt de sécurité.")

        # Lecture de champs de la page (sans rien envoyer), ex. l'adresse mail de la fiche client : etat['lectures']
        for champ, variable in etape.get("lire", {}).items():
            balise = soup_courante.find('input', {'name': champ})
            etat.setdefault('lectures', {})[variable] = balise.get('value', '').strip() if balise else ''

        # 5. TÉLÉCHARGEMENT DU FICHIER GÉNÉRÉ PAR LE SERVEUR (ex: duplicata de facture)
        if "telechargement" in etape:
            telechargement = etape["telechargement"]
            morceaux = []
            for champ in telechargement["nom"]:
                balise = soup_courante.find('input', {'name': champ})
                valeur = balise.get('value', '').strip() if balise else ''
                if not valeur:
                    sys.exit(f"🛑 ERREUR : Le champ {champ} (nom du fichier) est vide sur la page.")
                morceaux.append(re.sub(r'[^\w-]+', '_', valeur.replace('/', '-')).strip('_'))
            contenu = telecharger_fichier_webdev(session, url_courante, soup_courante, telechargement["champ"])
            if telechargement.get("extension") == ".pdf" and not contenu.startswith(b'%PDF'):
                sys.exit("🛑 ERREUR : Le fichier reçu n'est pas un PDF.")
            os.makedirs(telechargement["dossier"], exist_ok=True)
            nom_fichier = telechargement.get("prefixe", '') + '_'.join(morceaux) + telechargement.get("extension", '')
            chemin_local = os.path.join(telechargement["dossier"], nom_fichier)
            with open(chemin_local, 'wb') as fichier:
                fichier.write(contenu)
            etat.setdefault('fichiers', []).append(chemin_local)
            print(f"✅ SUCCÈS : Fichier enregistré : {chemin_local} ({len(contenu)} octets).")

        # 6. RECETTE RÉPÉTÉE POUR CHAQUE LIGNE TROUVÉE (ex : duplicata de toutes les factures d'une période)
        if "pour_chaque_ligne" in etape:
            url_courante, soup_courante = executer_pour_chaque_ligne(etape["pour_chaque_ligne"], ordre, donnees_plates,
                                                                     session, url_courante, soup_courante, etat)

    return url_courante, soup_courante


def action_cherche_client(action):
    """L'action passe-t-elle par la recherche de client (page "Gestion des clients", case A24) ?"""
    return any(etape.get("requete", {}).get('A24') == '{activite_actuelle}' for etape in CATALOGUE_ACTIONS.get(action, []))


def rechercher_client_autre_activite(payload, donnees_plates, session, url_courante, soup_courante, etat):
    """Après une recherche de client : si le tableau des résultats est vide, relance la même recherche dans l'autre
    catégorie (clients actifs ↔ inactifs), sauf si le mail a précisé l'activité. Personne dans les deux → arrêt."""
    libelles = {"1": "actifs", "0": "inactifs"}
    client = {k: v for k, v in (("code", payload.get('A28', '')), ("nom", payload.get('A29', ''))) if v}
    if lire_table_webdev(str(soup_courante), TABLE_CLIENTS):
        etat['activite_client'] = payload['A24']
        return url_courante, soup_courante
    if not donnees_plates.get("activite_automatique"):
        print(f"🛑 CLIENT INTROUVABLE parmi les clients {libelles[payload['A24']]} (catégorie précisée dans le mail) : {client}.")
        sys.exit("Arrêt de sécurité.")
    autre = ACTIVITE_SECOURS[payload['A24']]
    print(f"🔎 Aucun client {client} parmi les clients {libelles[payload['A24']]} : "
          f"nouvelle recherche parmi les clients {libelles[autre]}.")
    reponse, soup_courante = soumettre_page_webdev(session, url_courante, soup_courante, dict(payload, A24=autre))
    url_courante = reponse.url
    etat['url'], etat['soup'] = url_courante, soup_courante
    if not lire_table_webdev(str(soup_courante), TABLE_CLIENTS):
        print(f"🛑 CLIENT INTROUVABLE : aucun client {client} parmi les clients actifs ni inactifs.")
        sys.exit("Arrêt de sécurité.")
    print(f"✅ Client trouvé parmi les clients {libelles[autre]}.")
    donnees_plates["activite_actuelle"] = etat['activite_client'] = autre
    return url_courante, soup_courante


def executer_pour_chaque_ligne(boucle, ordre, donnees_plates, session, url_courante, soup_courante, etat):
    """Liste les lignes du tableau qui correspondent au critère, puis joue la recette boucle["action"] pour chacune,
    avec sa valeur (ex : numéro de facture). Rien n'est lancé si aucune ligne, trop de lignes, ou plusieurs clients."""
    element = boucle.get("element", "ligne")
    trouvees, lignes = chercher_lignes_table(str(soup_courante), boucle["table"], boucle["critere"])
    selection = [lignes[i] for i in trouvees if lignes[i].get(boucle["colonne"], '').strip()]
    valeurs = list(dict.fromkeys(ligne[boucle["colonne"]].strip() for ligne in selection))
    clients = {ligne.get(boucle.get("colonne_client", ''), '').strip() for ligne in selection} - {''}
    filtres = {k: donnees_plates[k] for k in boucle.get("criteres_affiches", []) if donnees_plates.get(k)}

    def lister():
        for ligne in selection[:40]:
            print("   - " + " | ".join(f"{titre} {ligne.get(col, '')}" for titre, col in boucle.get("colonnes_affichees", {}).items()))

    if not valeurs:
        print(f"🛑 AUCUNE {element.upper()} ne correspond aux critères {filtres}.")
        print(f"   Par sécurité, aucune {element} n'est téléchargée : vérifiez le client et la période.")
        sys.exit("Arrêt de sécurité.")
    if len(clients) > 1:
        print(f"🛑 Les {element}s trouvées appartiennent à {len(clients)} clients différents ({', '.join(sorted(clients))}) :")
        lister()
        print(f"   Par sécurité, aucune {element} n'est téléchargée : précisez le code client.")
        sys.exit("Arrêt de sécurité.")
    if len(valeurs) > boucle["max"]:
        print(f"🛑 {len(valeurs)} {element.upper()}S correspondent aux critères {filtres} (maximum {boucle['max']}) :")
        lister()
        print(f"   Par sécurité, aucune {element} n'est téléchargée : réduisez la période.")
        sys.exit("Arrêt de sécurité.")

    print(f"✅ SUCCÈS : {len(valeurs)} {element}(s) trouvée(s) : {', '.join(valeurs)}")
    code_client = next(iter(clients)) if len(clients) == 1 else ordre.get("code_client", "")
    for numero, valeur in enumerate(valeurs, start=1):
        print(f"\n••• {element.capitalize()} {numero}/{len(valeurs)} : {valeur} •••")
        sous_ordre = {"action": boucle["action"], "justification": ordre.get("justification", ""),
                      "activite_actuelle": ordre.get("activite_actuelle", "0"),
                      # Client désigné par son code exact (lu dans le tableau) : aucune ambiguïté sur le nom
                      "nom_client": "" if code_client else ordre.get("nom_client", ""), "code_client": code_client,
                      boucle["dossier"]: {boucle["variable"]: valeur}}
        url_courante, soup_courante = executer_recette(sous_ordre, session, url_courante, soup_courante, etat)
    return url_courante, soup_courante


class SuiviErreurs:
    """Recopie l'affichage à l'écran et garde les messages d'arrêt (🛑) de l'ordre en cours, pour le journal Excel."""
    def __init__(self, flux):
        self.flux, self.lignes, self.texte = flux, [], ""
    def write(self, texte):
        self.texte = (self.texte + texte)[-5000:]
        self.lignes += [ligne.strip() for ligne in texte.splitlines() if '🛑' in ligne or ligne.startswith('   - N°')]
        return self.flux.write(texte)
    def flush(self):
        self.flux.flush()


def prendre_verrou():
    """Attend que personne d'autre ne soit connecté à EGESYS (EGESYS refuse deux connexions : ERR_ALREADYCONNECTED).
    Le verrou est libéré automatiquement par le système à la fin du processus, même en cas de plantage."""
    import time
    os.makedirs(os.path.dirname(FICHIER_VERROU), exist_ok=True)
    fichier = open(FICHIER_VERROU, 'a+')
    debut = time.time()
    while True:
        try:
            if sys.platform == 'win32':
                import msvcrt
                fichier.seek(0)
                msvcrt.locking(fichier.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fichier, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fichier  # À garder ouvert jusqu'à la fin
        except OSError:
            if time.time() - debut > ATTENTE_VERROU:
                sys.exit(f"🛑 ERREUR : Une autre exécution EGESYS est en cours depuis plus de {ATTENTE_VERROU // 60} min.")
            if time.time() - debut < 3:
                print("⏳ Une autre exécution EGESYS est en cours : attente de sa fin...")
            time.sleep(3)


def ecrire_resultats(resultats, fichiers):
    """Résultat ordre par ordre, au format JSON (pour workflow.py / Power Automate)."""
    if not FICHIER_RESULTATS:
        return
    try:
        with open(FICHIER_RESULTATS, 'w', encoding='utf-8') as sortie:
            json.dump({"ordres": resultats, "fichiers": [os.path.basename(f) for f in fichiers]}, sortie,
                      ensure_ascii=False, indent=2)
    except OSError as erreur:
        print(f"⚠️  Fichier de résultats non écrit ({erreur}).")


if __name__ == "__main__":
    # Windows : console / redirection pas en UTF-8 par défaut, les emojis feraient planter le script
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    # Les ordres viennent d'un fichier JSON (un ordre ou une liste d'ordres), sinon de l'exemple ordre_ia ci-dessus.
    # Usage : python script_egesys.py cas_essai.json
    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding='utf-8') as fichier_ordres:
            ordres = json.load(fichier_ordres)
    else:
        ordres = ordre_ia
    if isinstance(ordres, dict):
        ordres = [ordres]

    identifiant = os.environ.get('EGESYS_IDENTIFIANT')
    mot_de_passe = os.environ.get('EGESYS_MDP')
    if not identifiant or not mot_de_passe:
        sys.exit("🛑 ERREUR : Variables d'environnement EGESYS_IDENTIFIANT et EGESYS_MDP non définies.")
    verrou = prendre_verrou()
    session, url_courante, soup_courante = connexion_egesys(identifiant, mot_de_passe)
    etat = {'url': url_courante, 'soup': soup_courante}
    resultats = [{"numero": numero, "action": ordre.get("action", ""), "client": client_de(ordre),
                  "resultat": "Non exécuté", "detail": "Arrêt sur un ordre précédent.", "modification": ""}
                 for numero, ordre in enumerate(ordres, start=1)]

    def consigner(numero, ordre, resultat, detail, source, modification):
        """Journal Excel + fichier de résultats."""
        ajouter_au_journal(ordre, resultat, detail, source, modification)
        resultats[numero - 1].update(resultat=resultat, detail=detail, modification=modification)

    def infos_factures(numero, fichiers_ordre):
        """Duplicatas récupérés : factures (code client, n°) et adresse mail de la fiche (A205, lue pendant la note de
        suivi) → mail au client avec ses factures (workflow/compte_rendu.py, mail_client)."""
        factures = factures_des_fichiers(fichiers_ordre)
        if factures:
            resultats[numero - 1].update(
                factures=[{"code_client": code, "numero_facture": numero_facture} for code, numero_facture in factures],
                mail_client=etat.get('lectures', {}).get('mail_client', ''))

    # Journal Excel : nom du mail d'origine (dossier de travail du workflow) ou du fichier d'ordres
    chemin_ordres = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else 'ordre_ia'
    source = os.path.basename(os.path.dirname(chemin_ordres)) if os.path.basename(chemin_ordres).startswith('reponse_copilot') \
        else os.path.basename(chemin_ordres)
    suivi = SuiviErreurs(sys.stdout)
    sys.stdout = suivi

    try:
        for numero, ordre in enumerate(ordres, start=1):
            print(f"\n==================== ORDRE {numero}/{len(ordres)} ====================")
            ordre_original = copy.deepcopy(ordre)  # preparer_donnees traduit l'ordre sur place
            suivi.lignes.clear(); suivi.texte = ""
            etape_en_cours = "exécution"
            modification = "\n".join(lignes_modification(ordre_original, {}))  # Valeurs demandées, si arrêt
            nb_fichiers_avant = len(etat.get('fichiers', []))
            etat.pop('activite_client', None)  # Catégorie (actif / inactif) où le client de CET ordre sera trouvé
            try:
                url_courante, soup_courante = executer_recette(ordre, session, url_courante, soup_courante, etat)
                modification = "\n".join(lignes_modification(ordre_original, etat.get('anciennes_valeurs', {})))
                # Duplicatas : la "modification" de l'ordre = les PDF récupérés (réponse au mail, journal Excel)
                fichiers_ordre = etat.get('fichiers', [])[nb_fichiers_avant:]
                if fichiers_ordre:
                    modification = "\n".join(f"Duplicata PDF récupéré : {os.path.basename(f)}" for f in fichiers_ordre)
                detail = ""
                note = note_de_suivi(ordre_original, etat.get('anciennes_valeurs', {}), fichiers_ordre)
                etat['lectures'] = {}  # Adresse mail lue sur la fiche pendant la note de suivi (factures)
                if note:
                    etape_en_cours = "note de suivi"
                    # La note est posée sur le client trouvé : même catégorie (actif / inactif), sans nouvelle recherche
                    if etat.get('activite_client') and action_cherche_client(ordre_original["action"]):
                        note["activite_actuelle"] = etat['activite_client']
                    print(f"\n📝 Note de suivi : « {note['note']['sujet']} »")
                    url_courante, soup_courante = executer_recette(note, session, url_courante, soup_courante, etat)
                    detail = f"Note de suivi ajoutée : « {note['note']['sujet']} »"
                consigner(numero, ordre_original, "Réussite", detail, source, modification)
                infos_factures(numero, fichiers_ordre)
            except SystemExit as arret:
                messages = " | ".join(suivi.lignes) or str(arret)
                fichiers_ordre = etat.get('fichiers', [])[nb_fichiers_avant:]
                if fichiers_ordre and etape_en_cours != "note de suivi":  # Factures récupérées avant l'arrêt
                    messages = (f"{len(fichiers_ordre)} duplicata(s) récupéré(s) avant l'arrêt "
                                f"({', '.join(os.path.basename(f) for f in fichiers_ordre)}) | {messages}")
                if etape_en_cours == "note de suivi":
                    consigner(numero, ordre_original, "Erreur",
                              f"Modification faite, mais note de suivi non ajoutée : {messages}", source, modification)
                    infos_factures(numero, fichiers_ordre)  # Factures récupérées : le client peut quand même les recevoir
                elif "Par sécurité, aucune" in suivi.texte:
                    consigner(numero, ordre_original, "Non exécuté", messages, source, modification)
                else:
                    consigner(numero, ordre_original, "Erreur", messages, source, modification)
                raise
        print(f"\n🎉 {len(ordres)} ordre(s) exécuté(s) avec succès.")
    finally:
        # Toujours exécuté, même après un arrêt de sécurité (sys.exit)
        try:
            deconnexion_egesys(session, etat['url'], etat['soup'])
        finally:
            ecrire_resultats(resultats, etat.get('fichiers', []))
            verrou.close()
