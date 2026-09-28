# NAO, assistant pédagogique de français

Ce projet vise à transformer un robot NAO en assistant pédagogique intelligent pour les cours de français. Il combine trois éléments : une base de connaissances locale, une mémoire persistante pour noter les souvenirs de l'utilisateur et, en option, un modèle d'intelligence artificielle distant pour les questions auxquelles la base ne répond pas.

Le mode de réponse par base de connaissances fonctionne directement sur le robot, sans ordinateur extérieur et sans connexion Internet : le programme lit les fichiers locaux, utilise les services NAOqi pour écouter et parler, et répond à partir des connaissances embarquées. **L'accès à Mistral nécessite obligatoirement une connexion Internet** : lorsqu'il est activé, les questions inconnues courtes sont envoyées au service Mistral distant.

`robot/main.py` est le point d'entrée réservé au robot NAO et refuse de démarrer hors de Python 2.7. La logique partagée, testable sur ordinateur, se trouve dans `robot/assistant_core.py` ; la simulation console pour le développement PC est dans `dev/nao_console.py`.

## Comment le programme fonctionne

Sur le robot, `robot/main.py` :

1. Il charge `nao_knowledge_base.json` en UTF-8, qui contient l'identité du robot, les réponses pédagogiques et les clés à publier dans `ALMemory`.
2. Il ouvre `memoire.json`, fichier séparé dans lequel les souvenirs dictés par l'utilisateur sont enregistrés et conservés entre les redémarrages.
3. Il se connecte aux services NAOqi locaux : reconnaissance vocale, synthèse vocale et mémoire du robot. La hauteur TTS est réglée à `0.8` pour rendre la voix plus grave.
4. Il écoute une question et cherche d'abord un déclencheur explicite dans la base de connaissances. Si une réponse correspond, elle est prononcée sans appel à l'IA ; les souvenirs pertinents peuvent compléter cette réponse.
5. Si la base ne répond pas, il recherche les souvenirs pertinents dans `memoire.json`. Sans clé Mistral, le robot restitue les informations mémorisées directement et localement. Avec Mistral, les souvenirs pertinents sont transmis comme contexte pour aider à répondre.
6. Une demande commençant par « Souvenir » ajoute le texte qui suit dans `memoire.json`. Les informations ainsi apprises sont disponibles aux questions suivantes.
7. Si aucune réponse locale ou mémoire pertinente n'est trouvée, une question de 200 caractères maximum peut être envoyée à Mistral. Les questions plus longues sont renvoyées à reformuler.
8. Pendant une exécution, NAO conserve les huit derniers échanges (question et réponse) et les transmet avec les questions envoyées à Mistral. L'historique transmis est limité à 6 000 caractères ; les réponses locales peuvent donc aussi éclairer une relance envoyée ensuite à Mistral. Cet historique de conversation reste en mémoire vive et est perdu à l'arrêt du programme.

La recherche de souvenirs repose sur les mots significatifs présents à la fois dans la question et dans les souvenirs. Il s'agit d'une recherche textuelle locale, pas d'une compréhension sémantique ; une question formulée très différemment peut ne pas retrouver le souvenir attendu.

Exemple : dites « Souvenir, mon prénom est Alice », puis demandez « Quel est mon prénom ? ». Sans Mistral, NAO retrouve et restitue localement le souvenir. Avec Mistral configuré, ce souvenir est fourni au modèle comme contexte pour formuler la réponse.

## Fichiers du projet

```text
Nao_project/
├── README.md
├── robot/
│   ├── __init__.py
│   ├── main.py
│   ├── assistant_core.py
│   ├── nao_hardware.py
│   ├── nao_knowledge_base.json
│   ├── memoire.json
│   └── educatee_francais_lycee.top
├── dev/
│   ├── nao_console.py
│   └── nao_memory_loader.py
└── tests/
    └── test_main.py
```

