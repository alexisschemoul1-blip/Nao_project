#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Assistant conversationnel NAO.

Une demande contenant un mot-clé de la base reçoit immédiatement la réponse
locale correspondante. Les autres demandes sont envoyées à Mistral.
"""

import argparse
import difflib
import json
import logging
import os
import re
import time
import unicodedata
from typing import Dict, List, Optional

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("nao_assistant")


class KnowledgeBase:
    def __init__(self, path: str):
        self.path = path
        self.entries: List[Dict] = []
        self.robot_identity: Dict = {}
        self.almemory_keys: Dict = {}
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.path):
            logger.warning("Base de connaissances introuvable : %s", self.path)
            return
        try:
            with open(self.path, "r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError) as exc:
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
                    "id": str(raw.get("id", "")),
                    "theme": "",
                    "triggers": [raw.get("question", "")] + raw.get("keywords", []),
                    "reponse_courte": raw.get("reponse", ""),
                    "reponse_longue": raw.get("reponse", ""),
                })
        logger.info("Base chargée : %d entrée(s)", len(self.entries))

    @staticmethod
    def _normalise(text: str) -> str:
        text = unicodedata.normalize("NFD", str(text).lower())
        text = "".join(char for char in text if unicodedata.category(char) != "Mn")
        return " ".join(text.split())

    def _keyword_is_in_question(self, keyword: str, question: str) -> bool:
        keyword = self._normalise(keyword).strip()
        question = self._normalise(question)
        if len(keyword) < 2:
            return False
        # Les limites évitent qu'un mot court soit trouvé au milieu d'un autre.
        pattern = r"(?<![\w])" + re.escape(keyword) + r"(?![\w])"
        return re.search(pattern, question) is not None

    def find_keyword_match(self, question: str):
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
        _, _, entry, keyword = max(matches)
        logger.info("Mot-clé local détecté : '%s'", keyword)
        return entry

    def search(self, question: str, top_k: int = 3, min_score: float = 0.3) -> List[Dict]:
        """Recherche de contexte utilisée uniquement pour l'appel Mistral."""
        question = self._normalise(question)
        scored = []
        for entry in self.entries:
            candidates = [entry.get("theme", "")] + entry.get("triggers", [])
            score = max(
                (difflib.SequenceMatcher(None, question, self._normalise(candidate)).ratio()
                 for candidate in candidates if candidate),
                default=0.0,
            )
            scored.append((score, entry))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [entry for score, entry in scored if score >= min_score][:top_k]

    def get_almemory_snapshot(self) -> Dict:
        return dict(self.almemory_keys)


