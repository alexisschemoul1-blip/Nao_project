#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-
"""
nao_assistant.py
=================

Assistant conversationnel pour robot NAO.

Architecture :
    - KnowledgeBase   : charge et interroge une base de connaissances locale (JSON).
    - MistralBrain    : "cerveau" IA (API Mistral) qui harmonise la réponse finale
                         en s'appuyant sur le contexte trouvé dans la base de connaissances.
    - NaoInterface    : contrôle du robot NAO (synthèse vocale + reconnaissance vocale)
                         via le SDK NAOqi. Bascule automatiquement en mode texte
                         (clavier / terminal) si le robot n'est pas disponible,
                         ce qui permet de développer/tester sans robot physique.
    - Assistant       : orchestre le tout : écoute -> recherche connaissance -> Mistral -> réponse.

Prérequis :
    Python 2.7 (fourni avec le SDK NAOqi / Choregraphe 2.5)
    # Pour piloter un vrai robot NAO, le SDK NAOqi Python doit être installé
    # et disponible sur la machine (voir doc SoftBank Robotics). Ce script
    # importe 'naoqi' de façon paresseuse et ne plante pas si absent.

Variables d'environnement :
    Mistral_API       : clé API Mistral (obligatoire pour utiliser le cerveau IA)

Utilisation :
    # Mode texte (sans robot), pour tester la logique de bout en bout :
    python main.py --text-mode

    # Mode robot NAO réel :
    python main.py --robot-ip 192.168.1.42 --robot-port 9559
"""

import os
import sys
import json
import argparse
import difflib
import logging
import codecs
import urllib2

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("nao_assistant")


# Ressources livrées avec ce programme. Le chemin absolu permet de lancer le
# script depuis n'importe quel dossier Windows.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_KB_PATH = os.path.join(BASE_DIR, "nao_knowledge_base.json")
MISTRAL_ENV_VAR = "Mistral_API"


