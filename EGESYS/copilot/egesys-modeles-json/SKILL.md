---
name: egesys-modeles-json
description: "Modèles JSON, listes de valeurs et exemples EGESYS."
---

## Listes de valeurs autorisées

Pour ces champs, recopier EXACTEMENT une valeur de la liste (majuscules, espaces et accents compris).
Si aucune valeur ne correspond à ce que dit le mail : laisser "" et l'expliquer dans `incertitudes`.

### `civilite`

- `ASSOCIATION`
- `CAT`
- `CHAMBRE`
- `COMMUNEAUTE`
- `COOPERATIVE`
- `E.A.R.L.`
- `EIRL`
- `ELEVAGE`
- `ENTREPRISE INDIVIDUELLE`
- `ESAT`
- `E.U.R.L.`
- `G.A.E.C.`
- `G.F.A.`
- `G.I.E.`
- `INDIVISION`
- `LYCEE ENSEI. PROF. AGRICOLE`
- `ORGANISME`
- `S.C.E.A.`
- `SICA`
- `SOCIETE`
- `SOCIÉTÉ ANONYME`
- `SOCIETE ANONYME ETABLISSEMENT`
- `SOCIETE CIVILE`
- `SOCIETE CIVILE AGRICOLE`
- `SOCIÉTÉ CIVILE EXPLOITATION`
- `SOCIETE CIVILE LAITIERE`
- `SOCIETE DE FAIT`
- `SOCIETE PAR ACTION SIMPLIFIEE`
- `SOC RESP LIMITEE`
- `S.T.E.F.`

### `mode_de_reglement`

- `CHEQUES`
- `ESPECES`
- `PRELEVEMENTS`
- `TRAITES`
- `VIREMENT SOGEN`
- `VIREMENTS`

### `echeance`

- `CHEQUE A RECEPTION`
- `PRELEVEMENT AU 02`
- `PRELEVEMENT AU 05`
- `PRELEVEMENT AU 10`
- `PRELEVEMENT AU 11`
- `PRELEVEMENT AU 15`
- `PRELEVEMENT AU 20`
- `PRELEVEMENT AU 22`
- `PRELEVEMENT AU 23`
- `PRELEVEMENT AU 25`
- `PRELEVEMENT AU 30`

### `compte general`

- `411000 ---- Clients`
- `41110000 ---- Clients Ventes Biens ou PS`
- `450000 ---- Collectif organismes`
- `453100 ---- COLLECTIF ADHERENTS`
- `45310000 ---- COLLECTIF ADHERENTS`
- `46700000 ---- Compte debiteur ou crediteur`

### `modèle`

- `TOUTES FAMILLES`
- `IA`
- `DOSES DIVERS`
- `MINERAL`

### `famille`

- `CONTRATS`
- `DOCUMENTS SOGEN`

### `confidentiel`

- `0`
- `1`

### `activite_actuelle`

- `0`
- `1`

### Champs à ne jamais remplir

`compte auxiliaire` : ajouté(s) automatiquement par le validateur, ne pas l'écrire dans le JSON.

## Actions EGESYS disponibles

Chaque ordre du JSON correspond à UNE action ci-dessous. Recopier le modèle de l'action, puis remplir
uniquement les champs que le mail précise. Un champ non précisé reste "" (pour une modification : "" = inchangé).
Ne jamais ajouter, renommer ou retirer une clé.

### `modifier_civilite_client`

Changer la civilité du client. Champs obligatoires : client uniquement (`nom_client` ou `code_client`).

```json
{
  "action": "modifier_civilite_client",
  "justification": "",
  "activite_actuelle": "",
  "code_client": "",
  "nom_client": "",
  "nouvelle_valeur_client": {
    "civilite": ""
  }
}
```

### `modifier_nom_client`

Changer le nom du client. Champs obligatoires : client uniquement (`nom_client` ou `code_client`).

```json
{
  "action": "modifier_nom_client",
  "justification": "",
  "activite_actuelle": "",
  "code_client": "",
  "nom_client": "",
  "nouvelle_valeur_client": {
    "nom": ""
  }
}
```

### `modifier_prenom_client`

Changer le prénom du client. Champs obligatoires : client uniquement (`nom_client` ou `code_client`).

