"""Explorateur EGESYS : cartographie les pages WebDev en JSON (lecture seule).

Usage : python explorer.py            (Gestion des clients)
        python explorer.py factures   (Gestion des ventes > Factures)
Identifiants lus dans EGESYS_IDENTIFIANT / EGESYS_MDP. Les cartes sont écrites dans cartes/.
"""
import json
import os
import re
import sys
from moteur_egesys import connexion_egesys, deconnexion_egesys, soumettre_page_webdev, decoder_chaine_js, declarations_champs, analyser_xml_table

DOSSIER_CARTES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cartes')
CHAMPS_TECHNIQUES = ('WD_', 'TXNOM')


# ==========================================
# 1. ANALYSE D'UNE PAGE
# ==========================================

def _texte(balise):
    return re.sub(r'\s+', ' ', balise.get_text(' ', strip=True)) if balise else ''

def _libelle(soup, alias):
    """WebDev place le libellé d'un champ A9 dans la cellule 'lzA9'."""
    libelle = _texte(soup.find(id=f'lz{alias}'))
    if not libelle:
        libelle = _texte(soup.find('label', {'for': re.compile(rf'^{alias}(_\d+)?$')}))
    return libelle

def _traitements_js(html):
    """Découpe les DeclareTraitementEx("Axx", ...) par alias."""
    traitements = {}
    morceaux = re.split(r'(?=clWDUtil\.DeclareTraitementEx\(")', html)
    for morceau in morceaux:
        m = re.match(r'clWDUtil\.DeclareTraitementEx\("([^"]+)"', morceau)
        if m:
            fin = morceau.find('</script>')
            traitements[m.group(1)] = traitements.get(m.group(1), '') + (morceau[:fin] if fin != -1 else morceau)
    return traitements

def _effet_bouton(alias, code_js):
    """Déduit ce que fait un bouton à partir de son code navigateur."""
    effet = {}
    if re.search(r'_JSL\(_PAGE_,\s*["\']%s["\']' % alias, code_js):
        effet['type'] = 'soumission'          # POST classique avec WD_BUTTON_CLICK_
    elif re.search(r'_JAEE\(_PAGE_,\s*["\']%s["\']' % alias, code_js):
        effet['type'] = 'ajax'                # Exécution AJAX (pas de changement de page)
    elif 'Lance()' in code_js:
        effet['type'] = 'upload'
    delegue = re.findall(r'pfGetTraitement\("(A\d+)",0', code_js)
    if delegue:
        effet['declenche'] = sorted(set(d for d in delegue if d != alias))
    confirmations = re.findall(r'confirm\("((?:[^"\\]|\\.)*)"\)', code_js)
    if confirmations:
        effet['confirmation'] = [decoder_chaine_js(c) for c in confirmations]
    controles = re.findall(r'alert\("((?:[^"\\]|\\.)*)"\)', code_js)
    if controles:
        effet['controles_saisie'] = [decoder_chaine_js(c) for c in controles]
    return effet

def _analyser_table(xml):
    colonnes, lignes = analyser_xml_table(xml)
    visibles = [(titre, i) for i, (_, visible, titre) in enumerate(colonnes) if visible]
    apercu = [{titre: cellules[i] for titre, i in visibles if i < len(cellules)} for cellules in lignes[:5]]
    return {
        'colonnes': [{'alias': a, 'titre': t, 'visible': v} for a, v, t in colonnes],
        'nb_lignes': len(lignes),
        'apercu_lignes': apercu,
    }

