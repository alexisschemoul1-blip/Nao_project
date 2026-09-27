# NAO, assistant pédagogique de français

Ce projet vise à transformer un robot NAO en assistant pédagogique intelligent pour les cours de français. Il combine trois éléments : une base de connaissances locale, une mémoire persistante pour noter les souvenirs de l'utilisateur et, en option, un modèle d'intelligence artificielle distant pour les questions auxquelles la base ne répond pas.

Le mode de réponse par base de connaissances fonctionne directement sur le robot, sans ordinateur extérieur et sans connexion Internet : le programme lit les fichiers locaux, utilise les services NAOqi pour écouter et parler, et répond à partir des connaissances embarquées. **L'accès à Mistral nécessite obligatoirement une connexion Internet** : lorsqu'il est activé, les questions inconnues courtes sont envoyées au service Mistral distant.

`robot/main.py` est compatible avec Python 2.7 et Python 3. Pour le fonctionnement local sur un NAO équipé de NAOqi et Python 2.7, il peut être exécuté directement sur le robot, sans ordinateur extérieur. Le chargeur de développement et les tests du dépôt restent prévus pour Python 3.

## Comment le programme fonctionne

`robot/main.py` est l'assistant autonome :

1. Il charge `nao_knowledge_base.json` en UTF-8, qui contient l'identité du robot, les réponses pédagogiques et les clés à publier dans `ALMemory`.
2. Il ouvre `memoire.json`, fichier séparé dans lequel les souvenirs dictés par l'utilisateur sont enregistrés.
3. Si une adresse de robot est fournie, il se connecte aux services NAOqi : reconnaissance vocale, synthèse vocale et mémoire du robot. La hauteur TTS est réglée à `0.8` pour rendre la voix plus grave.
4. Il écoute une question et cherche d'abord un déclencheur explicite dans la base de connaissances. Si une réponse locale correspond, elle est prononcée sans appel à l'IA.
5. Si aucune réponse locale ne correspond, une question de 200 caractères maximum est envoyée à Mistral uniquement si une clé API a été fournie. Les questions plus longues sont renvoyées à reformuler. Sans clé, aucune requête Mistral n'est faite.
6. Une demande commençant par « Souvenir » ajoute le texte qui suit dans `memoire.json`.

**Limite actuelle de la mémoire :** les souvenirs sont enregistrés sur disque, mais `main.py` ne les recherche pas et ne les transmet pas encore à Mistral pour répondre aux questions. La mémoire persistante est donc une fonction de prise de notes, pas encore une mémoire conversationnelle consultable.

## Fichiers du projet

```text
Nao_project/
├── README.md
├── robot/
│   ├── main.py
│   ├── nao_knowledge_base.json
│   ├── memoire.json
│   └── educatee_francais_lycee.top
├── dev/
│   └── nao_memory_loader.py
└── tests/
    └── test_main.py
```

- **`robot/main.py`** : boucle de conversation autonome, recherche locale des réponses, enregistrement des souvenirs et appels Mistral facultatifs.
- **`robot/nao_knowledge_base.json`** : base structurée des contenus Educatée et des réponses courtes ou longues. Le programme la lit sans modifier ce fichier.
- **`robot/memoire.json`** : données personnelles ajoutées avec la commande vocale « Souvenir, ... ». Ce fichier est distinct de la base pédagogique.
- **`robot/educatee_francais_lycee.top`** : topic QiChat contenant des concepts, des phrases déclencheuses et des dialogues prêts pour `ALDialog`. Il est chargé par l'outil de développement ; `main.py` utilise sa propre recherche dans le JSON et ne charge pas directement le topic.
- **`dev/nao_memory_loader.py`** : outil facultatif lancé depuis un ordinateur pour injecter les clés de connaissances dans `ALMemory`, configurer la voix et charger le topic QiChat dans `ALDialog`. Il fournit également une simulation en console. Cet ordinateur sert à préparer ou tester le robot, pas à exécuter l'assistant autonome une fois celui-ci installé sur un environnement compatible du robot.
- **`tests/test_main.py`** : tests de la sélection des réponses locales, des appels Mistral, de l'enregistrement des souvenirs, des réglages TTS et du chemin du topic.

Les clés injectées dans `ALMemory` sont organisées par domaines, par exemple `Educatee/Seconde/...` ou `Educatee/Bac/...`. Le JSON est la source structurée utilisée par l'assistant ; `ALMemory` expose également certaines de ces informations aux autres modules NAOqi.

## Exécution locale

### Assistant sur le robot

Après avoir copié le dossier `robot/` sur le NAO et vérifié la disponibilité de Python 2.7 et de NAOqi :

```bash
cd robot
python main.py --robot-ip 127.0.0.1
```

Le robot doit pouvoir joindre son service NAOqi sur le port `9559`. Le programme principal utilise Python standard pour les réponses locales et l'écriture de la mémoire ; il ne requiert pas `requests` sauf pour Mistral.

Pour tester l'assistant en console sans robot, Python 2.7 ou Python 3 peuvent être utilisés :

```bash
cd robot
python main.py --text-mode
```

Les réponses du JSON et l'enregistrement de souvenirs restent locaux. Aucune dépendance Python tierce n'est nécessaire pour ce mode sans Mistral ; l'accès au robot physique requiert NAOqi.

## Activer Mistral (facultatif)

Mistral n'est pas exécuté localement sur le NAO. **Cette option nécessite une connexion Internet**, une clé API et le paquet `requests`. Avec Python 2.7, installez une version de `requests` qui prend encore en charge Python 2 (par exemple `requests<2.28`). L'appel est réservé aux questions courtes qui ne correspondent pas à un déclencheur de la base locale. Les réponses locales, la reconnaissance vocale et la synthèse vocale du robot restent sur le NAO.

```bash
cd robot
python main.py --text-mode --mistral-api-key VOTRE_CLE_API
```

Sans clé API ou sans connexion Internet, aucune réponse Mistral ne peut être obtenue ; sans clé, le programme reste en mode local et indique qu'il n'a pas de réponse pour les questions inconnues. Ne placez pas une vraie clé dans un fichier suivi par Git.

## Charger les ressources NAO depuis un ordinateur

Cette étape est facultative et séparée de l'exécution autonome. Depuis un ordinateur équipé de Python 3 et du SDK NAOqi :

```bash
python3 dev/nao_memory_loader.py --ip ADRESSE_IP_DU_ROBOT --port 9559
```

Le chargeur injecte les clés du JSON dans `ALMemory` et tente de charger `educatee_francais_lycee.top` dans `ALDialog`. Pour lancer plutôt la simulation locale du chargeur :

```bash
python3 dev/nao_memory_loader.py --simu
```

## Vérifier les tests

Depuis la racine du dépôt, avec Python 3 :

```bash
python3 -m unittest discover -s tests -v
```

## Limites et évolutions possibles

- Le fonctionnement embarqué sans service externe concerne les réponses prévues dans la base et l'enregistrement local des souvenirs. Répondre à une question inconnue avec Mistral implique un échange avec un service distant.
- `dev/nao_memory_loader.py` et les tests utilisent Python 3 ; le portage Python 2.7 concerne le programme autonome `robot/main.py`.
- Pour que la mémoire devienne conversationnelle, il reste à rechercher les souvenirs enregistrés et à définir explicitement comment ils peuvent enrichir les réponses.
- Les sources pédagogiques sont structurées à partir des ressources Educatée et CLAPOTEE ; la base JSON reste modifiable indépendamment du code.

## Licence

Aucune licence n'est déclarée dans ce dépôt. Vérifiez les droits d'utilisation avant toute diffusion ou utilisation en production.
