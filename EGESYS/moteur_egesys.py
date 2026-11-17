"""Moteur HTTP EGESYS (WebDev) : partagé par script_egesys.py et explorer.py."""
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import sys
import os
import re
import mimetypes
import html as html_lib


# ==========================================
# 1. LE MOTEUR (Fonctions de base)
# ==========================================

def soumettre_page_webdev(session, url_actuelle, soup_actuelle, donnees_action, fichiers_action=None):
    """Fonction universelle de navigation sécurisée pour EGESYS."""
    formulaire = soup_actuelle.find('form')
    action_url = formulaire.get('action') if formulaire else ""
    post_url = urljoin(url_actuelle, action_url) if action_url else url_actuelle

    payload = {}
    payload.update(donnees_action)
    session.headers.update({'Referer': url_actuelle})

    if fichiers_action:
        # S'il y a un fichier, on dit à requests de l'envoyer en mode multipart
        reponse = session.post(post_url, data=payload, files=fichiers_action)
    else:
        # Sinon, comportement normal
        reponse = session.post(post_url, data=payload)

    nouvelle_soup = BeautifulSoup(reponse.text, 'html.parser')

    if nouvelle_soup.find('input', {'name': 'A4'}):
        print(f"\n[URL du crash : {post_url}]")
        print(f"[Dernières données envoyées : {donnees_action}]")
        sys.exit("🛑 ERREUR CRITIQUE : Le serveur EGESYS a fermé la session. Arrêt du script.")

    return reponse, nouvelle_soup

TAILLE_MAX_UPLOAD = 5242880  # Au-delà, WebDev découpe le fichier en morceaux (non géré)

def uploader_fichier_webdev(session, url_actuelle, soup_actuelle, champ_upload, chemin_fichier):
    """Upload AJAX d'un champ Upload HTML5 WebDev (ex: pièce jointe d'une note).
    Le fichier part AVANT la validation du formulaire, via WD_ACTION_=UPLOADFICHIERFIN.
    Retourne les champs mis à jour par le serveur (ex: {'A9': 'C:\\...\\temp\\xxx_test.pdf'})."""
    formulaire = soup_actuelle.find('form')
    action_url = formulaire.get('action') if formulaire else ""
    post_url = urljoin(url_actuelle, action_url) if action_url else url_actuelle
    post_url += ('&' if '?' in post_url else '?') + f"WD_ACTION_=UPLOADFICHIERFIN&WD_BUTTON_CLICK_={champ_upload}"

    if os.path.getsize(chemin_fichier) > TAILLE_MAX_UPLOAD:
        sys.exit(f"🛑 ERREUR : {chemin_fichier} dépasse 5 Mo, l'envoi par morceaux WebDev n'est pas géré.")

    nom_fichier = os.path.basename(chemin_fichier)
    type_mime = mimetypes.guess_type(nom_fichier)[0] or 'application/octet-stream'
    session.headers.update({'Referer': url_actuelle})

    with open(chemin_fichier, 'rb') as fichier:
        # WebDev exige l'ordre exact des champs envoyés par le navigateur (Upload APRÈS Filedata)
        parties = [
            ('Filename', (None, nom_fichier)),
            ('FilePartBegin', (None, '1')),
            ('FilePartEnd', (None, '1')),
            ('Filedata', (nom_fichier, fichier, type_mime)),
            ('Upload', (None, 'Submit Query')),
        ]
        reponse = session.post(post_url, files=parties)

    # Réponse attendue : <WAJAX><CHAMP ALIAS="A9" TYPE="2"><PROP NUM="21">chemin temp</PROP></CHAMP></WAJAX>
    champs_maj = dict(re.findall(r'<CHAMP ALIAS="([^"]+)"[^>]*><PROP NUM="21">([^<]*)</PROP>', reponse.text))
    if not reponse.text.startswith('<?xml') or not champs_maj:
        print(f"\n[URL du crash : {post_url}]")
        print(f"[Réponse serveur : {reponse.text[:300]}]")
        sys.exit(f"🛑 ERREUR CRITIQUE : Le serveur EGESYS a refusé l'upload de {chemin_fichier}.")

    return champs_maj

