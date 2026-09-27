import json
import os
import tempfile
import unittest

from robot.main import Assistant, KnowledgeBase


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


if __name__ == "__main__":
    unittest.main()