- **`robot/main.py`** : point d'entrée pour NAO uniquement. Il exige Python 2.7 et les services NAOqi ; il n'offre pas de mode console ou de simulation.
- **`robot/assistant_core.py`** : logique de conversation, base pédagogique, souvenirs et appels Mistral. Ce module compatible Python 2.7 et Python 3 est importé par le robot et testé sur ordinateur.
- **`robot/nao_hardware.py`** : adaptation des services NAOqi pour la reconnaissance vocale, la parole animée et l'injection dans `ALMemory`.
- **`robot/nao_knowledge_base.json`** : base structurée des contenus Educatée et des réponses courtes ou longues. Le programme la lit sans modifier ce fichier.
- **`robot/memoire.json`** : données personnelles ajoutées avec la commande vocale « Souvenir, ... ». Ce fichier est distinct de la base pédagogique et est consulté pour retrouver des souvenirs correspondant aux questions.
- **`robot/educatee_francais_lycee.top`** : topic QiChat contenant des concepts, des phrases déclencheuses et des dialogues prêts pour `ALDialog`. Il est chargé par l'outil de développement ; `main.py` utilise sa propre recherche dans le JSON et ne charge pas directement le topic.
- **`dev/nao_memory_loader.py`** : outil facultatif lancé depuis un ordinateur pour injecter les clés de connaissances dans `ALMemory`, configurer la voix et charger le topic QiChat dans `ALDialog`. Il fournit également une simulation en console. Cet ordinateur sert à préparer ou tester le robot, pas à exécuter l'assistant autonome une fois celui-ci installé sur un environnement compatible du robot.
- **`dev/nao_console.py`** : simulation interactive sur ordinateur, séparée de l'exécutable du robot. Sa mémoire de test est stockée dans le répertoire temporaire du système par défaut.
- **`tests/test_main.py`** : tests PC de la logique partagée, des appels Mistral, des souvenirs et du comportement de l'adaptateur NAOqi simulé.

Les clés injectées dans `ALMemory` sont organisées par domaines, par exemple `Educatee/Seconde/...` ou `Educatee/Bac/...`. Le JSON est la source structurée utilisée par l'assistant ; `ALMemory` expose également certaines de ces informations aux autres modules NAOqi.

## Déployer et lancer l'assistant sur le robot

`robot/main.py` tourne sur le NAO et se connecte aux services NAOqi locaux par `127.0.0.1:9559`. **Ne remplacez pas cette adresse par l'adresse réseau du robot** : celle-ci sert uniquement à transférer les fichiers et à ouvrir une session SSH depuis l'ordinateur. L'assistant peut répondre localement sans Internet ; seul Mistral nécessite un accès Internet.

1. **Vérifier le robot.** Connectez-vous au NAO et confirmez que Python 2.7 et le SDK NAOqi sont présents :

   ```bash
   python2.7 --version
   ```

   Le NAO doit disposer de ses services NAOqi actifs. Pour Mistral, il faut aussi un accès Internet depuis le robot.

2. **Préparer les fichiers.** Le dossier `robot/` doit être déployé en entier, car `main.py` importe `assistant_core.py` et `nao_hardware.py`. Il contient aussi `nao_knowledge_base.json`, nécessaire aux réponses. `memoire.json` est créé automatiquement s'il n'existe pas ; conservez-le lors d'une mise à jour si vous voulez garder les souvenirs enregistrés. Le fichier `.top` n'est utile qu'au chargeur QiChat facultatif.

