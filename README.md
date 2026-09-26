# Module mémoire EDUCATEE pour robot NAO

Ce projet a pour objectif de transformer les contenus pédagogiques du site [educatee.fr](https://www.educatee.fr) en une mémoire exploitable par un robot NAO.

Il fournit :
- une base de connaissances structurée au format JSON,
- un script Python pour injecter les données dans `ALMemory`,
- un dialogue QiChat compatible avec `ALDialog`,
- une simulation locale pour tester les réponses sans robot physique.

Le but est de permettre à NAO de répondre à des questions sur la seconde et le bac de français, en s'appuyant sur une base de connaissances fiable et organisée.

---

## Objectif du projet

Le robot NAO ne lit pas directement des documents texte classiques comme un humain. Il a besoin d'une mémoire structurée, adaptée à son environnement technique :

- `ALMemory` pour stocker des informations sous forme de clés hiérarchiques,
- `ALDialog` pour gérer des échanges oraux via QiChat,
- `ALTextToSpeech` pour parler clairement et naturellement,
- des contenus nettoyés pour être lisibles par la voix du robot.

Ce projet prépare précisément cette mémoire en réorganisant les contenus pédagogiques dans un format exploitable par NAO.

---

## Structure du dépôt

```text
Nao_project/
├── README.md
├── robot/
│   ├── main.py
│   ├── dialogue_bac_et_seconde.top
│   ├── nao_knowledge_base.json
│   └── memoire.json
└── dev/
    └── nao_memory_loader.py
```

### Fichiers principaux

- `robot/nao_knowledge_base.json` : ressource pédagogique structurée et base de réponses locales ; le chargeur envoie ses clés dans `ALMemory`.
- `robot/memoire.json` : mémoire utilisateur modifiable, initialement vide et séparée des réponses de base.
- `robot/dialogue_bac_et_seconde.top` : fichier QiChat chargé dans `ALDialog` sur le robot.
- `robot/main.py` : assistant autonome exécuté sur NAO ; il utilise les réponses locales et la base placée dans le même dossier, sans clé API ni bibliothèque Python tierce pour ce fonctionnement.
- `dev/nao_memory_loader.py` : outil lancé depuis l'ordinateur pour charger les ressources sur NAO ou simuler leur usage.

---

## Exemple de données mémorisées

Les clés sont rangées sous une arborescence de type :

```text
Educatee/
├── Meta/
├── Seconde/
│   ├── Projet
│   ├── Devise
│   ├── AnticipationBac
│   ├── PiliersReussite
│   └── SupportsCours
└── Bac/
    ├── Epreuves
    ├── Methode/
    └── Oeuvres/
```

Cela permet au robot d'accéder rapidement à des informations comme :
- les objectifs de la classe de seconde,
- les épreuves du bac,
- la méthode de commentaire, dissertation et oral,
- les œuvres étudiées.

---

## Fonctionnement

### 1. Assistant Python autonome sur le robot

Copiez le dossier `robot/` sur NAO et lancez `main.py` avec l'adresse locale du robot. Les réponses de base viennent de `nao_knowledge_base.json`, qui reste inchangé. Pour enregistrer un souvenir, dites « Souvenir, suivi de ce que tu veux que je retienne » ; le texte est ajouté dans `memoire.json`. Aucune clé API, connexion Internet ni exécution sur un autre ordinateur n'est nécessaire.

### 2. Dialogue oral

Le fichier `robot/dialogue_bac_et_seconde.top` définit les intentions, concepts et déclencheurs du robot. Il permet de gérer les interactions vocales avec un élève.

### 3. Simulation et outils de développement sur ordinateur

Le script facultatif `dev/nao_memory_loader.py` permet depuis un ordinateur d'envoyer les données dans `ALMemory` et de charger le topic QiChat dans `ALDialog`, ou de simuler les ressources localement. Il n'est pas nécessaire pour exécuter `robot/main.py` directement sur NAO.

---

## Prérequis

- Python 3 pour exécuter les scripts.
- Sur NAO : Python 3 et l'environnement NAOqi fourni avec le robot.
- Pour utiliser le chargeur depuis un ordinateur : accès réseau au robot et module `naoqi` du SDK.
- Facultatif : passer `--mistral-api-key` et disposer du paquet `requests` pour activer les réponses distantes aux questions inconnues. Sans cette option explicite, l'assistant reste local, même si une clé existe dans l'environnement.

---

## Utilisation

### Option 1 : lancer l'assistant directement sur NAO

```bash
cd robot
python main.py --robot-ip 127.0.0.1
```

Le dossier `robot/` contient le script et sa base de connaissances ; le mode local n'a pas besoin d'un appel à Mistral.

### Option 2 : charger la mémoire depuis un ordinateur

```bash
python dev/nao_memory_loader.py --ip <IP_DU_ROBOT_NAO> --port 9559
```

Le chargeur injecte les clés dans `ALMemory` et charge le topic QiChat dans `ALDialog`.

### Option 3 : simulation de développement sur ordinateur

```bash
python dev/nao_memory_loader.py --simu
```

Cette commande teste les ressources en console sans robot physique.

---

## Exemple de questions que le robot peut traiter

- "Qu'est-ce que le bac de français ?"
- "Quelle est la méthode de dissertation ?"
- "Parle-moi de Rimbaud"
- "Quelles sont les épreuves de français ?"
- "Qu'est-ce que la seconde prépare ?"

---

## Sources

Les contenus proviennent exclusivement du site [educatee.fr](https://www.educatee.fr), réorganisés pour un usage robotique et pédagogique.

---

## Cas d'usage

Ce projet est adapté pour :
- un robot éducatif en classe,
- un assistant oral de soutien scolaire,
- une démonstration de mémoire de connaissances structurée pour NAO,
- une base de départ pour un système conversationnel plus avancé.

---

## Remarques

- Ce projet est pensé pour l'environnement NAO/NAOqi.
- Les contenus ont été nettoyés pour limiter les éléments peu adaptés à la synthèse vocale.
- `robot/main.py` utilise les réponses locales en priorité. Mistral est une option distincte, activée uniquement si une clé API est fournie.

---

## Licence

Ce dépôt n'indique pas de licence explicite. Vérifiez avant toute utilisation en production ou diffusion publique.