def get_mistral_api_key():
    """Lit la clé Mistral depuis l'environnement du processus Windows.

    Windows ne distingue pas la casse des variables d'environnement, mais ce
    repli rend également le comportement fiable si le script est lancé depuis
    un autre environnement. ``MISTRAL_API_KEY`` reste accepté pour ne pas
    casser une configuration plus ancienne.
    """
    for name in (MISTRAL_ENV_VAR, "MISTRAL_API_KEY"):
        value = os.environ.get(name)
        if value and value.strip():
            return value.strip()

    accepted_names = set((MISTRAL_ENV_VAR.lower(), "mistral_api_key"))
    for name, value in os.environ.items():
        if name.lower() in accepted_names and value and value.strip():
            return value.strip()

    # Si la variable vient d'être créée avec ``setx``, un terminal déjà ouvert
    # ne l'a pas encore reçue dans son environnement. Sous Windows, on relit
    # alors les emplacements utilisateur et système du registre.
    if os.name == "nt":
        try:
            import _winreg as winreg
            registry_locations = (
                (winreg.HKEY_CURRENT_USER, r"Environment"),
                (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
            )
            for hive, subkey in registry_locations:
                key = winreg.OpenKey(hive, subkey)
                try:
                    for name in (MISTRAL_ENV_VAR, "MISTRAL_API_KEY"):
                        try:
                            value, _ = winreg.QueryValueEx(key, name)
                            if value and value.strip():
                                return value.strip()
                        except EnvironmentError:
                            continue
                finally:
                    winreg.CloseKey(key)
        except EnvironmentError:
            # Accès refusé ou registre indisponible : l'environnement courant
            # reste la seule source disponible.
            pass
    return None


# ---------------------------------------------------------------------------
# 1. Base de connaissances
# ---------------------------------------------------------------------------
class KnowledgeBase:
    """Charge une base de connaissances locale et retrouve les entrées
    les plus pertinentes par rapport à une question posée.

    Deux formats de fichier JSON sont acceptés :

    1. Format "riche" (recommandé), tel que produit pour un robot NAO :
       {
         "robot_identity": {...},          # identité / consignes de voix du robot
         "almemory_keys": {"Cle/Path": "valeur", ...},  # données à pousser dans ALMemory
         "dialogue_knowledge_base": [
            {
              "id": "...", "theme": "...",
              "triggers": ["mot clé 1", "phrase déclenchante 2", ...],
              "nao_tts_short": "réponse courte pour la voix du robot",
              "nao_tts_long": "réponse plus détaillée (optionnelle)",
              ... (champs libres additionnels utilisés comme contexte)
            }, ...
         ]
       }

    2. Format "simple" (rétrocompatible) :
       {"entries": [{"question": "...", "keywords": [...], "reponse": "..."}]}

    En interne, chaque entrée est normalisée vers un dictionnaire commun avec
    les clés : id, theme, triggers, reponse_courte, reponse_longue, extra.
    """

    def __init__(self, path):
        self.path = path
        self.entries = []
        self.robot_identity = {}
        self.almemory_keys = {}
        self._load()

    def _load(self):
        if not os.path.exists(self.path):
            logger.warning("Base de connaissances introuvable : %s (base vide utilisée)", self.path)
            return

        with codecs.open(self.path, "r", "utf-8") as f:
            data = json.load(f)

        self.robot_identity = data.get("robot_identity", {})
        self.almemory_keys = data.get("almemory_keys", {})

        if "dialogue_knowledge_base" in data:
            for raw in data["dialogue_knowledge_base"]:
                extra = {
                    k: v
                    for k, v in raw.items()
                    if k not in ("id", "theme", "triggers", "nao_tts_short", "nao_tts_long")
                }
                self.entries.append({
                    "id": raw.get("id", ""),
                    "theme": raw.get("theme", ""),
                    "triggers": raw.get("triggers", []),
                    "reponse_courte": raw.get("nao_tts_short", ""),
                    "reponse_longue": raw.get("nao_tts_long", "") or raw.get("nao_tts_short", ""),
                    "extra": extra,
                })
        elif "entries" in data:
            # Format simple rétrocompatible
            for raw in data["entries"]:
                self.entries.append({
                    "id": str(raw.get("id", "")),
                    "theme": "",
                    "triggers": [raw.get("question", "")] + raw.get("keywords", []),
                    "reponse_courte": raw.get("reponse", ""),
                    "reponse_longue": raw.get("reponse", ""),
                    "extra": {},
                })

        logger.info(
            "Base de connaissances chargée : %d entrées, %d clés ALMemory",
            len(self.entries), len(self.almemory_keys),
        )

    def _score(self, question, entry):
        """Calcule un score de similarité simple entre la question posée
        et une entrée de la base (thème + déclencheurs)."""
        question_l = question.lower()
        candidates = [entry.get("theme", "")] + entry.get("triggers", [])
        best = 0.0
        for cand in candidates:
            if not cand:
                continue
            cand_l = cand.lower()
            ratio = difflib.SequenceMatcher(None, question_l, cand_l).ratio()
            # bonus si un déclencheur est explicitement contenu dans la question
            # (ou l'inverse, pour les déclencheurs très courts comme "rimbaud")
            if cand_l in question_l or question_l in cand_l:
                ratio += 0.35
            best = max(best, ratio)
        return best

    def search(self, question, top_k=3, min_score=0.3):
        """Retourne les `top_k` entrées les plus pertinentes pour la question posée."""
        scored = [(self._score(question, e), e) for e in self.entries]
        scored.sort(key=lambda t: t[0], reverse=True)
        results = [e for score, e in scored if score >= min_score][:top_k]
        logger.debug("Recherche connaissance pour '%s' -> %d résultat(s)", question, len(results))
        return results

    def get_almemory_snapshot(self):
        """Retourne les clés/valeurs à pousser dans ALMemory au démarrage."""
        return dict(self.almemory_keys)


# ---------------------------------------------------------------------------
# 2. Cerveau IA (Mistral)
# ---------------------------------------------------------------------------
class MistralBrain:
    """Interface avec l'API Mistral, chargée d'harmoniser la réponse finale
    à partir de la question de l'utilisateur et du contexte de connaissances."""

    API_URL = "https://api.mistral.ai/v1/chat/completions"

    def __init__(self, api_key=None, model="mistral-small-latest"):
        self.api_key = api_key.strip() if api_key and api_key.strip() else get_mistral_api_key()
        self.model = model
        if not self.api_key:
            logger.warning(
                "Aucune clé %s trouvée : le cerveau IA fonctionnera "
                "en mode dégradé (réponse brute de la base de connaissances).",
                MISTRAL_ENV_VAR,
            )

    def _build_system_prompt(self, robot_identity=None):
        base = (
            "Tu es le cerveau conversationnel d'un robot humanoïde NAO. "
            "Tu réponds en français, en une ou deux phrases courtes, sur un ton "
            "chaleureux et adapté à une interaction orale robot/humain. "
            "Tu n'utilises QUE les informations issues de la base de connaissances "
            "fournie en contexte : tu ne dois jamais inventer un fait, un titre "
            "d'œuvre ou une ressource qui n'y figure pas. "
            "N'énonce jamais d'URL ou d'adresse web telle quelle à l'oral ; "
            "reformule-la ou décris la ressource. "
            "Si le contexte ne répond pas à la question, dis-le simplement et "
            "propose de reformuler la question."
        )
        if robot_identity:
            nom = robot_identity.get("nom", "NAO")
            role = robot_identity.get("role", "")
            source = robot_identity.get("source_exclusive", "")
            base += "\n\nTon identité : tu es {}. Ton rôle : {}. ".format(nom, role)
            base += "Ta source de connaissances exclusive est : {}.".format(source)
        return base

    def answer(
        self,
        question,
        context_entries,
        robot_identity=None,
        verbose=False,
    ):
        """Harmonise une réponse finale à partir de la question et du contexte
        récupéré dans la base de connaissances."""
        context_lines = []
        for e in context_entries:
            theme = e.get("theme", "")
            reponse = e.get("reponse_longue" if verbose else "reponse_courte", "")
            context_lines.append("- [{}] {}".format(theme, reponse))
        context_txt = "\n".join(context_lines)

        fallback_key = "reponse_longue" if verbose else "reponse_courte"

        if not self.api_key:
            # Mode dégradé : pas de clé API -> on renvoie directement la
            # meilleure entrée de la base de connaissances si elle existe.
            if context_entries:
                return context_entries[0].get(fallback_key, "Je n'ai pas de réponse à te donner.")
            return "Je n'ai pas encore de réponse à cette question."

        user_content = (
            "Question posée au robot : {}\n\n"
            "Contexte issu de la base de connaissances du robot :\n"
            "{}\n\n"
            "Formule la réponse finale que le robot doit prononcer."
        ).format(question, context_txt if context_txt else "(aucune information trouvée)")

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self._build_system_prompt(robot_identity)},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.4,
            "max_tokens": 200,
        }
        headers = {
            "Authorization": "Bearer {}".format(self.api_key),
            "Content-Type": "application/json",
        }

        try:
            request = urllib2.Request(self.API_URL, json.dumps(payload), headers)
            response = urllib2.urlopen(request, timeout=15)
            try:
                data = json.load(response)
            finally:
                response.close()
            return data["choices"][0]["message"]["content"].strip()
        except (urllib2.URLError, urllib2.HTTPError, ValueError, KeyError, IndexError) as exc:
            logger.error("Erreur appel API Mistral : %s", exc)
            if context_entries:
                return context_entries[0].get(fallback_key, "Je n'ai pas de réponse à te donner.")
            return "Désolé, je rencontre un problème pour réfléchir à une réponse."