```json
{
  "action": "modifier_prenom_client",
  "justification": "",
  "activite_actuelle": "",
  "code_client": "",
  "nom_client": "",
  "nouvelle_valeur_client": {
    "prenom": ""
  }
}
```

### `modifier_responsable_client`

Changer le responsable du client. Champs obligatoires : client uniquement (`nom_client` ou `code_client`).

```json
{
  "action": "modifier_responsable_client",
  "justification": "",
  "activite_actuelle": "",
  "code_client": "",
  "nom_client": "",
  "nouvelle_valeur_client": {
    "responsable": ""
  }
}
```

### `modifier_adresse_client`

Changer l'adresse postale (adresse, code postal, ville). Champs obligatoires : client uniquement (`nom_client` ou `code_client`).

```json
{
  "action": "modifier_adresse_client",
  "justification": "",
  "activite_actuelle": "",
  "code_client": "",
  "nom_client": "",
  "nouvelle_valeur_client": {
    "adresse": "",
    "code_postal": "",
    "ville": ""
  }
}
```

### `modifier_mail_client`

Changer l'adresse mail du client. Champs obligatoires : client uniquement (`nom_client` ou `code_client`).

```json
{
  "action": "modifier_mail_client",
  "justification": "",
  "activite_actuelle": "",
  "code_client": "",
  "nom_client": "",
  "nouvelle_valeur_client": {
    "mail": ""
  }
}
```

### `modifier_telephone_fixe_client`

Changer le téléphone fixe. Champs obligatoires : client uniquement (`nom_client` ou `code_client`).

```json
{
  "action": "modifier_telephone_fixe_client",
  "justification": "",
  "activite_actuelle": "",
  "code_client": "",
  "nom_client": "",
  "nouvelle_valeur_client": {
    "telephone_fixe": ""
  }
}
```

### `modifier_telephone_portable_client`

Changer le téléphone portable. Champs obligatoires : client uniquement (`nom_client` ou `code_client`).

```json
{
  "action": "modifier_telephone_portable_client",
  "justification": "",
  "activite_actuelle": "",
  "code_client": "",
  "nom_client": "",
  "nouvelle_valeur_client": {
    "telephone_portable": ""
  }
}
```

### `modifier_mail_comptable_client`

Changer l'adresse mail comptable. Champs obligatoires : client uniquement (`nom_client` ou `code_client`).

```json
{
  "action": "modifier_mail_comptable_client",
  "justification": "",
  "activite_actuelle": "",
  "code_client": "",
  "nom_client": "",
  "nouvelle_valeur_client": {
    "mail_comptable": ""
  }
}
```

### `ajouter_modèle_de_reglement_client`

Créer une nouvelle date d'application de modèle de règlement (mode de règlement, échéance, RIB/IBAN, BIC, RUM...). À utiliser pour un changement de RIB ou de mode de paiement à une date donnée. Champs obligatoires : `date_d_application`, `mode_de_reglement`, `echeance`, `modèle`.

```json
{
  "action": "ajouter_modèle_de_reglement_client",
  "justification": "",
  "activite_actuelle": "",
  "code_client": "",
  "nom_client": "",
  "modèle_de_reglement": {
    "bic": "",
    "compte general": "",
    "date_d_application": "",
    "domiciliation": "",
    "domiciliation_2": "",
    "echeance": "",
    "iban": "",
    "mode_de_reglement": "",
    "modèle": "",
    "rum": ""
  }
}
```

### `modifier_modèle_de_reglement_client`

Corriger une date d'application de modèle de règlement EXISTANTE (date_cible). Seulement si le mail demande explicitement de corriger un modèle déjà saisi. Champs obligatoires : `date_cible`.

```json
{
  "action": "modifier_modèle_de_reglement_client",
  "justification": "",
  "activite_actuelle": "",
  "code_client": "",
  "date_cible": "",
  "nom_client": "",
  "modèle_de_reglement": {
    "bic": "",
    "compte general": "",
    "domiciliation": "",
    "domiciliation_2": "",
    "echeance": "",
    "iban": "",
    "mode_de_reglement": "",
    "modèle": "",
    "rum": ""
  }
}
```

### `ajouter_document_client`

Ajouter un document (pièce jointe du mail) dans la fiche client, avec un libellé et une famille. Champs obligatoires : `libellé`, `chemin`, `famille`.

