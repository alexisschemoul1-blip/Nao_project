#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Console simulator for developing and testing NAO conversations on a PC."""

import argparse
import os
import sys
import tempfile

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from robot.assistant_core import Assistant, KnowledgeBase, MemoryStore, MistralBrain


class ConsoleInterface:
    def push_knowledge_to_almemory(self, values):
        print("[SIMULATION] {} clés mémoire disponibles.".format(len(values)))

    def say(self, text):
        print("[NAO dit] {}".format(text))

    def listen(self):
        try:
            return input("Question (Ctrl+C pour quitter) > ").strip()
        except EOFError:
            self.running = False
            return "quitter"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Simulation console de l'assistant NAO (ordinateur uniquement)"
    )
    parser.add_argument("--mistral-model", default="mistral-small-latest")
    parser.add_argument(
        "--mistral-api-key",
        default=os.environ.get("MISTRAL_API_KEY"),
        help="Clé API Mistral (par défaut : variable d'environnement MISTRAL_API_KEY)",
    )
    parser.add_argument(
        "--kb",
        default=os.path.join(PROJECT_DIR, "robot", "nao_knowledge_base.json"),
    )
    parser.add_argument(
        "--memory-file",
        default=os.path.join(tempfile.gettempdir(), "nao_console_memoire.json"),
    )
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    knowledge = KnowledgeBase(args.kb)
    memory = MemoryStore(args.memory_file)
    brain = MistralBrain(args.mistral_api_key, args.mistral_model)
    robot = ConsoleInterface()
    Assistant(robot, knowledge, brain, memory, args.verbose).run()


if __name__ == "__main__":
    main()