# ---------------------------------------------------------------------------
# 3. Interface robot NAO (avec repli mode texte)
# ---------------------------------------------------------------------------
class NaoInterface:
    """Contrôle la synthèse vocale et la reconnaissance vocale du robot NAO.

    Si le SDK NAOqi n'est pas disponible ou si la connexion au robot échoue,
    bascule automatiquement en mode texte (entrée clavier / sortie console),
    ce qui permet de tester toute la logique de l'assistant sans robot."""

    def __init__(self, ip=None, port=9559, force_text_mode=False):
        self.ip = ip
        self.port = port
        self.text_mode = force_text_mode or not ip
        self.tts = None
        self.asr = None
        self.memory = None

        if not self.text_mode:
            self._connect_robot()

    def _connect_robot(self):
        try:
            from naoqi import ALProxy  # SDK NAOqi (Python 2, robots physiques)
        except ImportError:
            logger.warning(
                "Module 'naoqi' introuvable. Passage en mode texte. "
                "Installe le SDK NAOqi pour piloter un robot réel."
            )
            self.text_mode = True
            return

        try:
            self.tts = ALProxy("ALTextToSpeech", self.ip, self.port)
            self.asr = ALProxy("ALSpeechRecognition", self.ip, self.port)
            self.memory = ALProxy("ALMemory", self.ip, self.port)
            logger.info("Connecté au robot NAO à %s:%s", self.ip, self.port)
        except Exception as exc:  # RuntimeError levée par NAOqi si IP injoignable
            logger.error("Impossible de se connecter au robot (%s). Passage en mode texte.", exc)
            self.text_mode = True

    def push_knowledge_to_almemory(self, almemory_keys):
        """Pousse les paires clé/valeur de la base de connaissances dans
        ALMemory du robot, pour qu'elles soient accessibles à d'autres
        comportements NAOqi (Choregraphe, etc.). Sans effet en mode texte."""
        if self.text_mode or not almemory_keys:
            return
        for key, value in almemory_keys.items():
            try:
                self.memory.insertData(key, value)
            except Exception as exc:
                logger.warning("Impossible d'écrire la clé ALMemory '%s' : %s", key, exc)
        logger.info("%d clés poussées dans ALMemory", len(almemory_keys))

    def say(self, text):
        """Fait parler le robot (ou affiche le texte en mode texte)."""
        logger.info("Réponse : %s", text)
        if self.text_mode:
            print("[NAO dit] {}".format(text))
        else:
            self.tts.say(text)

    def listen(self):
        """Récupère une question, soit via reconnaissance vocale NAO,
        soit via saisie clavier en mode texte."""
        if self.text_mode:
            try:
                return raw_input("Question (Ctrl+C pour quitter) > ").strip()
            except EOFError:
                return ""
        # NOTE : une intégration complète de ALSpeechRecognition nécessite de
        # configurer un vocabulaire ou d'activer la reconnaissance continue et
        # de s'abonner à l'événement "WordRecognized" via ALMemory. Cette
        # méthode simplifiée est un point de départ à adapter à ton cas d'usage
        # (vocabulaire fermé, dictée libre via un service tiers, etc.).
        self.asr.setLanguage("French")
        vocabulary = ["question"]  # à remplacer par un vrai vocabulaire ou une dictée libre
        self.asr.setVocabulary(vocabulary, False)
        self.asr.subscribe("nao_assistant")
        try:
            word_data = self.memory.getData("WordRecognized")
            self.asr.unsubscribe("nao_assistant")
            if word_data and len(word_data) > 0:
                return word_data[0]
        except Exception as exc:
            logger.error("Erreur reconnaissance vocale : %s", exc)
        return ""


