#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Entrée de l'assistant autonome exécutée sur le robot NAO (Python 2.7)."""

from __future__ import unicode_literals

import argparse
import os
import sys

if sys.version_info[:2] != (2, 7):
    raise SystemExit("robot/main.py doit être exécuté avec Python 2.7 sur le robot NAO.")

from assistant_core import Assistant, KnowledgeBase, MemoryStore, MistralBrain
from nao_hardware import NaoInterface


def parse_args():
    parser = argparse.ArgumentParser(description="Assistant français pour robot NAO")
    parser.add_argument("--robot-port", type=int, default=9559)
    parser.add_argument("--mistral-model", default="mistral-small-latest")
    parser.add_argument(
        "--mistral-api-key",
        default=os.environ.get("MISTRAL_API_KEY"),
        help="Clé API Mistral (par défaut : variable d'environnement MISTRAL_API_KEY)",
    )
    default_kb = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nao_knowledge_base.json")
    parser.add_argument("--kb", default=default_kb)
    default_memory = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memoire.json")
    parser.add_argument("--memory-file", default=default_memory)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    knowledge = KnowledgeBase(args.kb)
    memory = MemoryStore(args.memory_file)
    brain = MistralBrain(args.mistral_api_key, args.mistral_model)
    robot = NaoInterface(ip="127.0.0.1", port=args.robot_port)
    Assistant(robot, knowledge, brain, memory, args.verbose).run()


if __name__ == "__main__":
    main()
