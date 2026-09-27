import json
import os
import re
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from robot.main import Assistant, KnowledgeBase, MemoryStore, MistralBrain, NaoInterface


class FakeRobot:
    def __init__(self):
        self.spoken = []

    def say(self, text):
        self.spoken.append(text)


class FakeBrain:
    MAX_QUESTION_LENGTH = 200

    def __init__(self):
        self.calls = []

    def answer(self, question, context_entries, robot_identity, verbose):
        self.calls.append(question)
        return "Réponse Mistral"


class AssistantQuestionTests(unittest.TestCase):
    def setUp(self):
        self.kb_file = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False)
        json.dump({
            "dialogue_knowledge_base": [{
                "id": "presentation",
                "theme": "Présentation",
                "triggers": ["qui es-tu"],
                "nao_tts_short": "Je suis NAO.",
                "nao_tts_long": "Je suis NAO, le robot.",
            }],
        }, self.kb_file)
        self.kb_file.close()
        self.addCleanup(self._remove_kb_file)
        self.kb = KnowledgeBase(self.kb_file.name)
        self.robot = FakeRobot()
        self.brain = FakeBrain()
        self.assistant = Assistant(self.robot, self.kb, self.brain, memory=None)

    def _remove_kb_file(self):
        os.unlink(self.kb_file.name)

    def test_known_answer_uses_local_knowledge(self):
        answer = self.assistant.handle_question("Bonjour, qui es-tu ?")

        self.assertEqual(answer, "Je suis NAO.")
        self.assertEqual(self.brain.calls, [])

    def test_unmatched_question_similar_to_trigger_uses_mistral(self):
        answer = self.assistant.handle_question("qui es tu ?")

        self.assertEqual(answer, "Réponse Mistral")
        self.assertEqual(self.brain.calls, ["qui es tu ?"])

    def test_overlong_unknown_question_skips_mistral(self):
        answer = self.assistant.handle_question("question inconnue " * 12)

        self.assertIn("trop longue", answer)
        self.assertEqual(self.brain.calls, [])

    def test_overlong_question_with_local_answer_uses_knowledge_base(self):
        answer = self.assistant.handle_question(("qui es-tu " * 30))

        self.assertEqual(answer, "Je suis NAO.")
        self.assertEqual(self.brain.calls, [])

    def test_short_unknown_question_uses_mistral(self):
        answer = self.assistant.handle_question("question inconnue")

        self.assertEqual(answer, "Réponse Mistral")
        self.assertEqual(self.brain.calls, ["question inconnue"])


class NaoInterfaceTests(unittest.TestCase):
    def test_robot_connection_sets_lower_tts_pitch(self):
        proxy = Mock()
        naoqi = SimpleNamespace(ALProxy=Mock(return_value=proxy))

        with patch.dict(sys.modules, {"naoqi": naoqi}):
            robot = NaoInterface(ip="127.0.0.1")

        proxy.setParameter.assert_called_once_with("pitchShift", 0.8)
        self.assertFalse(robot.text_mode)


class MemoryStoreTests(unittest.TestCase):
    def test_unicode_memory_is_saved_and_read_as_utf8(self):
        descriptor, path = tempfile.mkstemp()
        os.close(descriptor)
        os.remove(path)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        memory = MemoryStore(path)

        self.assertTrue(memory.add("Révision du français avec NAO"))
        saved = memory._read()["souvenirs"][0]["texte"]

        self.assertEqual(saved, "Révision du français avec NAO")


class MistralBrainTests(unittest.TestCase):
    def test_request_uses_api_key_and_educational_system_prompt(self):
        response = Mock()
        response.json.return_value = {
            "choices": [{"message": {"content": "Réponse utile"}}]
        }
        requests = SimpleNamespace(post=Mock(return_value=response), RequestException=Exception)
        brain = MistralBrain("test-api-key")

        with patch.dict(sys.modules, {"requests": requests}):
            answer = brain.answer("Comment réviser ?", [])

        self.assertEqual(answer, "Réponse utile")
        request = requests.post.call_args
        self.assertEqual(request[1]["headers"]["Authorization"], "Bearer test-api-key")
        self.assertIn("assistant de Mme Cathelin", request[1]["json"]["messages"][0]["content"])


class BacKnowledgeTests(unittest.TestCase):
    def setUp(self):
        kb_path = os.path.join(
            os.path.dirname(__file__), "..", "robot", "nao_knowledge_base.json"
        )
        self.kb = KnowledgeBase(os.path.abspath(kb_path))

    def test_written_exam_modalities_are_available_locally(self):
        entry = self.kb.find_keyword_match("écrit du bac en voie technologique")

        self.assertIsNotNone(entry)
        self.assertIn("contraction de texte", entry["reponse_longue"])

    def test_oral_preparation_and_scoring_are_available_locally(self):
        entry = self.kb.find_keyword_match("combien de temps pour préparer l'oral")

        self.assertIsNotNone(entry)
        self.assertIn("trente minutes de préparation", entry["reponse_longue"])
        self.assertIn("huit points", entry["reponse_longue"])

    def test_written_and_oral_coefficients_are_available_locally(self):
        entry = self.kb.find_keyword_match("coefficient de l'écrit de français")

        self.assertIsNotNone(entry)
        self.assertIn("coefficient cinq", entry["reponse_longue"])


class QiChatTopicTests(unittest.TestCase):
    def test_topic_concepts_are_declared_and_loader_path_exists(self):
        repository = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        topic_path = os.path.join(repository, "robot", "educatee_francais_lycee.top")
        loader_path = os.path.join(repository, "dev", "nao_memory_loader.py")
        with open(topic_path, encoding="utf-8") as topic_file:
            topic = topic_file.read()
        with open(loader_path, encoding="utf-8") as loader_file:
            loader = loader_file.read()

        declared = set(re.findall(r"^concept:\(([^)]+)\)", topic, re.MULTILINE))
        referenced = set(re.findall(r"^u:\(~([^)]+)\)", topic, re.MULTILINE))

        self.assertTrue(os.path.isfile(topic_path))
        self.assertIn("educatee_francais_lycee.top", loader)
        self.assertEqual(referenced - declared, set())


if __name__ == "__main__":
    unittest.main()
