#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Assistant conversationnel NAO.

Une demande contenant un mot-clé de la base reçoit immédiatement la réponse
locale correspondante. Mistral est une option explicite ; sans clé, tout
fonctionne localement.
"""

from __future__ import unicode_literals

import argparse
import difflib
import io
import json
import logging
import os
import re
import tempfile
import time
import unicodedata
from datetime import datetime

try:
    text_type = unicode
    string_types = (basestring,)
    PY2 = True
except NameError:
    text_type = str
    string_types = (str,)
    PY2 = False


def to_text(value):
    if isinstance(value, text_type):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return text_type(value)


def to_naoqi_text(value):
    value = to_text(value)
    return value.encode("utf-8") if PY2 else value


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("nao_assistant")


class KnowledgeBase:
    def __init__(self, path):
        self.path = path
        self.entries = []
        self.robot_identity = {}
        self.almemory_keys = {}
        self._load()

    def _load(self):
        if not os.path.exists(self.path):
            logger.warning("Base de connaissances introuvable : %s", self.path)
            return
        try:
            with io.open(self.path, "r", encoding="utf-8") as file:
                data = json.load(file)
        except (IOError, ValueError) as exc:
            logger.error("Impossible de lire la base de connaissances : %s", exc)
            return

        self.robot_identity = data.get("robot_identity", {})
        self.almemory_keys = data.get("almemory_keys", {})

        if "dialogue_knowledge_base" in data:
            for raw in data["dialogue_knowledge_base"]:
                self.entries.append({
                    "id": raw.get("id", ""),
                    "theme": raw.get("theme", ""),
                    "triggers": raw.get("triggers", []),
                    "reponse_courte": raw.get("nao_tts_short", ""),
                    "reponse_longue": raw.get("nao_tts_long", "") or raw.get("nao_tts_short", ""),
                })
        else:
            for raw in data.get("entries", []):
                self.entries.append({
                    "id": to_text(raw.get("id", "")),
                    "theme": "",
                    "triggers": [raw.get("question", "")] + raw.get("keywords", []),
                    "reponse_courte": raw.get("reponse", ""),
                    "reponse_longue": raw.get("reponse", ""),
                })
        logger.info("Base chargée : %d entrée(s)", len(self.entries))

    @staticmethod
    def _normalise(text):
        text = unicodedata.normalize("NFD", to_text(text).lower())
        text = "".join(char for char in text if unicodedata.category(char) != "Mn")
        return " ".join(text.split())

    def _keyword_is_in_question(self, keyword, question):
        keyword = self._normalise(keyword).strip()
        question = self._normalise(question)
        if len(keyword) < 2:
            return False
        # Les limites évitent qu'un mot court soit trouvé au milieu d'un autre.
        pattern = r"(?<![\w])" + re.escape(keyword) + r"(?![\w])"
        return re.search(pattern, question) is not None

    def find_keyword_match(self, question):
        """Retourne l'entrée locale si un trigger/keyword est présent.

        La correspondance est volontairement directe : pas de similarité
        approximative. Cela évite d'utiliser une réponse locale inadéquate.
        Les mots-clés les plus longs sont prioritaires.
        """
        matches = []
        for index, entry in enumerate(self.entries):
            keywords = list(entry.get("triggers", []))
            if entry.get("theme"):
                keywords.append(entry["theme"])
            for keyword in keywords:
                if self._keyword_is_in_question(keyword, question):
                    matches.append((len(self._normalise(keyword)), -index, entry, keyword))
        if not matches:
            return None
        _, _, entry, keyword = max(matches, key=lambda match: (match[0], match[1]))
        logger.info("Mot-clé local détecté : '%s'", keyword)
        return entry

    def _rank_entries(self, question):
        question = self._normalise(question)
        if not question:
            return []
        scored = []
        for entry in self.entries:
            candidates = [entry.get("theme", "")] + entry.get("triggers", [])
            candidate_scores = [
                difflib.SequenceMatcher(None, question, self._normalise(candidate)).ratio()
                for candidate in candidates if candidate
            ]
            score = max(candidate_scores) if candidate_scores else 0.0
            scored.append((score, entry))
        scored.sort(key=lambda item: item[0], reverse=True)
        return scored

    def search(self, question, top_k=3, min_score=0.3):
        """Recherche de contexte utilisée uniquement pour l'appel Mistral."""
        scored = self._rank_entries(question)
        return [entry for score, entry in scored if score >= min_score][:top_k]

    def get_almemory_snapshot(self):
        return dict(self.almemory_keys)


