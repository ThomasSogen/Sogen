"""Compare la réponse de l'agent Copilot à la réponse attendue d'un mail de test (aucune connexion).

Usage : python comparer_reponse_copilot.py copilot/tests/attendus/test_05.json reponse_copilot.txt
- La réponse peut être collée telle quelle (bloc ```json ... ```).
- Dans l'attendu, "*" = texte libre : toute valeur non vide est acceptée.
- La casse, les accents et les espaces ne comptent pas (« Pau » = « PAU », « 06 11 » = « 0611 »).
"""
import json
import sys
import unicodedata
from valider_ordres import lire_reponse
from extraire_ordres import CHAMPS_FACULTATIFS


def normaliser(valeur):
    texte = unicodedata.normalize('NFKD', str(valeur)).encode('ascii', 'ignore').decode().lower()
    return ''.join(texte.split())

def comparer_valeurs(attendu, obtenu, chemin, ecarts):
    if isinstance(attendu, dict):
        if not isinstance(obtenu, dict):
            ecarts.append(f"{chemin} : objet attendu, reçu {obtenu!r}")
            return
        for cle in sorted(set(attendu) | set(obtenu)):
            if cle not in obtenu:
                ecarts.append(f"{chemin}.{cle} : clé manquante")
            elif cle not in attendu:
                ecarts.append(f"{chemin}.{cle} : clé en trop")
            else:
                comparer_valeurs(attendu[cle], obtenu[cle], f"{chemin}.{cle}", ecarts)
    elif attendu == "*":
        if not str(obtenu).strip():
            ecarts.append(f"{chemin} : texte attendu, reçu vide")
    elif normaliser(attendu) != normaliser(obtenu):
        ecarts.append(f"{chemin} : attendu {attendu!r}, reçu {obtenu!r}")


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    with open(sys.argv[1], encoding='utf-8') as fichier:
        attendu = json.load(fichier)
    ordres, incertitudes, resume = lire_reponse(sys.argv[2])

    ecarts = []
    restants = list(ordres)
    for numero, ordre_attendu in enumerate(attendu["ordres"], start=1):
        candidat = next((o for o in restants if o.get("action") == ordre_attendu["action"]), None)
        if candidat is None:
            ecarts.append(f"ordre {numero} : action '{ordre_attendu['action']}' absente de la réponse")
            continue
        restants.remove(candidat)
        # Champ facultatif non précisé dans l'attendu : la réponse doit le laisser vide (ou l'omettre)
        for champ, defaut in CHAMPS_FACULTATIFS.items():
            if champ not in ordre_attendu and candidat.get(champ, defaut) == defaut:
                candidat = {cle: valeur for cle, valeur in candidat.items() if cle != champ}
        comparer_valeurs(ordre_attendu, candidat, ordre_attendu["action"], ecarts)
    for ordre in restants:
        ecarts.append(f"ordre en trop : '{ordre.get('action')}'")
    if bool(attendu["incertitudes"]) != bool(incertitudes):
        ecarts.append("incertitudes : " + ("au moins une attendue, aucune reçue" if attendu["incertitudes"]
                                           else f"aucune attendue, reçu {incertitudes}"))

    print(f"📨 {resume}")
    for incertitude in incertitudes:
        print(f"⚠️  {incertitude}")
    if ecarts:
        print(f"\n🛑 {len(ecarts)} écart(s) avec la réponse attendue :")
        for ecart in ecarts:
            print(f"   - {ecart}")
        sys.exit(1)
    print("\n✅ Réponse conforme à l'attendu.")


if __name__ == '__main__':
    # Windows : console / redirection pas en UTF-8 par défaut, les emojis feraient planter le script
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    main()
