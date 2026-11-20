# Exemples de mails traités

Chaque exemple montre l'identifiant du message et l'expéditeur fournis dans la requête, le mail reçu, puis le JSON attendu ("id_message" et "expediteur" recopiés à l'identique, juste après "resume"). Les noms et numéros sont fictifs.

## Exemple 1 : duplicata d'une facture

ID du message fourni dans la requête : `AAMkXXXXXXXXXXXX01`
Expéditeur fourni dans la requête : `gestionnaire@exemple.fr`

Mail reçu :

> Objet : G++ Duplicata facture GAEC DUPONT
>
> Bonjour, le GAEC DUPONT (cheptel FR 12 345 678) a perdu sa facture du 28 février 2026.
> Pouvez-vous m'en sortir un duplicata ? Merci.

Points d'attention :
- Le numéro de cheptel est recopié sans espace ni « FR ».
- La date est mise au format JJ/MM/AAAA.

```json
{
  "resume": "Duplicata de la facture du 28/02/2026 du GAEC DUPONT.",
  "id_message": "AAMkXXXXXXXXXXXX01",
  "expediteur": "gestionnaire@exemple.fr",
  "ordres": [
    {
      "action": "telecharger_facture",
      "justification": "le GAEC DUPONT (cheptel FR 12 345 678) a perdu sa facture du 28 février 2026",
      "cheptel": "12345678",
      "nom_eleveur": "GAEC DUPONT",
      "date_facture": "28/02/2026"
    }
  ],
  "incertitudes": []
}
```

## Exemple 2 : création d'un espace adhérent web

ID du message fourni dans la requête : `AAMkXXXXXXXXXXXX02`
Expéditeur fourni dans la requête : `technicien@exemple.fr`

Mail reçu :

> Objet : G++ Accès internet M. MARTIN
>
> M. MARTIN, cheptel 87654321, voudrait avoir accès à son espace adhérent sur le site.
> Merci de lui créer ses identifiants.

Points d'attention :
- Le profil n'est pas cité : "profil" reste vide (le profil standard sera utilisé).

```json
{
  "resume": "Création de l'espace adhérent web de M. MARTIN.",
  "id_message": "AAMkXXXXXXXXXXXX02",
  "expediteur": "technicien@exemple.fr",
  "ordres": [
    {
      "action": "generer_espace_adherent",
      "justification": "M. MARTIN, cheptel 87654321, voudrait avoir accès à son espace adhérent sur le site.",
      "cheptel": "87654321",
      "nom_eleveur": "M. MARTIN",
      "profil": ""
    }
  ],
  "incertitudes": []
}
```

## Exemple 3 : éleveur désigné par son nom, dernière facture

ID du message fourni dans la requête : `AAMkXXXXXXXXXXXX03`
Expéditeur fourni dans la requête : `gestionnaire@exemple.fr`

Mail reçu :

> Objet : G++ facture
>
> Bonjour, pouvez-vous renvoyer à l'EARL DURAND sa dernière facture ? Merci.

Points d'attention :
- « sa dernière facture » : "telecharger_factures" avec "nombre_dernieres" = "1" (pas d'incertitude sur la date).
- Sans numéro de cheptel : "cheptel" vide et "nom_eleveur" recopié, SANS incertitude : le programme retrouve l'éleveur par son nom (s'il y en a plusieurs, il ne fait rien et le signale).

```json
{
  "resume": "Duplicata de la dernière facture de l'EARL DURAND.",
  "id_message": "AAMkXXXXXXXXXXXX03",
  "expediteur": "gestionnaire@exemple.fr",
  "ordres": [
    {
      "action": "telecharger_factures",
      "justification": "pouvez-vous renvoyer à l'EARL DURAND sa dernière facture ?",
      "cheptel": "",
      "nom_eleveur": "EARL DURAND",
      "periodes": "",
      "nombre_dernieres": "1"
    }
  ],
  "incertitudes": []
}
```

## Exemple 4 : duplicatas de toutes les factures d'une période et d'une date précise

ID du message fourni dans la requête : `AAMkXXXXXXXXXXXX05`
Expéditeur fourni dans la requête : `gestionnaire@exemple.fr`

Mail reçu :

> Objet : G++ factures EARL MOREAU
>
> Bonjour, l'EARL MOREAU (cheptel 23456789) voudrait recevoir toutes ses factures du premier trimestre 2026, ainsi que sa facture du 31 mai 2026. Merci !

Points d'attention :
- Plusieurs factures (période + date précise) : UN seul ordre « telecharger_factures », ce n'est pas une incertitude.
- « premier trimestre 2026 » = 01/01/2026 au 31/03/2026 ; la date précise s'ajoute après « ; ».

```json
{
  "resume": "Duplicatas des factures du 1er trimestre 2026 et de la facture du 31/05/2026 de l'EARL MOREAU.",
  "id_message": "AAMkXXXXXXXXXXXX05",
  "expediteur": "gestionnaire@exemple.fr",
  "ordres": [
    {
      "action": "telecharger_factures",
      "justification": "l'EARL MOREAU (cheptel 23456789) voudrait recevoir toutes ses factures du premier trimestre 2026, ainsi que sa facture du 31 mai 2026",
      "cheptel": "23456789",
      "nom_eleveur": "EARL MOREAU",
      "periodes": "01/01/2026 au 31/03/2026 ; 31/05/2026",
      "nombre_dernieres": ""
    }
  ],
  "incertitudes": []
}
```

## Exemple 4 bis : les dernières factures, sans date

ID du message fourni dans la requête : `AAMkXXXXXXXXXXXX06`
Expéditeur fourni dans la requête : `gestionnaire@exemple.fr`

Mail reçu :

> Objet : G++ factures
>
> Bonjour, le GAEC MARTIN (cheptel 34567890) voudrait ses trois dernières factures. Merci.

Points d'attention :
- « ses trois dernières factures » : "nombre_dernieres" = "3", "periodes" vide. Ce n'est pas une incertitude : le programme prend les 3 plus récentes du bilan.

```json
{
  "resume": "Duplicatas des 3 dernières factures du GAEC MARTIN.",
  "id_message": "AAMkXXXXXXXXXXXX06",
  "expediteur": "gestionnaire@exemple.fr",
  "ordres": [
    {
      "action": "telecharger_factures",
      "justification": "le GAEC MARTIN (cheptel 34567890) voudrait ses trois dernières factures.",
      "cheptel": "34567890",
      "nom_eleveur": "GAEC MARTIN",
      "periodes": "",
      "nombre_dernieres": "3"
    }
  ],
  "incertitudes": []
}
```

## Exemple 5 : demande hors périmètre

ID du message fourni dans la requête : `AAMkXXXXXXXXXXXX04`
Expéditeur fourni dans la requête : `gestionnaire@exemple.fr`

Mail reçu :

> Objet : G++ changement d'adresse
>
> Le cheptel 12345678 a changé d'adresse : 3 route du Moulin, 64000 PAU.

Points d'attention :
- Le changement d'adresse n'est pas une action GENICIA++ disponible : aucun ordre, une incertitude.

```json
{
  "resume": "Changement d'adresse du cheptel 12345678.",
  "id_message": "AAMkXXXXXXXXXXXX04",
  "expediteur": "gestionnaire@exemple.fr",
  "ordres": [],
  "incertitudes": [
    "Le changement d'adresse n'est pas une action disponible dans l'automatisation GENICIA++ : à faire à la main."
  ]
}
```
