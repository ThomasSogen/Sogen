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

## Exemple 4 bis : une facture sans le jour (seulement le mois)

ID du message fourni dans la requête : `AAMkXXXXXXXXXXXX08`
Expéditeur fourni dans la requête : `gestionnaire@exemple.fr`

Mail reçu :

> Bonjour, le client 1234567 voudrait sa facture de février 2026, il n'a pas la date exacte. Merci.

Points d'attention :
- UNE facture demandée, sans le jour : la période du mois dans "date_realisation".
- Ce n'est pas une incertitude : s'il y a plusieurs factures en février, le programme les envoie toutes.

```json
{
  "resume": "Duplicata de la facture de février 2026 du client 1234567.",
  "id_message": "AAMkXXXXXXXXXXXX08",
  "expediteur": "gestionnaire@exemple.fr",
  "ordres": [
    {
      "action": "telecharger_facture_client",
      "justification": "le client 1234567 voudrait sa facture de février 2026",
      "code_client": "1234567",
      "nom_client": "",
      "facture": {
        "date_etat": "",
        "date_realisation": "01/02/2026 au 28/02/2026",
        "montant": "",
        "numero_facture": ""
      }
    }
  ],
  "incertitudes": []
}
```

## Exemple 5 : duplicatas des factures d'un mois et d'une date précise

ID du message fourni dans la requête : `AAMkXXXXXXXXXXXX06`
Expéditeur fourni dans la requête : `gestionnaire@exemple.fr`

Mail reçu :

> Bonjour, M. Dupont souhaite recevoir un duplicata de toutes ses factures du mois de mars 2026, ainsi que de sa facture du 31 mai 2026. Merci.

Points d'attention :
- Plusieurs factures (période + date précise) : UN seul ordre « telecharger_factures_client », ce n'est pas une incertitude.
- « mars 2026 » = 01/03/2026 au 31/03/2026 ; la date précise s'ajoute après « ; ».

```json
{
  "resume": "Duplicatas des factures de mars 2026 et de la facture du 31/05/2026 pour M. Dupont.",
  "id_message": "AAMkXXXXXXXXXXXX06",
  "expediteur": "gestionnaire@exemple.fr",
  "ordres": [
    {
      "action": "telecharger_factures_client",
      "justification": "M. Dupont souhaite recevoir un duplicata de toutes ses factures du mois de mars 2026, ainsi que de sa facture du 31 mai 2026.",
      "code_client": "",
      "nom_client": "dupont",
      "factures": {
        "nombre_dernieres": "",
        "periodes": "01/03/2026 au 31/03/2026 ; 31/05/2026"
      }
    }
  ],
  "incertitudes": []
}
```

## Exemple 5 bis : les dernières factures, sans date

ID du message fourni dans la requête : `AAMkXXXXXXXXXXXX07`
Expéditeur fourni dans la requête : `gestionnaire@exemple.fr`

Mail reçu :

> Bonjour, le client 1234567 voudrait recevoir ses trois dernières factures. Merci.

Points d'attention :
- « ses trois dernières factures » : "nombre_dernieres" = "3", "periodes" vide. Ce n'est pas une incertitude : le programme prend les 3 plus récentes.
- « sa dernière facture » (une seule) → « telecharger_facture_client » sans critère (exemple 4).

```json
{
  "resume": "Duplicatas des 3 dernières factures du client 1234567.",
  "id_message": "AAMkXXXXXXXXXXXX07",
  "expediteur": "gestionnaire@exemple.fr",
  "ordres": [
    {
      "action": "telecharger_factures_client",
      "justification": "le client 1234567 voudrait recevoir ses trois dernières factures.",
      "code_client": "1234567",
      "nom_client": "",
      "factures": {
        "nombre_dernieres": "3",
        "periodes": ""
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