class MemoryStore:
    """Persists user memories separately from the read-only knowledge base."""

    def __init__(self, path):
        self.path = path
        if not os.path.exists(self.path):
            self._write({"souvenirs": []})
        self._read()

    def _read(self):
        try:
            with io.open(self.path, "r", encoding="utf-8") as memory_file:
                data = json.load(memory_file)
        except (IOError, ValueError) as exc:
            logger.error("Impossible de lire la mémoire utilisateur '%s' : %s", self.path, exc)
            raise
        if not isinstance(data, dict) or not isinstance(data.get("souvenirs"), list):
            raise ValueError("Le fichier mémoire doit contenir une liste 'souvenirs'.")
        return data

    def _write(self, data):
        temporary_path = None
        try:
            directory = os.path.dirname(os.path.abspath(self.path))
            descriptor, temporary_path = tempfile.mkstemp(dir=directory)
            os.close(descriptor)
            with io.open(temporary_path, "w", encoding="utf-8") as memory_file:
                json.dump(data, memory_file, ensure_ascii=False, indent=2)
                memory_file.write(u"\n")
            replace_file = getattr(os, "replace", os.rename)
            replace_file(temporary_path, self.path)
        except (IOError, OSError) as exc:
            logger.error("Impossible d'écrire la mémoire utilisateur '%s' : %s", self.path, exc)
            raise
        finally:
            if temporary_path and os.path.exists(temporary_path):
                try:
                    os.remove(temporary_path)
                except OSError as exc:
                    logger.warning("Impossible de supprimer le fichier temporaire '%s' : %s", temporary_path, exc)

    def add(self, text):
        content = to_text(text).strip()
        if not content:
            return False
        data = self._read()
        data["souvenirs"].append({
            "texte": content,
            "enregistre_le": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        })
        self._write(data)
        return True