```json
{
  "action": "ajouter_document_client",
  "justification": "",
  "activite_actuelle": "",
  "code_client": "",
  "nom_client": "",
  "document": {
    "chemin": "",
    "famille": "",
    "libellé": ""
  }
}
```

### `modifier_document_client`

Modifier un document existant (identifié par son libellé) : nouveau libellé, nouvelle famille et/ou nouveau fichier. Champs obligatoires : `libelle_cible`.

```json
{
  "action": "modifier_document_client",
  "justification": "",
  "activite_actuelle": "",
  "code_client": "",
  "nom_client": "",
  "document": {
    "chemin": "",
    "famille": "",
    "libellé": ""
  },
  "document_cible": {
    "libelle_cible": ""
  }
}
```

### `supprimer_document_client`

Supprimer un document existant, identifié par son libellé exact. Champs obligatoires : `libelle_cible`.

```json
{
  "action": "supprimer_document_client",
  "justification": "",
  "activite_actuelle": "",
  "code_client": "",
  "nom_client": "",
  "document_cible": {
    "libelle_cible": ""
  }
}
```

### `ajouter_note_client`

Ajouter une note sur la fiche client (sujet, message, pièce jointe éventuelle). Champs obligatoires : `sujet`, `message`.

```json
{
  "action": "ajouter_note_client",
  "justification": "",
  "activite_actuelle": "",
  "code_client": "",
  "nom_client": "",
  "note": {
    "confidentiel": "",
    "date_de_rappel": "",
    "message": "",
    "piece_jointe": "",
    "sujet": ""
  }
}
```

### `modifier_note_client`

Modifier une note existante, identifiée par son sujet (et sa date si connue). Champs obligatoires : `sujet_cible`.

```json
{
  "action": "modifier_note_client",
  "justification": "",
  "activite_actuelle": "",
  "code_client": "",
  "nom_client": "",
  "note": {
    "confidentiel": "",
    "date_de_rappel": "",
    "message": "",
    "piece_jointe": "",
    "sujet": ""
  },
  "note_cible": {
    "date_cible": "",
    "sujet_cible": ""
  }
}
```

### `supprimer_note_client`

Supprimer une note existante, identifiée par son sujet (et sa date si connue). Champs obligatoires : `sujet_cible`.

```json
{
  "action": "supprimer_note_client",
  "justification": "",
  "activite_actuelle": "",
  "code_client": "",
  "nom_client": "",
  "note_cible": {
    "date_cible": "",
    "sujet_cible": ""
  }
}
```

### `telecharger_facture_client`

Enregistrer le duplicata PDF d'UNE facture validée du client (aucune modification dans EGESYS). Sans critère de facture : la plus récente. Champs obligatoires : client uniquement (`nom_client` ou `code_client`).

```json
{
  "action": "telecharger_facture_client",
  "justification": "",
  "code_client": "",
  "nom_client": "",
  "facture": {
    "date_etat": "",
    "date_realisation": "",
    "montant": "",
    "numero_facture": ""
  }
}
```

### `telecharger_factures_client`

Enregistrer le duplicata PDF de TOUTES les factures validées du client sur une période (ex : un mois, un trimestre, une année ; 30 factures maximum). Aucune modification dans EGESYS. Champs obligatoires : `periode_du`, `periode_au`.

```json
{
  "action": "telecharger_factures_client",
  "justification": "",
  "code_client": "",
  "nom_client": "",
  "factures": {
    "periode_au": "",
    "periode_du": ""
  }
}
```

## Description des champs