class MistralBrain:
    API_URL = "https://api.mistral.ai/v1/chat/completions"

    def __init__(self, api_key: Optional[str] = None, model: str = "mistral-small-latest"):
        self.api_key = api_key or os.environ.get("MISTRAL_API_KEY") or os.environ.get("Mistral_API")
        self.model = model
        if not self.api_key:
            logger.warning("Aucune clé MISTRAL_API_KEY : les demandes inconnues ne pourront pas être traitées par Mistral.")

    def answer(self, question: str, context_entries: List[Dict],
               robot_identity: Optional[Dict] = None, verbose: bool = False) -> str:
        if not self.api_key:
            return "Je n'ai pas encore de réponse à cette question."

        context = "\n".join(
            f"- {entry.get('reponse_longue' if verbose else 'reponse_courte', '')}"
            for entry in context_entries
        )
        system = (
            "Tu es le cerveau conversationnel d'un robot NAO. Réponds en français, "
            "avec une réponse courte, claire et adaptée à l'oral. "
            "Si un contexte est fourni, utilise-le sans inventer de faits."
        )
        payload = {
            "model": self.model,
            "temperature": 0.4,
            "max_tokens": 200,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": f"Question : {question}\nContexte : {context or '(aucun contexte local)'}"},
            ],
        }
        try:
            response = requests.post(
                self.API_URL,
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=15,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()
        except (requests.RequestException, KeyError, IndexError, TypeError, ValueError) as exc:
            logger.error("Erreur Mistral : %s", exc)
            return "Désolé, je ne peux pas répondre pour le moment."


class NaoInterface:
    def __init__(self, ip: Optional[str] = None, port: int = 9559, force_text_mode: bool = False):
        self.ip, self.port = ip, port
        self.text_mode = force_text_mode or not ip
        self.tts = self.asr = self.memory = None
        if not self.text_mode:
            self._connect_robot()

    def _connect_robot(self) -> None:
        try:
            from naoqi import ALProxy
            self.tts = ALProxy("ALTextToSpeech", self.ip, self.port)
            self.asr = ALProxy("ALSpeechRecognition", self.ip, self.port)
            self.memory = ALProxy("ALMemory", self.ip, self.port)
            logger.info("Connecté au robot NAO à %s:%s", self.ip, self.port)
        except (ImportError, Exception) as exc:
            logger.error("Connexion NAO impossible : %s", exc)
            self.text_mode = True

    def push_knowledge_to_almemory(self, values: Dict) -> None:
        if self.text_mode:
            return
        for key, value in values.items():
            try:
                self.memory.insertData(key, value)
            except Exception as exc:
                logger.warning("Impossible d'écrire '%s' dans ALMemory : %s", key, exc)

    def say(self, text: str) -> None:
        if not text:
            return
        if self.text_mode:
            print(f"[NAO dit] {text}")
        else:
            try:
                self.tts.say(str(text))
            except Exception as exc:
                logger.error("Erreur TTS : %s", exc)

    def listen(self) -> str:
        if self.text_mode:
            try:
                return input("Question (Ctrl+C pour quitter) > ").strip()
            except EOFError:
                return ""
        try:
            self.asr.setLanguage("French")
            self.asr.subscribe("nao_assistant")
            start = time.time()
            while time.time() - start < 15:
                data = self.memory.getData("WordRecognized")
                if isinstance(data, (list, tuple)) and data and isinstance(data[0], str):
                    self.asr.unsubscribe("nao_assistant")
                    return data[0].strip()
                time.sleep(0.2)
            self.asr.unsubscribe("nao_assistant")
        except Exception as exc:
            logger.error("Erreur reconnaissance vocale : %s", exc)
        return ""


class Assistant:
    def __init__(self, robot: NaoInterface, kb: KnowledgeBase, brain: MistralBrain, verbose: bool = False):
        self.robot, self.kb, self.brain, self.verbose = robot, kb, brain, verbose

    def handle_question(self, question: str) -> str:
        if not question:
            return ""

        local_entry = self.kb.find_keyword_match(question)
        if local_entry is not None:
            # Mot-clé trouvé : réponse basique immédiate, sans appel à l'IA.
            key = "reponse_longue" if self.verbose else "reponse_courte"
            answer = local_entry.get(key) or "Je connais ce sujet."
            logger.info("Réponse locale utilisée : aucun appel Mistral.")
        else:
            # Aucun mot-clé trouvé : Mistral répond par défaut.
            logger.info("Aucun mot-clé détecté : appel Mistral.")
            answer = self.brain.answer(question, self.kb.search(question), self.kb.robot_identity, self.verbose)

        self.robot.say(answer)
        return answer

    def run(self) -> None:
        self.robot.push_knowledge_to_almemory(self.kb.get_almemory_snapshot())
        self.robot.say(f"Bonjour, je suis {self.kb.robot_identity.get('nom', 'NAO')}.")
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Assistant NAO : réponses locales puis Mistral par défaut")
    parser.add_argument("--robot-ip", default=None)
    parser.add_argument("--robot-port", type=int, default=9559)
    parser.add_argument("--text-mode", action="store_true")
    parser.add_argument("--kb", default="knowledge_base.json")
    parser.add_argument("--mistral-model", default="mistral-small-latest")
    parser.add_argument("--mistral-api-key", default=None)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    kb = KnowledgeBase(args.kb)
    brain = MistralBrain(args.mistral_api_key, args.mistral_model)
    robot = NaoInterface(args.robot_ip, args.robot_port, args.text_mode)
    Assistant(robot, kb, brain, args.verbose).run()


if __name__ == "__main__":
    main()
