# Automatisation EGESYS : du mail à l'exécution

Ce projet met à jour la base clients EGESYS (intranet SOGEN) à partir des mails reçus, et répond au mail avec le
résultat :

```
Mail reçu dans Outlook
   │  Power Automate envoie le mail (+ « ID du message » et « Expéditeur ») à l'agent Copilot
   ▼
Agent Copilot : traduit le mail en ordres JSON {resume, id_message, expediteur, ordres, incertitudes}
   │  Power Automate dépose le JSON (+ pièces jointes) dans OneDrive\pending\
   ▼
Workflow (sur le PC) : valide les ordres → exécute dans EGESYS → range dans completed\ ou error\
   │
   ▼
OneDrive\result\<nom>.json : {id_message, expediteur, objet, corps HTML}
   │  Power Automate répond au mail d'origine
   ▼
Réponse dans Outlook : ce qui a été fait, ce qui ne l'a pas été et pourquoi, que faire
```

Aucune action manuelle : tout (validation, connexion à EGESYS, saisie, vérification, déconnexion, réponse) est
automatique. Les cas douteux (incertitude de l'agent, coordonnées bancaires, facture ambiguë) ne sont **jamais**
exécutés : la réponse au mail explique quoi préciser.

L'exécution passe uniquement par des requêtes HTTP vers EGESYS (Python `requests` + BeautifulSoup) : pas de navigateur
piloté. Les données ne sortent pas de Microsoft 365 (agent Copilot, OneDrive, Power Automate) et du PC.

---

## 1. Ce que l'agent sait traiter

Le client est désigné par son **nom** (`nom_client`), son **code client** à 7 ou 8 chiffres (`code_client`), ou les deux.
Il est cherché d'abord parmi les clients **inactifs**, puis parmi les clients **actifs** s'il n'est pas trouvé (case
« Clients Actifs » de la recherche). Si le mail précise que le client est actif ou inactif, l'agent le note
(`activite_actuelle` = `1` ou `0`) et seule cette catégorie est cherchée. Introuvable dans les deux : arrêt, rien n'est modifié.

### Fiche client

| Action | Ce qui change dans EGESYS |
|---|---|
| `modifier_civilite_client` | Civilité (liste fermée : ENTREPRISE INDIVIDUELLE, G.A.E.C., E.A.R.L., S.C.E.A., …) |
| `modifier_nom_client` | Nom |
| `modifier_prenom_client` | Prénom |
| `modifier_responsable_client` | Responsable |
| `modifier_adresse_client` | Adresse, code postal, ville |
| `modifier_mail_client` | Adresse mail |
| `modifier_mail_comptable_client` | Adresse mail comptable |
| `modifier_telephone_fixe_client` | Téléphone fixe |
| `modifier_telephone_portable_client` | Téléphone portable |

### Modèle de règlement (dates d'application)

| Action | Ce qui change dans EGESYS |
|---|---|
| `ajouter_modèle_de_reglement_client` | Nouvelle date d'application : mode de règlement, échéance, famille de produits, compte général, banque, IBAN, BIC, RUM. Obligatoires : date, mode, échéance, famille. |
| `modifier_modèle_de_reglement_client` | Correction d'une date d'application **existante** (désignée par sa date). Les champs non fournis gardent leur valeur. |

Une date d'application ne peut **jamais** être supprimée (règle EGESYS) : l'agent la refuse et le signale.

### Note de suivi automatique

Après chaque action réussie (fiche client, modèle de règlement, document, duplicata de facture), le script ajoute une note sur la fiche :

- **Sujet** : ce qui a été modifié (« Modification adresse », « Nouveau modèle de règlement au 01/02/2027 »…) ;
- **Message** : date et heure, ancienne → nouvelle valeur de chaque champ (IBAN masqué), extrait du mail à l'origine ;
- **Factures** : sujet « Duplicata facture <n°> » ou « Duplicatas factures du <début> au <fin> », message = n° de chaque
  facture récupérée ; la note est posée sur le client de la facture (code lu sur le duplicata) ;
- **Agent** : GINESTE Thomas.

L'agent ne crée donc pas lui-même de note pour retracer une modification.

### Civilité

Depuis novembre 2026, les civilités de personne (MADAME, MONSIEUR, MADEMOISELLE, VEUVE…) ne s'utilisent plus :
une personne a la civilité **ENTREPRISE INDIVIDUELLE**, une société garde sa forme (G.A.E.C., E.A.R.L., S.C.E.A.…).
Un changement de nom ou de prénom ne change pas la civilité. Une demande « mettre Madame / Monsieur » donne
ENTREPRISE INDIVIDUELLE. Les anciennes civilités restent dans la liste EGESYS mais l'agent et le programme refusent de
les écrire.