| Champ | Emplacement | Description | Valeurs |
|---|---|---|---|
| `justification` | racine | Extrait exact du mail qui justifie cet ordre. | texte libre |
| `activite_actuelle` | racine | '1' si le mail dit que le client est actif, '0' s'il est inactif (ancien client, a cessé son activité...), sinon "" : le programme cherche alors dans les deux catégories. | voir « Listes de valeurs autorisées » |
| `code_client` | racine | Code client EGESYS (7 ou 8 chiffres, sans espace) s'il est cité dans le mail, sinon vide. « Cheptel » et « numéro d'élevage » désignent aussi le code client. | texte libre |
| `nom_client` | racine | Nom de famille du client en minuscules, tel qu'on le chercherait dans EGESYS (ex: 'martin'). | texte libre |
| `civilite` | nouvelle_valeur_client | Nouvelle civilité. | voir « Listes de valeurs autorisées » |
| `nom` | nouvelle_valeur_client | Nouveau nom. | texte libre |
| `prenom` | nouvelle_valeur_client | Nouveau prénom. | texte libre |
| `responsable` | nouvelle_valeur_client | Nouveau responsable. | texte libre |
| `adresse` | nouvelle_valeur_client | Nouvelle adresse (numéro et rue). | texte libre |
| `code_postal` | nouvelle_valeur_client | Nouveau code postal. | texte libre |
| `ville` | nouvelle_valeur_client | Nouvelle ville, en MAJUSCULES. | texte libre |
| `mail` | nouvelle_valeur_client | Nouvelle adresse mail. | texte libre |
| `telephone_fixe` | nouvelle_valeur_client | Nouveau téléphone fixe, 10 chiffres sans espace. | texte libre |
| `telephone_portable` | nouvelle_valeur_client | Nouveau téléphone portable, 10 chiffres sans espace. | texte libre |
| `mail_comptable` | nouvelle_valeur_client | Nouvelle adresse mail comptable. | texte libre |
| `bic` | modèle_de_reglement | BIC / code SWIFT. | texte libre |
| `compte general` | modèle_de_reglement | Compte général comptable. | voir « Listes de valeurs autorisées » |
| `date_d_application` | modèle_de_reglement | Date d'application JJ/MM/AAAA. | texte libre |
| `domiciliation` | modèle_de_reglement | Banque (1re ligne de domiciliation). | texte libre |
| `domiciliation_2` | modèle_de_reglement | Agence (2e ligne de domiciliation). | texte libre |
| `echeance` | modèle_de_reglement | Échéance. | voir « Listes de valeurs autorisées » |
| `iban` | modèle_de_reglement | IBAN complet tel qu'écrit dans le mail. | texte libre |
| `mode_de_reglement` | modèle_de_reglement | Mode de règlement. | voir « Listes de valeurs autorisées » |
| `modèle` | modèle_de_reglement | Famille de produits concernée par le modèle. | voir « Listes de valeurs autorisées » |
| `rum` | modèle_de_reglement | Référence unique de mandat (15 caractères maximum). | texte libre |
| `date_cible` | racine | Date d'application existante à corriger, JJ/MM/AAAA. | texte libre |
| `chemin` | document | Nom EXACT de la pièce jointe à ajouter comme document (pdf, doc, docx, xls, xlsx). | texte libre |
| `famille` | document | Famille du document : CONTRATS pour un contrat ou un mandat signé, sinon DOCUMENTS SOGEN. | voir « Listes de valeurs autorisées » |
| `libellé` | document | Libellé du document (nouveau libellé en cas de modification). | texte libre |
| `libelle_cible` | document_cible | Libellé EXACT du document existant visé. | texte libre |
| `confidentiel` | note | '1' si la note est confidentielle, '0' sinon. | voir « Listes de valeurs autorisées » |
| `date_de_rappel` | note | Date de rappel JJ/MM/AAAA. | texte libre |
| `message` | note | Texte de la note. | texte libre |
| `piece_jointe` | note | Nom EXACT d'une pièce jointe du mail à attacher à la note. | texte libre |
| `sujet` | note | Sujet de la note (nouveau sujet en cas de modification). | texte libre |
| `sujet_cible` | note_cible | Sujet de la note existante visée. | texte libre |
| `date_etat` | facture | Date d'état (validation) de la facture JJ/MM/AAAA, même approximative. | texte libre |
| `date_realisation` | facture | Date de réalisation (date) de la facture JJ/MM/AAAA, même approximative. | texte libre |
| `montant` | facture | Montant TTC de la facture (ex : 652,49), même approximatif. | texte libre |
| `numero_facture` | facture | Numéro de facture complet (13 chiffres, ex : 4500000012345) s'il est cité, sinon vide. | texte libre |
| `periode_au` | factures | Dernier jour de la période des factures demandées, JJ/MM/AAAA (ex : mars 2026 → 31/03/2026). | texte libre |
| `periode_du` | factures | Premier jour de la période des factures demandées, JJ/MM/AAAA (ex : mars 2026 → 01/03/2026). | texte libre |

# Exemples de mails traités

