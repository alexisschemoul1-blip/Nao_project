# -*- coding: utf-8 -*-
"""
Script de validation de l'environnement Python 2.7 + NAOqi
"""
import sys
import platform

print("=" * 60)
print("  VÉRIFICATION DE L'ENVIRONNEMENT PYTHON 2.7 + NAOQI")
print("=" * 60)
print("Python Version : " + sys.version.split()[0])
print("Architecture   : " + str(platform.architecture()))
print("Exécutable     : " + sys.executable)
print("-" * 60)

try:
    import naoqi  # type: ignore
    from naoqi import ALProxy  # type: ignore
    print("[SUCCÈS] Module 'naoqi' chargé avec succès !")
    print("Emplacement : " + naoqi.__file__)
    print("[SUCCÈS] Classe 'ALProxy' disponible : " + str(ALProxy))
except ImportError as e:
    print("[ÉCHEC] Impossible de charger 'naoqi' : " + str(e))
    sys.exit(1)

print("=" * 60)
print("Votre environnement Python 2.7 est 100% prêt à piloter NAO !")
print("=" * 60)
