#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""NAOqi hardware adapter used only by the robot runtime."""

from __future__ import unicode_literals

import time

try:
    from .assistant_core import logger, string_types, to_text
except (ImportError, ValueError):
    from assistant_core import logger, string_types, to_text


def to_naoqi_text(value):
    value = to_text(value)
    try:
        unicode
    except NameError:
        return value
    return value.encode("utf-8")

class NaoInterface:
    def __init__(self, ip="127.0.0.1", port=9559):
        self.ip, self.port = ip, port
        self.tts = self.asr = self.memory = self.animated_speech = None
        self._connect_robot()

    def _connect_robot(self):
        try:
            from naoqi import ALProxy
        except ImportError:
            raise RuntimeError(
                "Le SDK NAOqi est requis pour exécuter l'assistant sur le robot."
            )

        try:
            self.tts = ALProxy(to_naoqi_text("ALTextToSpeech"), self.ip, self.port)
            self.asr = ALProxy(to_naoqi_text("ALSpeechRecognition"), self.ip, self.port)
            self.memory = ALProxy(to_naoqi_text("ALMemory"), self.ip, self.port)
        except Exception as exc:
            logger.error("Connexion aux services NAOqi impossible : %s", exc)
            raise RuntimeError("Impossible de se connecter aux services NAOqi.")

        try:
            self.animated_speech = ALProxy(
                to_naoqi_text("ALAnimatedSpeech"), self.ip, self.port
            )
        except Exception as exc:
            logger.warning("Gestes vocaux NAO indisponibles : %s", exc)
        try:
            self.tts.setParameter(to_naoqi_text("pitchShift"), 0.8)
        except Exception as exc:
            logger.warning("Impossible d'abaisser la hauteur de la voix TTS : %s", exc)
        logger.info("Connecté au robot NAO à %s:%s", self.ip, self.port)

    def push_knowledge_to_almemory(self, values):
        for key, value in values.items():
            try:
                self.memory.insertData(to_naoqi_text(key), to_naoqi_text(value))
            except Exception as exc:
                logger.warning("Impossible d'écrire '%s' dans ALMemory : %s", key, exc)

    def say(self, text):
        if not text:
            return
        if self.animated_speech is not None:
            try:
                self.animated_speech.say(
                    to_naoqi_text(text),
                    {"bodyLanguageMode": to_naoqi_text("contextual")},
                )
                return
            except Exception as exc:
                logger.warning("Échec de la parole animée NAO : %s", exc)
        try:
            self.tts.say(to_naoqi_text(text))
        except Exception as exc:
            logger.error("Erreur TTS : %s", exc)

    def listen(self):
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