def telecharger_fichier_webdev(session, url_actuelle, soup_actuelle, champ_chemin):
    """Télécharge le fichier généré par le serveur (ex: duplicata PDF d'une facture).
    WebDev écrit son chemin dans un champ caché (ex: A57 = '/EGESYS_WEB/temp/facture_xxx.pdf'), puis le navigateur l'ouvre.
    Retourne le contenu binaire du fichier."""
    balise = soup_actuelle.find('input', {'name': champ_chemin})
    chemin_serveur = balise.get('value', '') if balise else ''
    if not chemin_serveur:
        sys.exit(f"🛑 ERREUR : Le serveur n'a pas fourni de fichier dans le champ {champ_chemin}.")
    reponse = session.get(urljoin(url_actuelle, chemin_serveur), headers={'Referer': url_actuelle})
    if reponse.status_code != 200 or not reponse.content:
        sys.exit(f"🛑 ERREUR : Téléchargement de {chemin_serveur} impossible (code HTTP {reponse.status_code}).")
    return reponse.content

IMAGE_BOUTON_RETOUR ='btn_4304aa1a121c0c0c333192c4d900b680cf9d28ca.png'  # Flèche "retour" des sous-pages WebDev

def deconnexion_egesys(session, url_actuelle, soup_actuelle):
    """Clic sur 'Déconnexion' (M37). Depuis une sous-page (Note, Document...), on remonte d'abord
    avec la flèche retour. Sans déconnexion, les sessions s'accumulent → ERR_ALREADYCONNECTED."""
    try:
        for _ in range(3):
            if soup_actuelle.find(id='M37'):
                break
            retour = soup_actuelle.find(id=True, style=re.compile(re.escape(IMAGE_BOUTON_RETOUR)))
            formulaire = soup_actuelle.find('form')
            if not retour or not formulaire:
                break
            session.headers.update({'Referer': url_actuelle})
            reponse = session.post(urljoin(url_actuelle, formulaire.get('action', '')), data={'WD_BUTTON_CLICK_': retour['id']})
            url_actuelle, soup_actuelle = reponse.url, BeautifulSoup(reponse.text, 'html.parser')

        if soup_actuelle.find('input', {'name': 'A4'}):
            print("🔌 Session déjà fermée.")
            return
        formulaire = soup_actuelle.find('form')
        if not soup_actuelle.find(id='M37') or not formulaire:
            print("⚠️  Déconnexion impossible depuis cette page : la session restera ouverte jusqu'à son expiration.")
            return
        session.headers.update({'Referer': url_actuelle})
        session.post(urljoin(url_actuelle, formulaire.get('action', '')), data={'WD_BUTTON_CLICK_': 'M37'})
        print("🔌 Déconnecté.")
    except requests.RequestException as erreur:
        print(f"⚠️  Déconnexion échouée ({erreur}).")

def connexion_egesys(identifiant, mot_de_passe):
    """Initialise la session et connecte l'utilisateur."""
    session = requests.Session()
    login_url = "http://egesys.sogen.coop/eGESYS/eGESYS?p1=TEST"   # base de TEST
    
    reponse_init = session.get(login_url)
    soup = BeautifulSoup(reponse_init.text, 'html.parser')
    
    payload_login = {
        'A4': identifiant,
        'A2': mot_de_passe,
        'WD_BUTTON_CLICK_': 'A6'
    }
    reponse, soup = soumettre_page_webdev(session, login_url, soup, payload_login)
    return session, reponse.url, soup

# ==========================================
# TABLEAUX WEBDEV (lecture et sélection de ligne)
# ==========================================