class MistralBrain:
    API_URL = "https://api.mistral.ai/v1/chat/completions"
    MAX_QUESTION_LENGTH = 200

    def __init__(self, api_key=None, model="mistral-small-latest"):
        self.api_key = api_key
        self.model = model
        if not self.api_key:
            logger.warning("Aucune clé Mistral fournie : les demandes inconnues resteront en mode local.")

    def answer(self, question, context_entries, robot_identity=None, verbose=False):
        if not self.api_key:
            return "Je n'ai pas encore de réponse à cette question."

        try:
            import requests
        except ImportError as exc:
            logger.error("Mistral indisponible sans la dépendance requests : %s", exc)
            return "Désolé, je ne peux pas répondre pour le moment."

        context = u"\n".join(
            u"- {0}".format(entry.get("reponse_longue" if verbose else "reponse_courte", ""))
            for entry in context_entries
        )
        system = (
            "Tu es NAO, l'assistant de Mme Cathelin. Tu aides les élèves à préparer "
            "le baccalauréat de français. Réponds en français avec des explications "
            "courtes, claires et adaptées à l'oral. Si un contexte est fourni, "
            "utilise-le sans inventer de faits ; si tu ne connais pas une information, "
            "dis-le clairement."
        )
        payload = {
            "model": self.model,
            "temperature": 0.4,
            "max_tokens": 200,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": u"Question : {0}\nContexte : {1}".format(
                    to_text(question), context or u"(aucun contexte local)"
                )},
            ],
        }
        try:
            response = requests.post(
                self.API_URL,
                headers={"Authorization": u"Bearer {0}".format(self.api_key),
                         "Content-Type": "application/json"},
                json=payload,
                timeout=15,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()
        except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as exc:
            logger.error("Erreur Mistral : %s", exc)
            return "Désolé, je ne peux pas répondre pour le moment."


class NaoInterface:
    def __init__(self, ip=None, port=9559, force_text_mode=False):
        self.ip, self.port = ip, port
        self.text_mode = force_text_mode or not ip
        self.tts = self.asr = self.memory = None
        if not self.text_mode:
            self._connect_robot()

    def _connect_robot(self):
        try:
            from naoqi import ALProxy
            self.tts = ALProxy(to_naoqi_text("ALTextToSpeech"), self.ip, self.port)
            self.asr = ALProxy(to_naoqi_text("ALSpeechRecognition"), self.ip, self.port)
            self.memory = ALProxy(to_naoqi_text("ALMemory"), self.ip, self.port)
            try:
                self.tts.setParameter(to_naoqi_text("pitchShift"), 0.8)
            except Exception as exc:
                logger.warning("Impossible d'abaisser la hauteur de la voix TTS : %s", exc)
            logger.info("Connecté au robot NAO à %s:%s", self.ip, self.port)
        except (ImportError, Exception) as exc:
            logger.error("Connexion NAO impossible : %s", exc)
            self.text_mode = True

    def push_knowledge_to_almemory(self, values):
        if self.text_mode:
            return
        for key, value in values.items():
            try:
                self.memory.insertData(to_naoqi_text(key), to_naoqi_text(value))
            except Exception as exc:
                logger.warning("Impossible d'écrire '%s' dans ALMemory : %s", key, exc)

    def say(self, text):
        if not text:
            return
        if self.text_mode:
            output = u"[NAO dit] {0}".format(to_text(text))
            print(output.encode("utf-8") if PY2 else output)
        else:
            try:
                self.tts.say(to_naoqi_text(text))
            except Exception as exc:
                logger.error("Erreur TTS : %s", exc)

    def listen(self):
        if self.text_mode:
            try:
                prompt = u"Question (Ctrl+C pour quitter) > "
                if PY2:
                    return to_text(raw_input(prompt.encode("utf-8"))).strip()
                return input(prompt).strip()
            except EOFError:
                return ""
        try:
            self.asr.setLanguage(to_naoqi_text("French"))
            self.asr.subscribe(to_naoqi_text("nao_assistant"))
            start = time.time()
            while time.time() - start < 15:
                data = self.memory.getData("WordRecognized")
                if isinstance(data, (list, tuple)) and data and isinstance(data[0], string_types):
                    self.asr.unsubscribe(to_naoqi_text("nao_assistant"))
                    return to_text(data[0]).strip()
                time.sleep(0.2)
            self.asr.unsubscribe(to_naoqi_text("nao_assistant"))
        except Exception as exc:
            logger.error("Erreur reconnaissance vocale : %s", exc)
        return ""


class Assistant:
    def __init__(self, robot, kb, brain, memory, verbose=False):
        self.robot, self.kb, self.brain, self.memory, self.verbose = robot, kb, brain, memory, verbose

    def _remember(self, question):
        keyword = "souvenir"
        normalized = question.strip()
        if normalized.lower() == keyword:
            self.robot.say("Dis : Souvenir, suivi de ce que tu veux que je retienne.")
            return True
        if not normalized.lower().startswith(keyword):
            return False

        remainder = normalized[len(keyword):]
        if remainder and not (remainder[0].isspace() or remainder[0] in ",:;-"):
            return False
        content = remainder.lstrip(" \t,.:;-").strip()
        if not content:
            self.robot.say("Indique le souvenir après le mot Souvenir.")
        else:
            try:
                saved = self.memory.add(content)
            except (IOError, OSError, ValueError) as exc:
                logger.error("Impossible d'enregistrer le souvenir : %s", exc)
                self.robot.say("Je n'ai pas pu enregistrer ce souvenir.")
            else:
                if saved:
                    self.robot.say("C'est noté, je garderai ce souvenir.")
                else:
                    self.robot.say("Indique le souvenir après le mot Souvenir.")
        return True

    def handle_question(self, question):
        if not question:
            return ""
        question = to_text(question)
        if self._remember(question):
            return ""

        local_entry = self.kb.find_keyword_match(question)
        if local_entry is not None:
            # Un déclencheur exact permet de répondre sans appel distant.
            key = "reponse_longue" if self.verbose else "reponse_courte"
            answer = local_entry.get(key) or "Je connais ce sujet."
            logger.info("Réponse locale utilisée : aucun appel Mistral.")
        elif len(question) > self.brain.MAX_QUESTION_LENGTH:
            answer = "Ta question est trop longue. Peux-tu la reformuler plus brièvement ?"
            logger.info(
                "Question trop longue (%d caractères) : aucun appel Mistral.",
                len(question),
            )
        else:
            # Mistral n'est appelé que si une clé a été fournie explicitement.
            logger.info("Aucun mot-clé détecté : réponse de secours locale ou Mistral optionnel.")
            answer = self.brain.answer(question, self.kb.search(question), self.kb.robot_identity, self.verbose)

        self.robot.say(answer)
        return answer

    def run(self):
        self.robot.push_knowledge_to_almemory(self.kb.get_almemory_snapshot())
        self.robot.say(u"Bonjour, je suis {0}.".format(
            self.kb.robot_identity.get("nom", "NAO")
        ))
        try:
            while True:
                question = self.robot.listen()
                if not question:
                    continue
                if question.lower() in ("stop", "quitter", "exit", "au revoir"):
                    self.robot.say("À bientôt !")
                    break
                self.handle_question(question)
        except KeyboardInterrupt:
            self.robot.say("À bientôt !")


def parse_args():
    parser = argparse.ArgumentParser(description="Assistant NAO : réponses locales et Mistral optionnel")
    parser.add_argument("--robot-ip", default=None)
    parser.add_argument("--robot-port", type=int, default=9559)
    parser.add_argument("--text-mode", action="store_true")
    default_kb = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nao_knowledge_base.json")
    parser.add_argument("--kb", default=default_kb)
    parser.add_argument("--mistral-model", default="mistral-small-latest")
    parser.add_argument("--mistral-api-key", default=None)
    default_memory = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memoire.json")
    parser.add_argument("--memory-file", default=default_memory)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    kb = KnowledgeBase(args.kb)
    memory = MemoryStore(args.memory_file)
    brain = MistralBrain(args.mistral_api_key, args.mistral_model)
    robot = NaoInterface(args.robot_ip, args.robot_port, args.text_mode)
    Assistant(robot, kb, brain, memory, args.verbose).run()


if __name__ == "__main__":
    main()
