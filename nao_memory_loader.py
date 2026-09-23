# -*- coding: utf-8 -*-
"""
NAO Memory Loader - Module Mémoire EDUCATEE pour Robot NAO (SoftBank Robotics / NAOqi)
Source de la mémoire : educatee.fr (par Cécile Cathelin)

Fonctions :
1. Injection des clés dans ALMemory (accès rapide par scripts Python ou boîtes Choregraphe).
2. Chargement du fichier QiChat (.top) dans ALDialog pour les conversations orales.
3. Mode simulation autonome sur PC si aucun robot NAO physique n'est connecté.
"""

import sys
import os
import json
import argparse

# Compatibilité Python 2 et 3 pour la saisie console
try:
    input = raw_input  # type: ignore
except NameError:
    pass

# Chemin des ressources locales
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
KB_JSON_PATH = os.path.join(BASE_DIR, "nao_knowledge_base.json")
QICHAT_TOP_PATH = os.path.join(BASE_DIR, "dialogue_bac_et_seconde.top")


def load_local_knowledge():
    with open(KB_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def connect_and_inject_nao(ip="127.0.0.1", port=9559):
    """
    Connecte le script au robot NAO via NAOqi et injecte la mémoire Educatee.
    """
    try:
        from naoqi import ALProxy  # type: ignore
    except ImportError:
        print("[AVERTISSEMENT] Module 'naoqi' introuvable sur cette machine.")
        print("[INFO] Basculement automatique en mode SIMULATION locale.\n")
        return run_local_simulation()

    print("[INFO] Connexion au robot NAO à l'adresse {}:{}...".format(ip, port))
    try:
        memory = ALProxy("ALMemory", ip, port)
        tts = ALProxy("ALTextToSpeech", ip, port)
        dialog = ALProxy("ALDialog", ip, port)
    except Exception as e:
        print("[ERREUR] Impossible de se connecter au robot : {}".format(e))
        print("[INFO] Lancement de la simulation locale.\n")
        return run_local_simulation()

    kb = load_local_knowledge()
    keys = kb.get("almemory_keys", {})

    print("[INFO] Injection de {} clés de connaissances dans ALMemory...".format(len(keys)))
    for key, value in keys.items():
        memory.insertData(key, value)
        print("  + ALMemory['{}'] OK".format(key))

    # Configuration de la langue et voix
    try:
        tts.setLanguage("French")
    except Exception:
        pass

    # Chargement du topic QiChat
    if os.path.exists(QICHAT_TOP_PATH):
        try:
            dialog.setLanguage("French")
            topic_name = dialog.loadTopic(QICHAT_TOP_PATH)
            dialog.activateTopic(topic_name)
            dialog.subscribe("EducateeDialog")
            print("[INFO] Topic QiChat '{}' chargé et activé avec succès dans ALDialog !".format(topic_name))
        except Exception as e:
            print("[ERREUR] Échec du chargement QiChat : {}".format(e))

    welcome = "Bonjour ! Ma mémoire a été mise à jour avec les cours de seconde et du bac de français depuis le site Educatée."
    print("[NAO TTS] {}".format(welcome))
    try:
        tts.say(welcome)
    except Exception:
        pass

    print("[SUCCÈS] Mémoire Educatée prête et active sur le robot NAO.")


def run_local_simulation():
    """
    Simulateur de mémoire NAO en console interactive.
    Permet de tester les réponses vocales TTS et la recherche d'intentions.
    """
    kb = load_local_knowledge()
    qa_list = kb.get("dialogue_knowledge_base", [])
    memory_keys = kb.get("almemory_keys", {})

    print("=" * 65)
    print("      SIMULATION DE MÉMOIRE POUR ROBOT NAO (EDUCATEE)")
    print("=" * 65)
    print("Robot       : {} ({})".format(kb['robot_identity']['nom'], kb['robot_identity']['role']))
    print("Source      : {}".format(kb['robot_identity']['source_exclusive']))
    print("Clés mémoire: {} clés disponibles".format(len(memory_keys)))
    print("Intents vocaux: {} thématiques prêtes".format(len(qa_list)))
    print("=" * 65)
    print("Commandes disponibles :")
    print("  - Tapez un mot-clé ou une question (ex: 'bac', 'seconde', 'sarraute', 'oral')")
    print("  - Tapez 'cles' pour lister les clés ALMemory")
    print("  - Tapez 'quitter' pour sortir\n")

    while True:
        try:
            user_input = input("Élève / Utilisateur > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input:
            continue
        if user_input in ["quitter", "exit", "quit", "q"]:
            print("Arrêt de la simulation.")
            break
        if user_input == "cles":
            print("\n--- CLÉS ALMEMORY DISPONIBLES ---")
            for k, v in memory_keys.items():
                print("[{}] : {}...".format(k, v[:75]))
            print()
            continue

        # Recherche de correspondance dans la base d'intents
        match = None
        for item in qa_list:
            for trig in item.get("triggers", []):
                if trig in user_input or user_input in trig:
                    match = item
                    break
            if match:
                break

        if match:
            print("\n[NAO - Synthèse Vocale TTS] :")
            print('"{}"\n'.format(match['nao_tts_long']))
        else:
            print("\n[NAO - Synthèse Vocale TTS] :")
            print("\"Je n'ai pas bien compris. Tu peux me questionner sur le programme de seconde, les épreuves du bac, la méthode de dissertation, ou les œuvres comme Rimbaud, La Boétie et Sarraute !\"\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Chargeur de mémoire Educatée pour Robot NAO")
    parser.add_argument("--ip", default="127.0.0.1", help="Adresse IP du robot NAO (défaut: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=9559, help="Port NAOqi (défaut: 9559)")
    parser.add_argument("--simu", action="store_true", help="Forcer le mode simulation PC")

    args = parser.parse_args()

    if args.simu:
        run_local_simulation()
    else:
        connect_and_inject_nao(ip=args.ip, port=args.port)