### Documents

| Action | Ce qui change dans EGESYS |
|---|---|
| `ajouter_document_client` | Ajoute la pièce jointe du mail dans la fiche, avec un libellé et une famille (CONTRATS ou DOCUMENTS SOGEN) |
| `modifier_document_client` | Renomme, reclasse ou remplace le fichier d'un document existant (désigné par son libellé exact) |
| `supprimer_document_client` | Supprime un document existant (désigné par son libellé exact) |

### Notes

| Action | Ce qui change dans EGESYS |
|---|---|
| `ajouter_note_client` | Nouvelle note : sujet, message, date de rappel, confidentielle ou non, pièce jointe éventuelle |
| `modifier_note_client` | Modifie une note existante (désignée par son sujet, et sa date si connue) |
| `supprimer_note_client` | Supprime une note existante |

### Factures (lecture seule)

| Action | Résultat |
|---|---|
| `telecharger_facture_client` | Télécharge le **duplicata PDF** d'**une** facture validée en comptabilité. Rien n'est modifié dans EGESYS. |
| `telecharger_factures_client` | Télécharge le duplicata PDF de **toutes** les factures validées du client sur une **période** (« toutes les factures de mars », « du 1er trimestre »…). Rien n'est modifié dans EGESYS. |

**Une facture** — critères de recherche, tous facultatifs, recopiés du mail même s'ils sont approximatifs :

| Critère | Recherche dans EGESYS |
|---|---|
| Numéro de facture (13 chiffres) | Exact ; suffit à lui seul, même sans nom de client |
| Date de la facture | ± 3 jours |
| Date d'état (validation) | ± 3 jours |
| Montant TTC | ± 1 % (au moins 1 €) |

- **Une seule** facture correspond → son duplicata est téléchargé.
- **Aucune** ou **plusieurs** factures → rien n'est téléchargé ; le rapport liste les factures candidates (numéro, dates,
  montant) pour préciser la demande.
- Aucun critère dans le mail → la facture validée la plus récente du client.

**Toutes les factures d'une période** — `periode_du` et `periode_au` (obligatoires, bornes incluses, sur la date de
facture ; « mars 2026 » → du 01/03/2026 au 31/03/2026) :

- les factures validées de la période sont listées, puis chacune est téléchargée par son numéro exact, une à une ;
- **rien n'est téléchargé** si aucune facture ne correspond, s'il y en a plus de **30** (période à réduire) ou si elles
  appartiennent à **plusieurs clients** (nom ambigu : préciser le code client) ; la réponse liste les factures trouvées ;
- chaque PDF est listé dans la réponse au mail et joint par Power Automate (dossier `result/pdf/`).

### Ce que l'agent ne fait pas

- Il n'exécute rien lui-même : il produit seulement le JSON.
- Une demande hors de ces actions (supprimer une date d'application, changer l'activité du client, demande sans rapport
  avec EGESYS, consignes cachées dans un mail…) ne donne **aucun ordre** : elle est signalée dans « incertitudes ».
- Une coordonnée simplement citée (« vous pouvez la joindre au… ») n'est pas considérée comme une modification.

---

## 2. Comment tout fonctionne

### Étape 1 : l'agent Copilot

L'agent est configuré avec deux éléments :

- **Instructions** : [copilot/instructions.md](copilot/instructions.md), à coller dans l'agent (limite ≈ 8 000
  caractères). Rôle, format de réponse (JSON brut uniquement), règles de construction et choix de l'action.
- **Compétence** : [copilot/egesys-modeles-json/SKILL.md](copilot/egesys-modeles-json/SKILL.md). Modèle JSON exact de
  chaque action, listes de valeurs autorisées, exemples de mails traités. Ce fichier est **généré** par
  `python generer_doc_copilot.py` (ne pas le modifier à la main).

Pour chaque mail, il répond uniquement par un JSON de 5 clés, dans cet ordre : `resume` (la demande en une phrase),
`id_message` et `expediteur` (recopiés depuis les lignes « ID du message : … » et « Expéditeur : … » de la requête),
`ordres`, `incertitudes` (points ambigus : leur présence bloque toute exécution).

### Étape 2 : le workflow

