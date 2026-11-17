---
name: genicia-modeles-json
description: "Modèles JSON, listes de valeurs et exemples des actions GENICIA++."
---

## Listes de valeurs autorisées

Pour ces champs, recopier EXACTEMENT une valeur de la liste (majuscules, espaces et signes compris).
Si le mail n'en parle pas : "". Si rien ne correspond à ce que dit le mail : "" et l'expliquer dans `incertitudes`.

### `profil`

- `ELWEB1 STANDARD`
- `PRWEB2 STANDART+`
- `PRWEB3 TECHNIQUE`
- `PRWEB4 TECHNIQUE+`
- `PRWEBA BASE`

Profil vide ("") : le profil `ELWEB1 STANDARD` est utilisé.

## Actions GENICIA++ disponibles

### `telecharger_facture`

Récupère le duplicata PDF d'une facture d'un éleveur (Bilan éleveur > F5 DETAILLER > F5 DUPLICATA). Lecture seule : rien n'est modifié dans GENICIA++.

Champs obligatoires : `cheptel`, `date_facture`

Champs :

- `justification` : extrait exact du mail qui justifie l'ordre
- `cheptel` : N° de cheptel de l'éleveur : 8 caractères sans espace (ex : 12345678). « Code client » et « numéro d'élevage » désignent aussi le n° de cheptel
- `nom_eleveur` : Nom de l'éleveur tel qu'écrit dans le mail (information seulement), sinon ""
- `date_facture` : Date de la facture, JJ/MM/AAAA

Modèle JSON (recopier toutes les clés, dans cet ordre) :

```json
{
  "action": "telecharger_facture",
  "justification": "",
  "cheptel": "",
  "nom_eleveur": "",
  "date_facture": ""
}
```

### `telecharger_factures`

Récupère le duplicata PDF de TOUTES les factures d'un éleveur sur une période (ex : un mois, un trimestre, une année ; 30 factures maximum). Lecture seule : rien n'est modifié dans GENICIA++.

Champs obligatoires : `cheptel`, `periode_du`, `periode_au`

Champs :

- `justification` : extrait exact du mail qui justifie l'ordre
- `cheptel` : N° de cheptel de l'éleveur : 8 caractères sans espace (ex : 12345678). « Code client » et « numéro d'élevage » désignent aussi le n° de cheptel
- `nom_eleveur` : Nom de l'éleveur tel qu'écrit dans le mail (information seulement), sinon ""
- `periode_du` : Premier jour de la période des factures demandées, JJ/MM/AAAA (ex : mars 2026 → 01/03/2026)
- `periode_au` : Dernier jour de la période des factures demandées, JJ/MM/AAAA (ex : mars 2026 → 31/03/2026)

Modèle JSON (recopier toutes les clés, dans cet ordre) :

```json
{
  "action": "telecharger_factures",
  "justification": "",
  "cheptel": "",
  "nom_eleveur": "",
  "periode_du": "",
  "periode_au": ""
}
```

### `generer_espace_adherent`

Ouvre les droits web de l'éleveur (profil choisi), génère un nouveau mot de passe, envoie par mail à l'éleveur ses identifiants (adresse de sa fiche) et l'abonne aux factures par mail sans pièce jointe. Modifie la fiche de l'éleveur.

Champs obligatoires : `cheptel`

Champs :

- `justification` : extrait exact du mail qui justifie l'ordre
- `cheptel` : N° de cheptel de l'éleveur : 8 caractères sans espace (ex : 12345678). « Code client » et « numéro d'élevage » désignent aussi le n° de cheptel
- `nom_eleveur` : Nom de l'éleveur tel qu'écrit dans le mail (information seulement), sinon ""
- `profil` : Profil web demandé (liste fermée) ; "" si le mail n'en parle pas → ELWEB1 STANDARD

Modèle JSON (recopier toutes les clés, dans cet ordre) :

```json
{
  "action": "generer_espace_adherent",
  "justification": "",
  "cheptel": "",
  "nom_eleveur": "",
  "profil": ""
}
```

## Exemples de mails traités

Chaque exemple montre l'identifiant du message et l'expéditeur fournis dans la requête, le mail reçu, puis le JSON attendu ("id_message" et "expediteur" recopiés à l'identique, juste après "resume"). Les noms et numéros sont fictifs.

### Exemple 1 : duplicata d'une facture

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

### Exemple 2 : création d'un espace adhérent web

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

### Exemple 3 : numéro de cheptel absent et date imprécise

ID du message fourni dans la requête : `AAMkXXXXXXXXXXXX03`
Expéditeur fourni dans la requête : `gestionnaire@exemple.fr`

Mail reçu :

> Objet : G++ facture
>
> Bonjour, pouvez-vous renvoyer à l'EARL DURAND sa dernière facture ? Merci.

Points d'attention :
- Sans numéro de cheptel ni date précise, l'ordre est créé avec des champs vides et deux incertitudes : rien ne sera exécuté.

```json
{
  "resume": "Duplicata de la dernière facture de l'EARL DURAND.",
  "id_message": "AAMkXXXXXXXXXXXX03",
  "expediteur": "gestionnaire@exemple.fr",
  "ordres": [
    {
      "action": "telecharger_facture",
      "justification": "pouvez-vous renvoyer à l'EARL DURAND sa dernière facture ?",
      "cheptel": "",
      "nom_eleveur": "EARL DURAND",
      "date_facture": ""
    }
  ],
  "incertitudes": [
    "Numéro de cheptel manquant pour l'EARL DURAND : le programme ne retrouve pas un éleveur par son nom. Indiquer le numéro de cheptel (8 caractères).",
    "Date exacte de la facture à préciser : « la dernière facture » ne suffit pas. Indiquer la date de la facture (JJ/MM/AAAA)."
  ]
}
```

### Exemple 4 : duplicatas de toutes les factures d'une période

ID du message fourni dans la requête : `AAMkXXXXXXXXXXXX05`
Expéditeur fourni dans la requête : `gestionnaire@exemple.fr`

Mail reçu :

> Objet : G++ factures EARL MOREAU
>
> Bonjour, l'EARL MOREAU (cheptel 23456789) voudrait recevoir toutes ses factures du premier trimestre 2026. Merci !

Points d'attention :
- Plusieurs factures sur une période : UN seul ordre « telecharger_factures », ce n'est pas une incertitude.
- « premier trimestre 2026 » = du 01/01/2026 au 31/03/2026.

```json
{
  "resume": "Duplicatas de toutes les factures du 1er trimestre 2026 de l'EARL MOREAU.",
  "id_message": "AAMkXXXXXXXXXXXX05",
  "expediteur": "gestionnaire@exemple.fr",
  "ordres": [
    {
      "action": "telecharger_factures",
      "justification": "l'EARL MOREAU (cheptel 23456789) voudrait recevoir toutes ses factures du premier trimestre 2026",
      "cheptel": "23456789",
      "nom_eleveur": "EARL MOREAU",
      "periode_du": "01/01/2026",
      "periode_au": "31/03/2026"
    }
  ],
  "incertitudes": []
}
```

### Exemple 5 : demande hors périmètre

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
