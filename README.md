# NAO — assistant pédagogique de français

Assistant vocal pour robot NAO, conçu pour aider les élèves à réviser le français et le bac. Il s’appuie sur une base de connaissances locale, une mémoire de souvenirs utilisateur et, en option, l’API distante de Mistral.

## Fonctionnalités

- Réponses locales sur les cours, les œuvres et les épreuves de français, depuis `robot/nao_knowledge_base.json`.
- Ajout de souvenirs avec la commande **« Souvenir, … »**, enregistrés dans `robot/memoire.json`.
- Réponses aux questions inconnues courtes par Mistral, si une clé API et une connexion Internet sont disponibles.
- Simulation sur ordinateur et tests de la logique sans robot.

Les réponses locales et les souvenirs restent sur l’appareil. Si Mistral est activé, la question, les échanges récents et les souvenirs pertinents peuvent être envoyés au service distant. Sans clé API, aucune requête Mistral n’est effectuée. La recherche des souvenirs est textuelle : elle peut ne pas retrouver une formulation très différente.

## Démarrer sur ordinateur

La simulation utilise Python 3 et ne nécessite pas le SDK NAOqi :

```bash
python3 dev/nao_console.py
```

Pour activer Mistral, installez `requests` et fournissez une clé API dans l’environnement :

```bash
python3 -m pip install requests
export MISTRAL_API_KEY="votre_cle_api"
python3 dev/nao_console.py
```

Les tests automatisés s’exécutent avec :

```bash
python3 -m unittest discover -s tests -v
```

## Déployer sur NAO

`robot/main.py` s’exécute **sur le robot**, avec Python 2.7 et les services NAOqi actifs. Il ne fonctionne pas comme simulateur sur un PC. Le SDK fournit la reconnaissance vocale, la synthèse vocale et la mémoire du robot.

1. Transférez le dossier `robot/` sur le NAO (adaptez l’adresse et le compte à votre installation) :

   ```bash
   scp -r robot nao@192.168.1.42:/home/nao/
   ```

2. Connectez-vous au robot et lancez l’assistant :

   ```bash
   ssh nao@192.168.1.42
   cd /home/nao/robot
   python2.7 main.py
   ```

L’assistant se connecte aux services NAOqi locaux sur le port `9559`. Pour utiliser Mistral, installez une version de `requests` compatible avec Python 2.7 (par exemple `requests<2.28`) et définissez `MISTRAL_API_KEY` avant le lancement. **Ne stockez pas votre clé dans un fichier suivi par Git.**

La reconnaissance vocale de NAO utilise le vocabulaire construit à partir des déclencheurs de la base de connaissances ; elle ne transcrit pas librement toute phrase. La mémoire utilisateur est conservée dans `memoire.json` entre les lancements. Gardez ce fichier lors d’une mise à jour si vous souhaitez préserver les souvenirs.

## Fichiers principaux

```text
robot/
├── main.py                    # Entrée du programme sur le NAO (Python 2.7)
├── assistant_core.py          # Conversation, connaissances, souvenirs et Mistral
├── nao_hardware.py            # Adaptateur des services NAOqi
├── nao_knowledge_base.json    # Contenus et réponses pédagogiques
├── memoire.json               # Souvenirs utilisateur persistants
└── educatee_francais_lycee.top # Topic QiChat facultatif

dev/
├── nao_console.py             # Simulation interactive sur PC (Python 3)
└── nao_memory_loader.py       # Charge les ressources dans ALMemory / ALDialog

tests/
└── test_main.py               # Tests automatisés
```

Le chargeur QiChat est une fonctionnalité séparée de l’assistant autonome. Depuis un ordinateur équipé du SDK NAOqi, il peut charger le topic et publier les clés de connaissances dans `ALMemory` :

```bash
python3 dev/nao_memory_loader.py --ip 192.168.1.42 --port 9559
```

Pour afficher la simulation du chargeur sans robot :

```bash
python3 dev/nao_memory_loader.py --simu
```

## Licence

Aucune licence n’est déclarée dans ce dépôt. Vérifiez les droits d’utilisation des contenus avant toute diffusion.
