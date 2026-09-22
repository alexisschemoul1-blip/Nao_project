# Module Mémoire EDUCATEE pour Robot NAO (SoftBank Robotics / NAOqi)

Ce dossier contient l'ensemble des connaissances extraites **exclusivement du site [educatee.fr](https://www.educatee.fr)** (conçu par Cécile Cathelin) reformatées et optimisées pour servir de **mémoire et de base de dialogue à un robot humanoïde NAO**.

---

## 🤖 Pourquoi ce formatage spécifique pour NAO ?

Contrairement à un document textuel classique ou un JSON brut, un robot NAO impose des contraintes robotiques et vocales précises :
1. **Diction et Text-to-Speech (TTS) :** Suppression totale des liens hypertextes bruts (`http...`) et de la ponctuation complexe inaudible pour le moteur vocal de NAO (`ALTextToSpeech` / `ALAnimatedSpeech`).
2. **Architecture ALMemory :** Découpage sous forme de clés mémoires hiérarchiques (`Educatee/Bac/...`, `Educatee/Seconde/...`) injectables directement dans le tableau noir partagé de NAOqi.
3. **Moteur conversationnel QiChat :** Fichier natif `.top` intégrant la reconnaissance d'intentions vocales, des concepts de synonymes et des animations gestuelles (`^start(...)`) synchronisées avec la parole.

---

## 📂 Contenu du dossier `mémoire_educatee_vf`

| Fichier | Format | Rôle pour NAO |
| :--- | :--- | :--- |
| **`nao_knowledge_base.json`** | JSON NAOqi | Base de connaissances complète : clés `almemory_keys`, intents vocaux, réponses courtes et détaillées TTS, et repères pédagogiques. |
| **`dialogue_bac_et_seconde.top`** | QiChat (`.top`) | Script de dialogue natif pour le module `ALDialog` de NAO, avec concepts, déclencheurs oraux et gestuelle associée. |
| **`nao_memory_loader.py`** | Script Python | Script d'injection automatique dans `ALMemory` / `ALDialog`, intégrant également un mode simulation autonome sur PC. |
| **`README_NAO.md`** | Markdown | Documentation d'intégration et guide d'utilisation. |

---

## 🧠 Clés mémoires injectées dans `ALMemory`

Toutes les informations essentielles sont enregistrées sous l'arborescence `Educatee/` :

```
Educatee/
├── Meta/
│   ├── Source                    -> "educatee.fr par Cécile Cathelin"
│   ├── Ouvrage                   -> "Vous allez aimer réussir votre bac de français (Ellipses)"
│   └── Podcasts                  -> "Plateforme audio CLAPOTEE"
├── Seconde/
│   ├── Projet                    -> "L'Odyssée du lecteur"
│   ├── Devise                    -> "Parce que l'on ne peut que réussir lorsque que l'on sait où l'on va !"
│   ├── AnticipationBac           -> "Importance de s'entraîner dès la 2nde..."
│   ├── PiliersReussite           -> "Minimiser le stress, améliorer l'expression, feedbacks..."
│   ├── SupportsCours             -> "Odyssée 2nde, rentrée et mythes, Pandora de Redon..."
│   ├── Grammaire                 -> "Points fondamentaux de 2nde (Flashcards)..."
│   └── LecturesAudio             -> "Du Bellay, Racine, Zola..."
└── Bac/
    ├── Epreuves                  -> "Écrit de 4h et oral de 20min..."
    ├── Methode/Commentaire       -> "To Do List et mémento de formules..."
    ├── Methode/Dissertation      -> "Méthode Clapotee et phrases magiques..."
    ├── Methode/Oral              -> "Lecture linéaire en 3 temps, grammaire et entretien..."
    ├── Oral/Bordereau            -> "Grille d'évaluation officielle 2022..."
    └── Oeuvres/
        ├── Sarraute              -> "Pour un oui ou pour un non (théâtre / Molière)"
        ├── LaBoetie              -> "Discours de la servitude volontaire (idées / Rousseau)"
        ├── Rimbaud               -> "Cahiers de Douai (poésie / révolution poétique)"
        └── ChretienDeTroyes      -> "Roman arthurien et aventure courtoise"
```

---

## 🚀 Comment déployer la mémoire sur NAO ?

### Méthode 1 : Via le script Python `nao_memory_loader.py`

#### Sur le robot réel (ou simulateur Choregraph / robot virtuel) :
```bash
python nao_memory_loader.py --ip <IP_DU_ROBOT_NAO> --port 9559
```
*Le script se connecte au robot, injecte les clés dans `ALMemory`, compile le topic QiChat dans `ALDialog` et fait prononcer une phrase d'accueil à NAO.*

#### En simulation locale sur ordinateur (sans robot branché) :
```bash
python nao_memory_loader.py --simu
```

---

### Méthode 2 : Dans le logiciel Choregraphe (SoftBank Robotics)

1. Ouvrez votre projet dans **Choregraphe**.
2. Créez une boîte **Set Data** ou **Python Script** :
   ```python
   class MyClass(GeneratedClass):
       def onInput_onStart(self):
           import json
           memory = ALProxy("ALMemory")
           with open("nao_knowledge_base.json", "r") as f:
               data = json.load(f)
           for k, v in data["almemory_keys"].items():
               memory.insertData(k, v)
           self.onStopped()
   ```
3. Glissez une boîte **Dialog** et importez le fichier `dialogue_bac_et_seconde.top`.
4. Reliez l'entrée au démarrage du comportement : NAO est prêt à dialoguer avec les élèves !

---

## 🗣️ Exemples d'interactions vocales avec NAO

- **Élève :** *"NAO, présente-toi."*  
  **NAO :** *"Bonjour ! Je suis NAO, votre assistant pédagogique pour les cours de français au lycée. Toutes mes connaissances sont issues du site Educatée, conçu par la professeure Cécile Cathelin. Je peux vous guider pour le programme de seconde, ou vous entraîner pour le baccalauréat de français en première !"*

- **Élève :** *"Pourquoi s'entraîner dès la seconde pour le bac ?"*  
  **NAO :** *"Sur Educatée, Cécile Cathelin explique que s'entraîner dès la seconde apporte trois grands atouts. Premièrement : minimiser le stress des examens futurs. Deuxièmement : obtenir de meilleures performances à l'oral et à l'écrit. Et troisièmement : bénéficier de feedbacks réguliers pour progresser en toute confiance !"*

- **Élève :** *"Que faut-il savoir sur Rimbaud ?"*  
  **NAO :** *"Dans la séquence poésie, les Cahiers de Douai illustrent la fougue rimbaldienne. Sur Educatée, vous découvrirez ses codes poétiques, quatre lectures linéaires, un sujet de dissertation pas à pas demandant si ce recueil représente une révolution poétique, complété par les séries audio de Sylvain Tesson sur France Inter."*

- **Élève :** *"Donne-moi un conseil pour la dissertation."*  
  **NAO :** *"La méthode de dissertation sur Educatée repose sur trois piliers : d'abord, la To Do List pour analyser le sujet et construire sa problématique ; ensuite, la méthode Clapotee pour structurer les parties ; et enfin, le répertoire des phrases magiques pour rédiger des transitions impeccables !"*