3. **Transférer depuis l'ordinateur.** Remplacez l'adresse et le compte par ceux configurés sur votre robot (le compte SSH peut varier selon l'image NAOqi) :

   ```bash
   scp -r robot nao@192.168.1.42:/home/nao/
   ```

   Cette commande crée `/home/nao/robot/`. Le transfert utilise l'adresse réseau ; le script, une fois démarré sur le NAO, utilise bien `127.0.0.1` pour `ALProxy`.

4. **Installer la dépendance Mistral, si nécessaire.** Cette étape est facultative et concerne uniquement l'accès à l'API distante :

   ```bash
   ssh nao@192.168.1.42
   python2.7 -m pip install "requests<2.28"
   ```

   Si `pip` n'est pas installé sur le robot, préparez `requests` et ses dépendances pour Python 2.7 avec une méthode compatible avec votre image NAOqi. Sans Mistral, aucune dépendance Python externe n'est nécessaire.

5. **Lancer sur le robot.** Depuis la session SSH ouverte sur le NAO :

   ```bash
   cd /home/nao/robot
   python2.7 main.py
   ```

   Pour activer Mistral, définissez la clé dans l'environnement du processus, puis lancez le script :

   ```bash
   export MISTRAL_API_KEY="VOTRE_CLE_API"
   python2.7 main.py
   ```

   La clé n'est pas nécessaire aux réponses locales ; ne l'inscrivez pas dans un fichier suivi par Git. Pour arrêter l'assistant, interrompez le processus avec `Ctrl+C`. Les souvenirs de `memoire.json` persistent ; l'historique de conversation utilisé pour les relances à Mistral est remis à zéro au redémarrage.

## Tester sur ordinateur

```bash
python3 dev/nao_console.py
```

La simulation console teste la logique partagée sans SDK NAOqi. Pour activer Mistral, la clé API peut être définie dans `MISTRAL_API_KEY` ou fournie par `--mistral-api-key`. Pour les tests automatisés :

```bash
python3 -m unittest discover -s tests -v
```

## Activer Mistral (facultatif)

Mistral n'est pas exécuté localement sur le NAO. **Son accès nécessite une connexion Internet**, une clé API et le paquet `requests`. La clé est lue dans la variable d'environnement `MISTRAL_API_KEY`. L'appel est réservé aux questions courtes qui ne correspondent pas à un déclencheur de la base locale ; les souvenirs pertinents et jusqu'aux huit derniers échanges (dans la limite de 6 000 caractères) sont ajoutés au contexte envoyé à Mistral. Pour un démarrage automatique sous Linux/NAO, configurez `MISTRAL_API_KEY` dans l'environnement du service ou du script de lancement. Les réponses de la base et de la mémoire, la reconnaissance vocale et la synthèse vocale restent sur le NAO.

Sans clé API, le programme ne fait aucun appel Internet et peut toujours répondre avec la base et les souvenirs locaux. Si Mistral est configuré mais que le robot n'a pas Internet, aucune réponse de Mistral ne peut être obtenue. Ne placez pas une vraie clé dans un fichier suivi par Git. Lorsque Mistral est activé, la question courante, l'historique récent de la conversation et les extraits de souvenirs pertinents sont transmis au service distant. L'historique n'est conservé que durant le processus en cours ; il repart à zéro au redémarrage.

## Charger les ressources NAO depuis un ordinateur

Cette étape est facultative et séparée de l'exécution autonome. Depuis un ordinateur équipé de Python 3 et du SDK NAOqi :

```bash
python3 dev/nao_memory_loader.py --ip ADRESSE_IP_DU_ROBOT --port 9559
```

Le chargeur injecte les clés du JSON dans `ALMemory` et tente de charger `educatee_francais_lycee.top` dans `ALDialog`. Pour lancer plutôt la simulation locale du chargeur :

```bash
python3 dev/nao_memory_loader.py --simu
```

## Limites et évolutions possibles

- La base de connaissances et la mémoire utilisateur sont conservées localement. Les souvenirs pertinents ne quittent le robot que si un appel Mistral est activé pour répondre à une question.
- `robot/main.py` et les modules qu'il importe doivent rester compatibles avec Python 2.7 ; la simulation PC, le chargeur et les tests sont exécutés avec Python 3.
- La recherche des souvenirs est lexicale et peut manquer les paraphrases ; une recherche sémantique reste une évolution possible.
- Les sources pédagogiques sont structurées à partir des ressources Educatée et CLAPOTEE ; la base JSON reste modifiable indépendamment du code.

## Licence

Aucune licence n'est déclarée dans ce dépôt. Vérifiez les droits d'utilisation avant toute diffusion ou utilisation en production.
