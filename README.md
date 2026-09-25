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
├── main.py
├── nao_memory_loader.py
├── nao_knowledge_base.json
├── dialogue_bac_et_seconde.top
└── ...
```

### Fichiers principaux

- `nao_knowledge_base.json` : base de connaissances complète, sous forme de clés `ALMemory` et de réponses pédagogiques.
- `dialogue_bac_et_seconde.top` : script de dialogue en QiChat pour `ALDialog`.
- `nao_memory_loader.py` : script d'injection de la mémoire sur le robot ou en simulation locale.
- `main.py` : assistant conversationnel Python qui détecte les mots-clés locaux puis fait appel à Mistral si nécessaire.

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

### 1. Injection dans la mémoire NAO

Le script `nao_memory_loader.py` permet d'envoyer les données dans `ALMemory` et de charger le topic QiChat dans `ALDialog`.

### 2. Dialogue oral

Le fichier `dialogue_bac_et_seconde.top` définit les intentions, concepts et déclencheurs du robot. Il permet de gérer les interactions vocales avec un élève.

### 3. Simulation locale

Si aucun robot NAO n'est accessible, le script peut tourner en mode simulation sur ordinateur pour tester les réponses textuelles et la logique de détection de mots-clés.

---

## Prérequis

- Python 3
- Accès à un robot NAO avec NAOqi (optionnel)
- `naoqi` si vous voulez vous connecter au vrai robot
- Optionnel : une clé API Mistral pour le mode assistant IA dans `main.py`

---

## Utilisation

### Option 1 : charger la mémoire sur un robot NAO

```bash
python nao_memory_loader.py --ip <IP_DU_ROBOT_NAO> --port 9559
```

Le script :
- se connecte au robot,
- injecte les clés dans `ALMemory`,
- charge le topic QiChat dans `ALDialog`,
- prononce un message d'accueil.

### Option 2 : lancer la simulation locale

```bash
python nao_memory_loader.py --simu
```

Cette commande lance une simulation console pour tester la logique de réponse locale.

### Option 3 : utiliser l'assistant Python

```bash
python main.py --text-mode
```

En mode texte, l'application fonctionne sans robot physique et permet de simuler les échanges.

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
- La logique d'IA de `main.py` est un complément, mais les réponses locales restent prioritaires pour rester fidèle au programme et au contexte pédagogique.

---

## Licence

Ce dépôt n'indique pas de licence explicite. Vérifiez avant toute utilisation en production ou diffusion publique.