# ---------------------------------------------------------------------------
# 4. Orchestrateur
# ---------------------------------------------------------------------------
class Assistant:
    """Boucle principale : écoute une question, interroge la base de
    connaissances, fait harmoniser la réponse par Mistral, puis fait parler
    le robot."""

    def __init__(self, robot, kb, brain, verbose=False):
        self.robot = robot
        self.kb = kb
        self.brain = brain
        self.verbose = verbose

    def handle_question(self, question):
        if not question:
            return ""
        context = self.kb.search(question)
        answer = self.brain.answer(
            question, context, robot_identity=self.kb.robot_identity, verbose=self.verbose
        )
        self.robot.say(answer)
        return answer

    def run(self):
        self.robot.push_knowledge_to_almemory(self.kb.get_almemory_snapshot())
        nom = self.kb.robot_identity.get("nom", "NAO")
        self.robot.say("Bonjour, je suis {}, prêt à répondre à tes questions sur le français.".format(nom))
        try:
            while True:
                question = self.robot.listen()
                if not question:
                    continue
                if question.lower() in ("stop", "quitter", "exit"):
                    self.robot.say("À bientôt !")
                    break
                self.handle_question(question)
        except KeyboardInterrupt:
            self.robot.say("À bientôt !")


# ---------------------------------------------------------------------------
# 5. Point d'entrée
# ---------------------------------------------------------------------------
def parse_args():
    parser = argparse.ArgumentParser(description="Assistant NAO avec base de connaissances et cerveau Mistral")
    parser.add_argument("--robot-ip", type=str, default=None, help="Adresse IP du robot NAO")
    parser.add_argument("--robot-port", type=int, default=9559, help="Port NAOqi (défaut : 9559)")
    parser.add_argument("--text-mode", action="store_true", help="Forcer le mode texte (sans robot)")
    parser.add_argument(
        "--kb", type=str, default=DEFAULT_KB_PATH,
        help="Chemin vers la base de connaissances JSON (défaut : nao_knowledge_base.json livré avec le programme)",
    )
    parser.add_argument("--mistral-model", type=str, default="mistral-small-latest", help="Modèle Mistral à utiliser")
    parser.add_argument(
        "--mistral-api-key", type=str, default=None,
        help="Clé API Mistral (sinon variable d'environnement Windows Mistral_API)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    kb = KnowledgeBase(args.kb)
    brain = MistralBrain(api_key=args.mistral_api_key, model=args.mistral_model)
    robot = NaoInterface(ip=args.robot_ip, port=args.robot_port, force_text_mode=args.text_mode)

    assistant = Assistant(robot=robot, kb=kb, brain=brain)
    assistant.run()


if __name__ == "__main__":
    main()