def decoder_chaine_js(chaine):
    """Décode les échappements \\xHH, \\uHHHH, \\" et \\\\ d'une chaîne JavaScript générée par WebDev."""
    chaine = re.sub(r'\\x([0-9A-Fa-f]{2})', lambda m: chr(int(m.group(1), 16)), chaine)
    chaine = re.sub(r'\\u([0-9A-Fa-f]{4})', lambda m: chr(int(m.group(1), 16)), chaine)
    return chaine.replace('\\"', '"').replace("\\'", "'").replace('\\r', '\r').replace('\\n', '\n').replace('\\t', '\t').replace('\\\\', '\\')

def declarations_champs(html, classe):
    """Retourne {alias: premier paramètre décodé} pour clWDUtil.DeclareChamp("Axx",...,<classe>,[...])."""
    resultat = {}
    for m in re.finditer(r'DeclareChamp\("([^"]+)",void 0,void 0,void 0,%s,\["((?:[^"\\]|\\.)*)"' % classe, html):
        resultat.setdefault(m.group(1), decoder_chaine_js(m.group(2)))
    return resultat

def analyser_xml_table(xml):
    """Retourne (colonnes, lignes) : colonnes = [(alias, visible, titre)], lignes = [[cellules]] dans l'ordre affiché."""
    colonnes = []
    for balise in re.findall(r'<COLONNE ALIAS="[^"]+"[^>]*/>', xml):
        attributs = dict(re.findall(r'(\w+)="([^"]*)"', balise))
        titre = html_lib.unescape(attributs.get('TITRE') or attributs['ALIAS'])
        colonnes.append((attributs['ALIAS'], attributs.get('VISIBLE', '1') == '1', titre))
    lignes = [[html_lib.unescape(c).strip() for c in re.findall(r'<COLONNE>(.*?)</COLONNE>', contenu, re.S)]
              for contenu in re.findall(r'<LIGNE [^>]*>(.*?)</LIGNE>', xml, re.S)]
    return colonnes, lignes

def lire_table_webdev(html, table):
    """Lignes d'un tableau WebDev sous forme [{titre de colonne: valeur}] (colonnes cachées incluses)."""
    xml = declarations_champs(html, 'WDTable').get(table)
    if xml is None:
        sys.exit(f"🛑 ERREUR : Le tableau {table} est absent de la page.")
    colonnes, lignes = analyser_xml_table(xml)
    return [{titre: valeur for (_, _, titre), valeur in zip(colonnes, cellules)} for cellules in lignes]

def valeurs_zones_repetees(html):
    """Valeurs des champs des zones répétées (WDZR), générés en JavaScript donc absents du HTML.
    Retourne {name: valeur}, ex: {'zrl_1_A35': '5', 'zrl_1_A18': '21 820,00'}."""
    valeurs = {}
    for xml in declarations_champs(html, 'WDZR').values():
        for cdata in re.findall(r'<!\[CDATA\[(.*?)\]\]>', xml, re.S):
            for balise in BeautifulSoup(cdata, 'html.parser').find_all(['input', 'select', 'textarea']):
                if not balise.get('name'):
                    continue
                if balise.name == 'select':
                    option_choisie = balise.find('option', selected=True)
                    valeurs[balise['name']] = option_choisie.get('value', '') if option_choisie else ''
                elif balise.name == 'textarea':
                    valeurs[balise['name']] = balise.get_text()
                else:
                    valeurs[balise['name']] = balise.get('value', '')
    return valeurs

def chercher_lignes_table(html, table, critere):
    """Indices des lignes dont les colonnes correspondent au critère. Les valeurs vides du critère sont ignorées."""
    critere = {col: str(val).strip().lower() for col, val in critere.items() if str(val).strip()}
    if not critere:
        sys.exit(f"🛑 ERREUR : Critère vide pour chercher une ligne du tableau {table}.")
    lignes = lire_table_webdev(html, table)
    trouvees = [i for i, ligne in enumerate(lignes)
                if all(ligne.get(col, '').strip().lower() == val for col, val in critere.items())]
    return trouvees, lignes