def cartographier_page(soup, html, url=''):
    """Transforme une page WebDev en dictionnaire décrivant tout ce qu'on peut y saisir ou cliquer."""
    formulaire = soup.find('form')
    traitements = _traitements_js(html)
    proprietes = soup.find('input', {'name': 'WD_JSON_PROPRIETE_'})
    securises = set(json.loads(proprietes['value']).get('m_oProprietesSecurisees', {})) if proprietes and proprietes.get('value') else set()

    carte = {
        'titre': _texte(soup.title),
        'formulaire': formulaire.get('name') if formulaire else None,
        'champs': {},
        'boutons': {},
        'tableaux': {},
        'uploads': {},
        'etat_cache': [],
    }

    # --- Champs de saisie ---
    for balise in soup.find_all(['input', 'select', 'textarea']):
        nom = balise.get('name')
        type_balise = (balise.get('type') or balise.name).lower()
        if not nom or nom.startswith(CHAMPS_TECHNIQUES) or type_balise in ('button', 'submit', 'image', 'file'):
            continue
        if type_balise == 'hidden':
            if nom not in carte['etat_cache']:
                carte['etat_cache'].append(nom)
            continue
        champ = carte['champs'].setdefault(nom, {'libelle': _libelle(soup, nom), 'type': type_balise})
        if balise.has_attr('readonly') or balise.has_attr('disabled') or nom in securises:
            champ['lecture_seule'] = True
        if balise.get('placeholder'):
            champ['indication'] = balise['placeholder']
        if balise.name == 'select':
            champ['options'] = {_texte(o): o.get('value', '') for o in balise.find_all('option')}
            choisie = balise.find('option', selected=True)
            champ['valeur'] = choisie.get('value', '') if choisie else ''
        elif type_balise in ('checkbox', 'radio'):
            champ.setdefault('options', {})[_libelle(soup, balise.get('id', '')) or balise.get('value', '')] = balise.get('value', '')
            if balise.has_attr('checked'):
                champ['valeur'] = balise.get('value', '')
        elif balise.name == 'textarea':
            champ['valeur'] = balise.get_text()
        else:
            champ['valeur'] = balise.get('value', '')
    # Les champs vides de libellé dont l'état caché porte le même nom (cases à cocher) ne sont plus "cachés"
    carte['etat_cache'] = [n for n in carte['etat_cache'] if n not in carte['champs']]

    # --- Tableaux et uploads ---
    for alias, xml in declarations_champs(html, 'WDTable').items():
        carte['tableaux'][alias] = _analyser_table(xml)
    for alias, extensions in declarations_champs(html, 'WDUploadHTML5').items():
        carte['uploads'][alias] = {'extensions': re.findall(r'\*\.(\w+)', extensions)}

    # --- Boutons et liens WebDev ---
    for balise in soup.find_all(['a', 'button', 'input']):
        alias = balise.get('id') or ''
        href = balise.get('href', '') or ''
        if balise.name == 'input' and (balise.get('type') or '').lower() not in ('button', 'submit', 'image'):
            continue
        m = re.search(r"_JSL\(_PAGE_,'([^']+)'", href)
        if m:
            alias = m.group(1)
        if not re.match(r'^[AMI]\d+$', alias):  # I = champ d'une page interne (ex: I35 Factures)
            continue
        style = balise.get('style', '')
        image = re.search(r'background-image:url\([^)]*/([^/)]+)\)', style)
        bouton = carte['boutons'].setdefault(alias, {})
        texte = _texte(balise) or balise.get('value', '')
        if texte:
            bouton['texte'] = texte
        if balise.get('title'):
            bouton['infobulle'] = balise['title']
        if image and 'texte' not in bouton:
            bouton['image'] = image.group(1)
        effet = _effet_bouton(alias, traitements.get(alias, '') + href)
        if alias in carte['uploads']:
            effet['type'] = 'upload'
        bouton.update(effet)
    return carte


# ==========================================
# 2. NAVIGATION ET SAUVEGARDE
# ==========================================

def sauver_carte(nom, carte, chemin_clics):
    os.makedirs(DOSSIER_CARTES, exist_ok=True)
    carte = {'nom': nom, 'chemin_depuis_accueil': chemin_clics, **carte}
    with open(os.path.join(DOSSIER_CARTES, f'{nom}.json'), 'w', encoding='utf-8') as f:
        json.dump(carte, f, ensure_ascii=False, indent=2)
    print(f"🗺️  {nom} : '{carte['titre']}' — {len(carte['champs'])} champs, {len(carte['boutons'])} boutons, "
          f"{len(carte['tableaux'])} tableaux, {len(carte['uploads'])} uploads")