Chaque exemple montre l'identifiant du message et l'expéditeur fournis dans la requête, le mail reçu, puis le JSON attendu ("id_message" et "expediteur" recopiés à l'identique, juste après "resume"). Les noms sont génériques.

## Exemple 1 : déménagement, nouveau portable et contrat à classer

ID du message fourni dans la requête : `AAMkXXXXXXXXXXXX01`
Expéditeur fourni dans la requête : `gestionnaire@exemple.fr`

Mail reçu (pièce jointe : `contrat_2027.pdf`) :

> Objet : Mise à jour fiche - Mme MARTIN
>
> Mme MARTIN a déménagé au 12 rue des Lilas, 64000 Pau.
> Son nouveau portable est le 06 XX XX XX XX, vous pouvez aussi la joindre par mail.
> Vous trouverez en pièce jointe son contrat signé, merci de le classer dans sa fiche.

Points d'attention :
- Le portable est explicitement « nouveau » : c'est une modification, en 10 caractères sans espace.
- Le mail est seulement cité comme moyen de contact : ce n'est PAS une modification.
- Un contrat signé va dans la famille CONTRATS.

```json
{
  "resume": "Nouvelle adresse, nouveau portable et contrat signé à classer pour Mme MARTIN.",
  "id_message": "AAMkXXXXXXXXXXXX01",
  "expediteur": "gestionnaire@exemple.fr",
  "ordres": [
    {
      "action": "modifier_adresse_client",
      "justification": "Mme MARTIN a déménagé au 12 rue des Lilas, 64000 Pau.",
      "activite_actuelle": "",
      "code_client": "",
      "nom_client": "martin",
      "nouvelle_valeur_client": {
        "adresse": "12 rue des Lilas",
        "code_postal": "64000",
        "ville": "PAU"
      }
    },
    {
      "action": "modifier_telephone_portable_client",
      "justification": "Son nouveau portable est le 06 XX XX XX XX",
      "activite_actuelle": "",
      "code_client": "",
      "nom_client": "martin",
      "nouvelle_valeur_client": {
        "telephone_portable": "06XXXXXXXX"
      }
    },
    {
      "action": "ajouter_document_client",
      "justification": "Vous trouverez en pièce jointe son contrat signé, merci de le classer dans sa fiche.",
      "activite_actuelle": "",
      "code_client": "",
      "nom_client": "martin",
      "document": {
        "chemin": "contrat_2027.pdf",
        "famille": "CONTRATS",
        "libellé": "Contrat signé"
      }
    }
  ],
  "incertitudes": []
}
```

## Exemple 2 : nouveau mode de règlement à une date donnée, avec note

ID du message fourni dans la requête : `AAMkXXXXXXXXXXXX02`
Expéditeur fourni dans la requête : `gestionnaire@exemple.fr`

Mail reçu :

> M. Dupont souhaite régler par chèque à réception à partir du 01/01/2027, pour toutes les familles de produits.
> Merci de noter qu'il nous a appelés à ce sujet.

Points d'attention :
- Un changement de mode de règlement à une date = nouvelle date d'application.
- Sans coordonnées bancaires dans le mail, les champs bancaires restent "".

```json
{
  "resume": "Passage au règlement par chèque à réception au 01/01/2027 pour M. Dupont, avec note de suivi.",
  "id_message": "AAMkXXXXXXXXXXXX02",
  "expediteur": "gestionnaire@exemple.fr",
  "ordres": [
    {
      "action": "ajouter_modèle_de_reglement_client",
      "justification": "M. Dupont souhaite régler par chèque à réception à partir du 01/01/2027, pour toutes les familles de produits.",
      "activite_actuelle": "",
      "code_client": "",
      "nom_client": "dupont",
      "modèle_de_reglement": {
        "bic": "",
        "compte general": "",
        "date_d_application": "01/01/2027",
        "domiciliation": "",
        "domiciliation_2": "",
        "echeance": "CHEQUE A RECEPTION",
        "iban": "",
        "mode_de_reglement": "CHEQUES",
        "modèle": "TOUTES FAMILLES",
        "rum": ""
      }
    },
    {
      "action": "ajouter_note_client",
      "justification": "Merci de noter qu'il nous a appelés à ce sujet.",
      "activite_actuelle": "",
      "code_client": "",
      "nom_client": "dupont",
      "note": {
        "confidentiel": "0",
        "date_de_rappel": "",
        "message": "Appel du client : règlement par chèque à réception à partir du 01/01/2027.",
        "piece_jointe": "",
        "sujet": "Mode de règlement"
      }
    }
  ],
  "incertitudes": []
}
```

## Exemple 3 : client désigné par son code client

ID du message fourni dans la requête : `AAMkXXXXXXXXXXXX03`
Expéditeur fourni dans la requête : `gestionnaire@exemple.fr`

Mail reçu :

> Bonjour, le client 1234567 a un nouveau téléphone fixe : 05 XX XX XX XX. Merci.

Points d'attention :
- Le client n'est désigné que par son code client (7 ou 8 chiffres) : `code_client` rempli, `nom_client` vide.

```json
{
  "resume": "Nouveau téléphone fixe pour le client de code 1234567.",
  "id_message": "AAMkXXXXXXXXXXXX03",
  "expediteur": "gestionnaire@exemple.fr",
  "ordres": [
    {
      "action": "modifier_telephone_fixe_client",
      "justification": "le client 1234567 a un nouveau téléphone fixe : 05 XX XX XX XX.",
      "activite_actuelle": "",
      "code_client": "1234567",
      "nom_client": "",
      "nouvelle_valeur_client": {
        "telephone_fixe": "05XXXXXXXX"
      }
    }
  ],
  "incertitudes": []
}
```

## Exemple 4 : duplicata d'une facture

ID du message fourni dans la requête : `AAMkXXXXXXXXXXXX04`
Expéditeur fourni dans la requête : `gestionnaire@exemple.fr`

Mail reçu :

> M. Dupont nous demande un duplicata de sa facture d'environ 120 € du début du mois de mars 2026.

Points d'attention :
- Les critères approximatifs sont recopiés tels quels : le programme cherche autour de la date et du montant.
- « début mars » sans jour précis : date approchée 01/03/2026.

```json
{
  "resume": "Duplicata de la facture d'environ 120 € de début mars 2026 pour M. Dupont.",
  "id_message": "AAMkXXXXXXXXXXXX04",
  "expediteur": "gestionnaire@exemple.fr",
  "ordres": [
    {
      "action": "telecharger_facture_client",
      "justification": "M. Dupont nous demande un duplicata de sa facture d'environ 120 € du début du mois de mars 2026.",
      "code_client": "",
      "nom_client": "dupont",
      "facture": {
        "date_etat": "",
        "date_realisation": "01/03/2026",
        "montant": "120,00",
        "numero_facture": ""
      }
    }
  ],
  "incertitudes": []
}
```

## Exemple 5 : duplicatas de toutes les factures d'un mois

ID du message fourni dans la requête : `AAMkXXXXXXXXXXXX06`
Expéditeur fourni dans la requête : `gestionnaire@exemple.fr`

Mail reçu :

> Bonjour, M. Dupont souhaite recevoir un duplicata de toutes ses factures du mois de mars 2026. Merci.

Points d'attention :
- Plusieurs factures sur une période : UN seul ordre « telecharger_factures_client », ce n'est pas une incertitude.
- « mars 2026 » = du premier au dernier jour du mois.

```json
{
  "resume": "Duplicatas de toutes les factures de mars 2026 pour M. Dupont.",
  "id_message": "AAMkXXXXXXXXXXXX06",
  "expediteur": "gestionnaire@exemple.fr",
  "ordres": [
    {
      "action": "telecharger_factures_client",
      "justification": "M. Dupont souhaite recevoir un duplicata de toutes ses factures du mois de mars 2026.",
      "code_client": "",
      "nom_client": "dupont",
      "factures": {
        "periode_au": "31/03/2026",
        "periode_du": "01/03/2026"
      }
    }
  ],
  "incertitudes": []
}
```

## Exemple 6 : mail sans demande de modification

ID du message fourni dans la requête : `AAMkXXXXXXXXXXXX05`
Expéditeur fourni dans la requête : `gestionnaire@exemple.fr`

Mail reçu :

> Bonjour, je vous confirme ma présence à l'assemblée générale du 20 novembre. Bonne journée.

```json
{
  "resume": "Confirmation de présence à l'assemblée générale, aucune modification EGESYS demandée.",
  "id_message": "AAMkXXXXXXXXXXXX05",
  "expediteur": "gestionnaire@exemple.fr",
  "ordres": [],
  "incertitudes": []
}
```