def valeurs_formulaire(soup_actuelle):
    """Toutes les valeurs que le navigateur enverrait avec le formulaire (champs cachés compris)."""
    valeurs = {}
    formulaire = soup_actuelle.find('form')
    for balise in (formulaire.find_all(['input', 'select', 'textarea']) if formulaire else []):
        nom, type_balise = balise.get('name'), (balise.get('type') or '').lower()
        if not nom or type_balise in ('button', 'submit', 'image', 'file', 'reset'):
            continue
        if type_balise in ('checkbox', 'radio'):
            if balise.has_attr('checked'):
                valeurs[nom] = balise.get('value', '')
        elif balise.name == 'select':
            option_choisie = balise.find('option', selected=True)
            valeurs[nom] = option_choisie.get('value', '') if option_choisie else ''
        elif balise.name == 'textarea':
            valeurs[nom] = balise.get_text()
        else:
            valeurs[nom] = balise.get('value', '')
    return valeurs

def executer_evenement_ajax(session, url_actuelle, soup_actuelle, alias, evenement, donnees_sup=None):
    """Équivalent de _JAEE(_PAGE_, alias, evenement, 2, ...) : code serveur d'un champ exécuté en AJAX,
    avec toutes les valeurs de la page (WD_ACTION_=AJAXPAGE)."""
    formulaire = soup_actuelle.find('form')
    post_url = urljoin(url_actuelle, formulaire.get('action', '')) if formulaire else url_actuelle
    donnees = {'WD_ACTION_': 'AJAXPAGE', 'EXECUTE': str(evenement), 'WD_CONTEXTE_': alias}
    donnees.update({k: v for k, v in valeurs_formulaire(soup_actuelle).items() if k not in donnees})
    donnees.update(donnees_sup or {})
    session.headers.update({'Referer': url_actuelle})
    reponse = session.post(post_url, data=donnees)
    if not reponse.text.startswith('<?xml'):
        sys.exit(f"🛑 ERREUR CRITIQUE : Le serveur a refusé l'exécution AJAX de {alias}.")
    return reponse.text

def selectionner_ligne_table(session, url_actuelle, soup_actuelle, table, critere, evenement_ajax=None):
    """Sélectionne côté serveur LA ligne dont les colonnes correspondent au critère (ex: {'Sujet': 'test2'}).
    Le navigateur envoie un POST AJAX (WD_ACTION_=AJAXCHAMP) à chaque clic sur une ligne : le serveur
    mémorise la sélection, que le bouton suivant (Modification, Suppression...) utilise."""
    trouvees, lignes = chercher_lignes_table(str(soup_actuelle), table, critere)
    if len(trouvees) != 1:
        print(f"[Lignes du tableau {table} : {lignes}]")
        sys.exit(f"🛑 ERREUR : {len(trouvees)} ligne(s) du tableau {table} correspondent à {critere} (il en faut exactement 1).")

    formulaire = soup_actuelle.find('form')
    post_url = urljoin(url_actuelle, formulaire.get('action', '')) if formulaire else url_actuelle
    session.headers.update({'Referer': url_actuelle})
    reponse = session.post(post_url, data={
        'WD_ACTION_': 'AJAXCHAMP', 'CLICTABLE': table, table: str(trouvees[0]),
        'WD_TABLE_DEBUT_': '0', 'WD_TABLE_NOMBRE_': str(len(lignes)), 'WD_TABLE_COL_LIEN_': '',
    })
    if not reponse.text.startswith('<?xml'):
        sys.exit(f"🛑 ERREUR CRITIQUE : Le serveur a refusé la sélection de la ligne {trouvees[0]} du tableau {table}.")
    if evenement_ajax:
        # Certains tableaux déclenchent en plus un traitement AJAX au clic sur une ligne (ex: A143 → A156)
        executer_evenement_ajax(session, url_actuelle, soup_actuelle, evenement_ajax['alias'], evenement_ajax['evenement'],
                                {table: str(trouvees[0] + 1)})
    return trouvees[0]