class Explorateur:
    """Garde UNE seule session ouverte et mémorise le chemin de clics depuis l'accueil."""

    def __init__(self):
        identifiant = os.environ.get('EGESYS_IDENTIFIANT')
        mot_de_passe = os.environ.get('EGESYS_MDP')
        if not identifiant or not mot_de_passe:
            sys.exit("🛑 ERREUR : Variables d'environnement EGESYS_IDENTIFIANT et EGESYS_MDP non définies.")
        self.session, self.url, self.soup = connexion_egesys(identifiant, mot_de_passe)
        self.html = self.soup.decode()
        self.chemin = []

    def cliquer(self, donnees, titre_attendu=None):
        reponse, self.soup = soumettre_page_webdev(self.session, self.url, self.soup, donnees)
        self.url, self.html = reponse.url, reponse.text
        self.chemin.append(donnees)
        titre = _texte(self.soup.title)
        if titre_attendu and titre_attendu.lower() not in titre.lower():
            sys.exit(f"🛑 ERREUR DE NAVIGATION : On attendait '{titre_attendu}', on est sur '{titre}'.")
        return self

    def cartographier(self, nom):
        carte = cartographier_page(self.soup, self.html, self.url)
        sauver_carte(nom, carte, list(self.chemin))
        return carte

    def deconnecter(self):
        deconnexion_egesys(self.session, self.url, self.soup)


# ==========================================
# 3. PARCOURS "GESTION DES CLIENTS"
# ==========================================

CLIENT_TEST = 'guitton'

OUVRIR_FICHE_CLIENT = [
    ('gestion_clients', {'WD_BUTTON_CLICK_': 'M3'}, 'Gestion des clients'),
    ('gestion_clients_resultats', {'A24': '0', 'A29': CLIENT_TEST, 'WD_BUTTON_CLICK_': 'A27'}, 'Gestion des clients'),
    ('fiche_client', {'WD_BUTTON_CLICK_': 'A4'}, 'Gestion des clients'),
]

# Sous-pages ouvertes depuis la fiche client (jamais validées par l'explorateur)
SOUS_PAGES_FICHE = {
    'modele_regroupement_creation': 'A324',
    'modele_regroupement_modification': 'A325',
    'document_creation': 'A153',
    'document_modification': 'A154',
    'note_creation': 'A177',
    'note_modification': 'A178',
}

def explorer_gestion_clients():
    explorateur = Explorateur()
    try:
        explorateur.cartographier('accueil')
        for nom, clic, titre in OUVRIR_FICHE_CLIENT:
            explorateur.cliquer(clic, titre).cartographier(nom)
    finally:
        explorateur.deconnecter()

    # Une session par sous-page : on ne revient jamais en arrière, on se déconnecte.
    for nom, bouton in SOUS_PAGES_FICHE.items():
        explorateur = Explorateur()
        try:
            for _, clic, titre in OUVRIR_FICHE_CLIENT:
                explorateur.cliquer(clic, titre)
            explorateur.cliquer({'WD_BUTTON_CLICK_': bouton}).cartographier(nom)
        finally:
            explorateur.deconnecter()


# ==========================================
# 4. PARCOURS "GESTION DES VENTES > FACTURES"
# ==========================================
# ⚠️ Lecture seule : on ne clique jamais Supprimer (A77), Inverser l'état (A65), les transferts compta (A23, A85...)
# ni Envoyer (A10 sur le détail = mail au client). Duplicata (A3) n'est pas cliqué ici : il génère un PDF.

CLIENT_TEST_FACTURES = 'brana'

OUVRIR_FACTURE = [
    ('menu_general', {'WD_BUTTON_CLICK_': 'A2'}, 'Menu Général'),  # Juste après la connexion (Tableau de bord)
    ('factures', {'WD_BUTTON_CLICK_': 'I35'}, 'Factures'),
    ('factures_resultats', {'A22': CLIENT_TEST_FACTURES, 'A51': '2', 'WD_BUTTON_CLICK_': 'A27'}, 'Factures'),
    ('facture_detail', {'WD_BUTTON_CLICK_': 'A11'}, 'Facture Detail'),
]

def explorer_factures():
    explorateur = Explorateur()
    try:
        for nom, clic, titre in OUVRIR_FACTURE:
            explorateur.cliquer(clic, titre).cartographier(nom)
    finally:
        explorateur.deconnecter()


if __name__ == '__main__':
    # Windows : console / redirection pas en UTF-8 par défaut, les emojis feraient planter le script
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    if 'factures' in sys.argv:
        explorer_factures()
    else:
        explorer_gestion_clients()