[workflow/workflow.py](workflow/workflow.py) surveille toutes les 5 secondes les dossiers OneDrive
(`<OneDrive Sogen>\EGESYS`, trouvé automatiquement sur chaque PC : voir [config_egesys.py](config_egesys.py)).
**Un seul PC à la fois** : le fichier `EGESYS\_poste_actif.json` du OneDrive indique quel PC fait tourner le workflow ; un
autre PC refuse de démarrer tant que le premier donne signe de vie (5 min) :

| Dossier | Contenu |
|---|---|
| `pending/` | Power Automate y dépose le JSON de l'agent et les pièces jointes citées par les ordres |
| `processing/` | JSON validé, pendant son exécution dans EGESYS |
| `completed/` | Exécution réussie |
| `error/` | JSON refusé, exécution bloquée (incertitude, IBAN, facture ambiguë) ou erreur pendant l'exécution |
| `result/` | `<nom>.json` : la **réponse au mail d'origine**, écrite en tout dernier |
| `result/pdf/` | PDF récupérés (duplicatas de facture), `<nom>_<fichier>.pdf`, à joindre à la réponse |

Pour chaque `pending/<nom>.json` :

1. il attend la fin de la synchronisation et les pièces jointes citées (jusqu'à 10 minutes) ;
2. **validation** ([valider_ordres.py](valider_ordres.py), sans connexion) : structure exacte, valeurs des listes,
   champs obligatoires, IBAN (clé de contrôle), RUM, dates, présence des pièces jointes, incertitudes de l'agent ;
3. **garde-fou bancaire** : un ordre avec IBAN ou BIC n'est jamais exécuté automatiquement (risque de fraude au RIB) ;
4. **exécution** ([script_egesys.py](script_egesys.py)) : le JSON passe dans `processing/` le temps de l'exécution ;
5. **classement** dans `completed/` ou `error/`, puis **réponse** dans `result/`.

| Résultat | Code | Dossier | Exécuté dans EGESYS ? |
|---|---|---|---|
| Tout est correct | `EXECUTE` | `completed/` | Oui |
| Incertitude de l'agent ou ordre refusé par la validation | `REFUSE_VALIDATION` | `error/` | Non |
| Coordonnées bancaires (IBAN ou BIC) | `A_VERIFIER_BANQUE` | `error/` | Non : à confirmer auprès du client |
| Facture : aucune ou plusieurs correspondent | `A_PRECISER` | `error/` | Non (les factures possibles sont listées) |
| Arrêt de sécurité pendant l'exécution | `ERREUR_EXECUTION` | `error/` | Les ordres précédents l'ont été : lire la réponse |
| PC ou workflow arrêté pendant une exécution | `INTERROMPU` | `error/` | Inconnu : vérifier dans EGESYS (jamais relancé) |

Dans `completed/` ou `error/`, on trouve pour chaque mail : `<nom>.json` (réponse de l'agent), `<nom>_valide.json`,
`<nom>_rapport.txt` (rapport technique détaillé), les fichiers produits ou reçus préfixés par `<nom>_` (duplicata de
facture, pièces jointes) et `<nom>_resultat.json` (résultat technique : statut, code, message, résultat de chaque ordre).

**La réponse au mail** (`result/<nom>.json`, rédigée par [workflow/compte_rendu.py](workflow/compte_rendu.py)) :

```json
{
  "id_message": "AAMk…",
  "expediteur": "prenom.nom@exemple.fr",
  "objet": "EGESYS : Demande traitée",
  "corps": "<div …>… HTML mis en forme pour Outlook …</div>",
  "pdf": ["<nom>_facture_<n° client>_<n° facture>.pdf"],
  "client": {"mail": "…", "objet": "…", "corps": "…"}
}
```

L'objet dépend du résultat : « Demande traitée », « Demande partiellement traitée », « Précisions nécessaires »,
« Coordonnées bancaires à confirmer », « Facture à préciser », « Erreur lors du traitement », « Traitement interrompu, à
vérifier dans EGESYS », « Demande non traitée ». Le corps est en HTML (gras, souligné, couleurs, listes) et ne contient
aucun nom de fichier ni jargon : bilan coloré, demandes exécutées (ancienne → nouvelle valeur), demandes non exécutées
avec ce qui était demandé et la raison, points à clarifier, « Que faire ? ». Le flux Power Automate de réponse se
déclenche sur `result/`, insère `corps` tel quel dans la réponse et joint les fichiers de `result/pdf/` listés dans `pdf` (liste vide si aucun PDF). Les PDF sont copiés avant l'écriture du JSON : quand le flux se déclenche, ils sont déjà là. Une copie reste dans `completed/`.

**Mail au client avec ses factures** : l'utilisateur se contente de transférer le mail du client. Quand des duplicatas
ont été récupérés, le JSON contient aussi :

```json
"client": {"mail": "adresse de la fiche client", "objet": "SOGEN : duplicata de votre facture n° …", "corps": "<div …>…</div>"}
```

- L'adresse est lue dans la **fiche client EGESYS** (champ A205), au moment où la note de suivi est ajoutée. Elle ne vient
  jamais du mail : une facture n'est jamais envoyée à une adresse inconnue.
- `client.mail` est **vide** (rien à envoyer au client) si aucune facture n'a été récupérée, si la fiche n'a pas
  d'adresse valide, ou si les factures concernent plusieurs clients.
- Le message (objet « SOGEN : … », signé « Le service administratif de SOGEN ») se modifie dans
  `workflow/compte_rendu.py`, fonction `mail_client`. L'objet ne contient jamais « EGESYS ».
- Dans le flux de réponse, après la réponse à l'utilisateur et **avant** de supprimer les PDF de `result/pdf/` : condition
  « `client.mail` n'est pas vide » → « Envoyer un e-mail (V2) » : À = `client.mail`, Objet = `client.objet`,
  Corps = `client.corps`, pièces jointes = les mêmes PDF que la réponse.

**Journal Excel** : `journal_egesys.xlsx`, à la racine du OneDrive EGESYS, reçoit une ligne par ordre : date, action, client, valeurs
modifiées (« ancienne » → « nouvelle », IBAN masqué ; valeurs demandées si l'ordre n'a pas abouti), raison (extrait du
mail), résultat (Réussite / Erreur / Non exécuté, en couleur), détail, mail d'origine.

Exécuter à la main un mail bloqué, après vérification (PowerShell, dans le dossier du projet) :
```powershell
python script_egesys.py "$env:OneDriveCommercial\EGESYS\error\<nom>_valide.json"
```

### Étape 3 : l'exécution dans EGESYS

Le script rejoue le parcours d'un utilisateur, page par page, puis **vérifie** le résultat avant de passer à la suite :

- après une saisie, il relit les champs pour confirmer que la valeur est enregistrée ;
- pour les modèles de règlement et les documents, il clique sur « Enregistrer » puis **rouvre la fiche** pour
  vérifier que la ligne existe vraiment en base ;
- au moindre écart (mauvaise page, valeur non enregistrée, session expirée), il **s'arrête net** avec un message clair,
  sans continuer à l'aveugle ;
- il se **déconnecte toujours** à la fin, même après un arrêt (sinon EGESYS refuse les connexions suivantes) ;
- un verrou (`%LOCALAPPDATA%\EGESYS\connexion_egesys.lock`) garantit une seule connexion à la fois.

Les identifiants sont des variables d'environnement de l'utilisateur Windows (`EGESYS_IDENTIFIANT`, `EGESYS_MDP`),
enregistrées par `lancer_workflow.bat -Identifiants`. Ils ne figurent dans aucun fichier du projet.

Boutons dangereux jamais utilisés : Supprimer, Inverser l'état R/V et transferts comptables (page Factures),
Envoyer (page Détail facture, qui envoie la facture par mail au client).

---

## 3. Démarrer le workflow

Tout passe par `lancer_workflow.bat` (double-clic = lancement), dans le dossier du projet :

| Pour… | Commande (PowerShell, dans le dossier du projet) |
|---|---|
| **Première fois** : enregistrer les identifiants EGESYS (saisie masquée) | `.\lancer_workflow.bat -Identifiants` |
| Lancer en arrière-plan (fenêtre cachée, une seule instance) | `.\lancer_workflow.bat` ou double-clic |
| Lancer à chaque ouverture de session Windows | `.\lancer_workflow.bat -Installer` (retirer : `-Desinstaller`) |
| Savoir s'il tourne, et sur quel PC (+ fin du journal) | `.\lancer_workflow.bat -Etat` |
| Suivre le journal en direct | `Get-Content $env:LOCALAPPDATA\EGESYS\workflow.log -Wait -Tail 20 -Encoding UTF8` |
| Arrêter (vérifier d'abord que `processing/` est vide) | `.\lancer_workflow.bat -Arreter` |
| Lancer au premier plan, pour voir ce qu'il fait | `python workflow\workflow.py` (Ctrl+C pour arrêter) |
| Un seul passage | `python workflow\workflow.py --une-fois` |
| Vider le OneDrive (completed, error, result, result\pdf) | `python nettoyer_onedrive.py` ou double-clic sur `nettoyer_onedrive.bat` (supprime tout de suite, sans question ; `--simulation` pour seulement lister ; `--jours 30` pour garder le dernier mois) |

Les notifications s'affichent dans le centre de notifications Windows (émetteur « Windows PowerShell »).
Le PC doit être allumé, OneDrive synchronisé et le workflow lancé pour que les mails soient traités.

---

## 4. Fichiers du projet

| Fichier | Rôle |
|---|---|
| [workflow/workflow.py](workflow/workflow.py) | Surveillance de `pending/`, validation, garde-fous, exécution, classement, réponse, notifications |
| [workflow/compte_rendu.py](workflow/compte_rendu.py) | Rédaction de la réponse au mail (objet + corps HTML) |
| [script_egesys.py](script_egesys.py) | Correspondances des listes (`MAPPING_*`), **recettes** de chaque action (`CATALOGUE_ACTIONS`), exécution et contrôles |
| [moteur_egesys.py](moteur_egesys.py) | Moteur HTTP : connexion, navigation WebDev, upload et téléchargement de fichiers, lecture des tableaux, déconnexion |
| [valider_ordres.py](valider_ordres.py) | Validation hors ligne d'une réponse de l'agent ; lecture de `id_message` / `expediteur` |
| [journal_egesys.py](journal_egesys.py) | Journal Excel des ordres (OneDrive EGESYS\journal_egesys.xlsx) |
| [config_egesys.py](config_egesys.py) | Tous les emplacements : OneDrive EGESYS (trouvé automatiquement), journal Excel, dossier technique `%LOCALAPPDATA%\EGESYS` (verrous, travail, workflow.log) |
| [workflow/poste_actif.py](workflow/poste_actif.py) | Un seul PC à la fois (fichier `_poste_actif.json` dans le OneDrive EGESYS). Identique à celui de G++ |
| [extraire_ordres.py](extraire_ordres.py) | Schéma des ordres (utilisé par la validation et la compétence) ; extraction par l'API Claude en option |
| [generer_doc_copilot.py](generer_doc_copilot.py) | Génère la compétence SKILL.md de l'agent |
| [copilot/](copilot/) | Instructions de l'agent, compétence générée, exemples, 26 mails de test et réponses attendues |
| [comparer_reponse_copilot.py](comparer_reponse_copilot.py) | Compare une réponse de l'agent à la réponse attendue d'un mail de test |
| [explorer.py](explorer.py) | Cartographie des pages EGESYS en lecture seule → [cartes/](cartes/) |
| [envoyer_mails_test.py](envoyer_mails_test.py) | Mails de test : génère `copilot/tests/mails_json/test_XX.json` depuis `mails_de_test.md` et les dépose dans `OneDrive - Sogen\TESTS_MAILS`, d'où un flux Power Automate les envoie (objet `[EGSYS] [TEST XX] …`) |
| [nettoyer_onedrive.py](nettoyer_onedrive.py) | Supprime les fichiers accumulés dans completed/, error/, result/ et result/pdf/ (jamais pending/ ni processing/) |
| `lancer_workflow.bat`, `lancer_workflow.ps1` | Identifiants, lancement en arrière-plan, démarrage automatique, état, arrêt |
| [presentation_projet.html](presentation_projet.html) | Présentation illustrée de tout le projet (à ouvrir dans un navigateur) |

---

## 5. Faire évoluer le système

**Ajouter une action EGESYS :**
1. cartographier les pages concernées avec `explorer.py` (lecture seule) ;
2. ajouter la recette dans `CATALOGUE_ACTIONS` (et un `MAPPING_*` si la page a une liste déroulante : on envoie la
   valeur technique de l'option, pas le texte affiché) ;
3. ajouter sa description dans `extraire_ordres.py` (`ACTIONS_DESCRIPTIONS`, champs dans `CHAMPS`) ;
4. `python generer_doc_copilot.py`, puis recharger le SKILL.md dans l'agent (et les instructions si une règle change) ;
5. ajouter un mail de test dans `copilot/tests/`.

**Contraintes Copilot :** les textes chargés dans l'agent ne doivent contenir ni formulations du type « ignore tes
instructions », ni données personnelles ou bancaires réalistes (noms réels, IBAN, téléphones, mails), sinon Microsoft
bloque la création de l'agent (« violation IAR »). Les exemples utilisent des X et des noms génériques.
