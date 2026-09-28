#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Shared conversation logic, testable on a development computer."""

from __future__ import unicode_literals

import difflib
import io
import json
import logging
import os
import re
import tempfile
import unicodedata
from datetime import datetime

try:
    text_type = unicode
    string_types = (basestring,)
except NameError:
    text_type = str
    string_types = (str,)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("nao_assistant")

def to_text(value):
    if isinstance(value, text_type):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return text_type(value)


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

    STOP_WORDS = set((
        "alors", "avec", "avoir", "cette", "comment", "dans", "depuis", "des", "donc",
        "elle", "elles", "est", "et", "eux", "faire", "fait", "ici", "ils",
        "je", "la", "le", "les", "leur", "lui", "ma", "mais", "me", "mes",
        "moi", "mon", "ne", "nos", "notre", "nous", "on", "ou", "par", "pas",
        "pour", "que", "quel", "quelle", "quels", "quelles", "qui", "sa", "se",
        "ses", "son", "sur", "ta", "te", "tes", "toi", "ton", "tu", "un", "une",
        "vos", "votre", "vous", "y",
    ))
    TERM_ALIASES = {
        "prenom": "identite",
        "appelle": "identite",
        "appelles": "identite",
        "surnom": "identite",
    }

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

    def search(self, question, top_k=3, min_score=0.34):
        """Finds saved memories sharing meaningful words with the question."""
        question_words = self._search_terms(question)
        if not question_words:
            return []

        ranked = []
        for index, item in enumerate(self._read()["souvenirs"]):
            if not isinstance(item, dict) or not item.get("texte"):
                continue
            memory_words = self._search_terms(item["texte"])
            overlap = question_words.intersection(memory_words)
            score = float(len(overlap)) / len(question_words)
            if overlap and score >= min_score:
                ranked.append((score, index, item))

        ranked.sort(key=lambda match: (match[0], match[1]), reverse=True)
        return [item for score, index, item in ranked[:top_k]]

    def _search_terms(self, text):
        words = re.findall(r"[a-z0-9]+", KnowledgeBase._normalise(text))
        return set(
            self.TERM_ALIASES.get(word, word)
            for word in words
            if len(word) > 2 and word not in self.STOP_WORDS
        )


class MistralBrain:
    API_URL = "https://api.mistral.ai/v1/chat/completions"
    MAX_QUESTION_LENGTH = 200
    MAX_CONVERSATION_TURNS = 8
    MAX_CONVERSATION_CHARS = 6000

    def __init__(self, api_key=None, model="mistral-small-latest"):
        self.api_key = api_key
        self.model = model
        if not self.api_key:
            logger.warning("Aucune clé Mistral fournie : les demandes inconnues resteront en mode local.")

    def answer(self, question, context_entries, robot_identity=None, verbose=False,
               memory_entries=None, conversation_history=None):
        if not self.api_key:
            return "Je n'ai pas encore de réponse à cette question."

        try:
            import requests
        except ImportError as exc:
            logger.error("Mistral indisponible sans la dépendance requests : %s", exc)
            return "Désolé, je ne peux pas répondre pour le moment."

        context_sections = []
        knowledge_context = u"\n".join(
            u"- {0}".format(entry.get("reponse_longue" if verbose else "reponse_courte", ""))
            for entry in context_entries
        )
        if knowledge_context:
            context_sections.append(u"Base pédagogique locale :\n{0}".format(knowledge_context))
        if memory_entries:
            memories = u"\n".join(
                u"- {0}".format(to_text(entry.get("texte", "")))
                for entry in memory_entries
            )
            context_sections.append(
                u"Souvenirs personnels enregistrés pour cet utilisateur :\n{0}".format(memories)
            )
        context = u"\n".join(context_sections)
        system = (
            "Tu es NAO, l'assistant de Mme Cathelin. Tu aides les élèves à préparer "
            "le baccalauréat de français. Réponds en français avec des explications "
            "courtes, claires et adaptées à l'oral. Tiens compte des échanges précédents "
            "pour comprendre les relances. Si un contexte est fourni, "
            "utilise-le sans inventer de faits ; si tu ne connais pas une information, "
            "dis-le clairement."
        )
        messages = [{"role": "system", "content": system}]
        history = []
        history_chars = 0
        history_turns = 0
        previous_messages = conversation_history or []
        for index in range(len(previous_messages) - 2, -1, -2):
            user_message = previous_messages[index]
            assistant_message = previous_messages[index + 1]
            if (
                user_message.get("role") != "user"
                or assistant_message.get("role") != "assistant"
            ):
                continue
            turn_chars = len(user_message.get("content", "")) + len(
                assistant_message.get("content", "")
            )
            if (
                history_turns >= self.MAX_CONVERSATION_TURNS
                or history_chars + turn_chars > self.MAX_CONVERSATION_CHARS
            ):
                break
            history[0:0] = [user_message, assistant_message]
            history_chars += turn_chars
            history_turns += 1
        messages.extend(history)
        messages.append({
            "role": "user",
            "content": u"Question : {0}\nContexte : {1}".format(
                to_text(question), context or u"(aucun contexte local)"
            ),
        })
        payload = {
            "model": self.model,
            "temperature": 0.4,
            "max_tokens": 200,
            "messages": messages,
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


class Assistant:
    def __init__(self, robot, kb, brain, memory, verbose=False):
        self.robot, self.kb, self.brain, self.memory, self.verbose = robot, kb, brain, memory, verbose
        self.conversation_history = []

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

        memories = self.memory.search(question)
        local_entry = self.kb.find_keyword_match(question)
        if local_entry is not None:
            key = "reponse_longue" if self.verbose else "reponse_courte"
            answer = local_entry.get(key) or "Je connais ce sujet."
            if memories:
                remembered_text = u" ; ".join(
                    to_text(entry.get("texte", "")) for entry in memories
                )
                answer = u"{0} Je me souviens aussi que {1}".format(answer, remembered_text)
            logger.info("Réponse locale utilisée : aucun appel Mistral.")
        else:
            has_mistral_key = bool(getattr(self.brain, "api_key", None))
            if memories and (
                not has_mistral_key or len(question) > self.brain.MAX_QUESTION_LENGTH
            ):
                remembered_text = u" ; ".join(
                    to_text(entry.get("texte", "")) for entry in memories
                )
                answer = u"Je me souviens que {0}".format(remembered_text)
                logger.info("Réponse issue de la mémoire utilisateur : aucun appel Mistral.")
            elif len(question) > self.brain.MAX_QUESTION_LENGTH:
                answer = "Ta question est trop longue. Peux-tu la reformuler plus brièvement ?"
                logger.info(
                    "Question trop longue (%d caractères) : aucun appel Mistral.",
                    len(question),
                )
            else:
                logger.info("Aucun mot-clé détecté : réponse Mistral ou de secours locale.")
                answer = self.brain.answer(
                    question,
                    self.kb.search(question),
                    self.kb.robot_identity,
                    self.verbose,
                    memory_entries=memories,
                    conversation_history=self.conversation_history,
                )

        self.conversation_history.extend([
            {"role": "user", "content": question},
            {"role": "assistant", "content": to_text(answer)},
        ])
        max_history_messages = self.brain.MAX_CONVERSATION_TURNS * 2
        if len(self.conversation_history) > max_history_messages:
            self.conversation_history = self.conversation_history[-max_history_messages:]

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
