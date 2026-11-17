"""Compare la réponse de l'agent Copilot à la réponse attendue d'un mail de test (sans GENICIA++).

Usage : python comparer_reponse_copilot.py copilot/tests/attendus/test_01.json copilot/tests/reponses/test_01.txt
- La réponse peut être collée telle quelle (bloc ```json ... ```).
- Dans l'attendu, "*" = texte libre : toute valeur non vide est acceptée.
- Casse, accents et espaces ne comptent pas. Les ordres sont aussi passés au contrôle de ordres_genicia.py.
"""
import json
import sys
import unicodedata

from ordres_genicia import JsonIllisible, lire_reponse, valider_ordre


def normaliser(valeur):
    texte = unicodedata.normalize("NFKD", str(valeur)).encode("ascii", "ignore").decode().lower()
    return "".join(texte.split())


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    attendu = json.loads(open(sys.argv[1], encoding="utf-8").read())
    try:
        ordres, incertitudes, resume = lire_reponse(sys.argv[2])
    except JsonIllisible as erreur:
        sys.exit(f"🛑 Réponse illisible : {erreur}")

    ecarts = []
    restants = list(ordres)
    for numero, ordre_attendu in enumerate(attendu["ordres"], start=1):
        candidat = next((o for o in restants if isinstance(o, dict) and o.get("action") == ordre_attendu["action"]
                         and (normaliser(o.get("date_facture", "")) == normaliser(ordre_attendu.get("date_facture", ""))
                              or "date_facture" not in ordre_attendu)), None)
        candidat = candidat or next((o for o in restants if isinstance(o, dict)
                                     and o.get("action") == ordre_attendu["action"]), None)
        if candidat is None:
            ecarts.append(f"ordre {numero} : action '{ordre_attendu['action']}' absente de la réponse")
            continue
        restants.remove(candidat)
        if set(candidat) != set(ordre_attendu):
            ecarts.append(f"ordre {numero} : clés {sorted(candidat)} au lieu de {sorted(ordre_attendu)}")
        _, erreurs = valider_ordre(dict(candidat))
        for cle, valeur in ordre_attendu.items():
            obtenu = candidat.get(cle, "")
            if valeur == "*":
                if not str(obtenu).strip():
                    ecarts.append(f"ordre {numero}.{cle} : texte attendu, reçu vide")
            elif normaliser(valeur) != normaliser(obtenu):
                ecarts.append(f"ordre {numero}.{cle} : attendu {valeur!r}, reçu {obtenu!r}")
        if not attendu["incertitudes"]:
            ecarts += [f"ordre {numero} : refusé par la validation ({e})" for e in erreurs]
    ecarts += [f"ordre en trop : {o.get('action') if isinstance(o, dict) else o!r}" for o in restants]
    if bool(attendu["incertitudes"]) != bool(incertitudes):
        ecarts.append("incertitudes : " + ("au moins une attendue, aucune reçue" if attendu["incertitudes"]
                                           else f"aucune attendue, reçu {incertitudes}"))

    print(f"📨 {resume}")
    for incertitude in incertitudes:
        print(f"⚠️  {incertitude}")
    if ecarts:
        print("\n🛑 Écarts :\n" + "\n".join(f"  - {e}" for e in ecarts))
        sys.exit(1)
    print("\n✅ Réponse conforme à l'attendu.")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
