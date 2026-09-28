import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from dev.nao_console import parse_args
from robot.assistant_core import Assistant, KnowledgeBase, MemoryStore, MistralBrain
from robot.nao_hardware import NaoInterface


class FakeRobot:
    def __init__(self):
        self.spoken = []

    def say(self, text):
        self.spoken.append(text)


class FakeBrain:
    MAX_QUESTION_LENGTH = 200
    MAX_CONVERSATION_TURNS = 8

    def __init__(self):
        self.calls = []
        self.api_key = None
        self.memory_contexts = []
        self.conversation_histories = []

    def answer(self, question, context_entries, robot_identity, verbose, memory_entries=None,
               conversation_history=None):
        self.calls.append(question)
        self.memory_contexts.append(memory_entries or [])
        self.conversation_histories.append(list(conversation_history or []))
        return "Réponse Mistral"


class FakeMemory(MemoryStore):
    def __init__(self):
        self.items = []

    def add(self, text):
        self.items.append({"texte": text})
        return True

    def search(self, question):
        return MemoryStore.search(self, question)

    def _read(self):
        return {"souvenirs": self.items}


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
        self.memory = FakeMemory()
        self.assistant = Assistant(self.robot, self.kb, self.brain, self.memory)

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

    def test_mistral_follow_up_receives_previous_local_and_remote_turns(self):
        self.assistant.handle_question("question inconnue")
        self.assistant.handle_question("qui es-tu ?")
        self.assistant.handle_question("Et peux-tu préciser ?")

        self.assertEqual(
            self.brain.conversation_histories[-1],
            [
                {"role": "user", "content": "question inconnue"},
                {"role": "assistant", "content": "Réponse Mistral"},
                {"role": "user", "content": "qui es-tu ?"},
                {"role": "assistant", "content": "Je suis NAO."},
            ],
        )

    def test_conversation_history_keeps_only_recent_eight_turns(self):
        for index in range(10):
            self.assistant.handle_question("question inconnue {0}".format(index))

        self.assertEqual(len(self.assistant.conversation_history), 16)
        self.assertEqual(
            self.assistant.conversation_history[0]["content"],
            "question inconnue 2",
        )

    def test_saved_memory_answers_locally_without_mistral(self):
        self.assistant.handle_question("Souvenir, Mon prénom est Alice")

        answer = self.assistant.handle_question("Quel est mon prénom ?")

        self.assertIn("Alice", answer)
        self.assertEqual(self.brain.calls, [])

    def test_relevant_memory_is_passed_to_mistral(self):
        self.assistant.handle_question("Souvenir, Mon prénom est Alice")
        self.brain.api_key = "test-api-key"

        answer = self.assistant.handle_question("Quel est mon prénom ?")

        self.assertEqual(answer, "Réponse Mistral")
        self.assertEqual(self.brain.memory_contexts[-1][0]["texte"], "Mon prénom est Alice")

    def test_environment_variable_provides_mistral_key(self):
        with patch.dict(os.environ, {"MISTRAL_API_KEY": "environment-key"}):
            with patch.object(sys, "argv", ["main.py"]):
                args = parse_args()

        self.assertEqual(args.mistral_api_key, "environment-key")


class RobotEntryPointTests(unittest.TestCase):
    def test_main_refuses_to_run_outside_python_27(self):
        main_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "robot", "main.py")
        )

        result = subprocess.run(
            [sys.executable, main_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Python 2.7 sur le robot NAO", result.stdout)


class NaoInterfaceTests(unittest.TestCase):
    def test_robot_interface_requires_naoqi_sdk_instead_of_simulating(self):
        with patch.dict(sys.modules, {"naoqi": None}):
            with self.assertRaisesRegex(RuntimeError, "SDK NAOqi est requis"):
                NaoInterface()

    def test_robot_connection_sets_lower_tts_pitch(self):
        proxy = Mock()
        proxy_factory = Mock(return_value=proxy)
        naoqi = SimpleNamespace(ALProxy=proxy_factory)

        with patch.dict(sys.modules, {"naoqi": naoqi}):
            robot = NaoInterface()

        proxy.setParameter.assert_called_once_with("pitchShift", 0.8)
        self.assertIsNotNone(robot.animated_speech)
        self.assertEqual(
            proxy_factory.call_args_list,
            [
                unittest.mock.call("ALTextToSpeech", "127.0.0.1", 9559),
                unittest.mock.call("ALSpeechRecognition", "127.0.0.1", 9559),
                unittest.mock.call("ALMemory", "127.0.0.1", 9559),
                unittest.mock.call("ALAnimatedSpeech", "127.0.0.1", 9559),
            ],
        )

    def test_robot_speaks_with_contextual_body_language(self):
        robot = NaoInterface.__new__(NaoInterface)
        robot.animated_speech = Mock()
        robot.tts = Mock()

        robot.say("Bonjour, je vais expliquer cette œuvre.")

        robot.animated_speech.say.assert_called_once_with(
            "Bonjour, je vais expliquer cette œuvre.",
            {"bodyLanguageMode": "contextual"},
        )
        robot.tts.say.assert_not_called()

    def test_robot_falls_back_to_tts_when_animated_speech_fails(self):
        robot = NaoInterface.__new__(NaoInterface)
        robot.animated_speech = Mock()
        robot.animated_speech.say.side_effect = RuntimeError("service unavailable")
        robot.tts = Mock()

        robot.say("Je continue sans gestes.")

        robot.tts.say.assert_called_once_with("Je continue sans gestes.")


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
        self.assertEqual(
            memory.search("Comment réviser le français ?")[0]["texte"],
            "Révision du français avec NAO",
        )
        self.assertEqual(memory.search("Quel est le prénom de mon chat ?"), [])

    def test_memory_search_matches_prenom_and_appelle_wording(self):
        memory = MemoryStore.__new__(MemoryStore)
        memory.path = "unused"
        memory._read = lambda: {"souvenirs": [{"texte": "Je m'appelle Alice"}]}

        matches = memory.search("Quel est mon prénom ?")

        self.assertEqual(matches[0]["texte"], "Je m'appelle Alice")


class MistralBrainTests(unittest.TestCase):
    def test_request_uses_api_key_and_educational_system_prompt(self):
        response = Mock()
        response.json.return_value = {
            "choices": [{"message": {"content": "Réponse utile"}}]
        }
        requests = SimpleNamespace(post=Mock(return_value=response), RequestException=Exception)
        brain = MistralBrain("test-api-key")
        history = [
            {"role": "user", "content": "Je prépare l'oral."},
            {"role": "assistant", "content": "Quelle œuvre as-tu choisie ?"},
        ]

        with patch.dict(sys.modules, {"requests": requests}):
            answer = brain.answer(
                "Comment réviser ?",
                [],
                memory_entries=[{"texte": "L'élève révise avec Alice"}],
                conversation_history=history,
            )

        self.assertEqual(answer, "Réponse utile")
        request = requests.post.call_args
        self.assertEqual(request[1]["headers"]["Authorization"], "Bearer test-api-key")
        self.assertIn("assistant de Mme Cathelin", request[1]["json"]["messages"][0]["content"])
        messages = request[1]["json"]["messages"]
        self.assertEqual(messages[1:3], history)
        self.assertIn("L'élève révise avec Alice", messages[-1]["content"])
        self.assertIn("Comment réviser ?", messages[-1]["content"])

    def test_api_request_trims_history_to_eight_turns(self):
        response = Mock()
        response.json.return_value = {
            "choices": [{"message": {"content": "Réponse utile"}}]
        }
        requests = SimpleNamespace(post=Mock(return_value=response), RequestException=Exception)
        brain = MistralBrain("test-api-key")
        history = []
        for index in range(10):
            history.extend([
                {"role": "user", "content": "Question {0}".format(index)},
                {"role": "assistant", "content": "Réponse {0}".format(index)},
            ])

        with patch.dict(sys.modules, {"requests": requests}):
            brain.answer("Relance finale", [], conversation_history=history)

        messages = requests.post.call_args[1]["json"]["messages"]
        self.assertEqual(len(messages), 18)
        self.assertEqual(messages[1]["content"], "Question 2")
        self.assertEqual(messages[-2]["content"], "Réponse 9")
        self.assertIn("Relance finale", messages[-1]["content"])

    def test_api_request_obeys_history_character_budget(self):
        response = Mock()
        response.json.return_value = {
            "choices": [{"message": {"content": "Réponse utile"}}]
        }
        requests = SimpleNamespace(post=Mock(return_value=response), RequestException=Exception)
        brain = MistralBrain("test-api-key")
        history = [
            {"role": "user", "content": "a" * 3000},
            {"role": "assistant", "content": "b" * 3000},
            {"role": "user", "content": "question récente"},
            {"role": "assistant", "content": "réponse récente"},
        ]

        with patch.dict(sys.modules, {"requests": requests}):
            brain.answer("Relance", [], conversation_history=history)

        messages = requests.post.call_args[1]["json"]["messages"]
        self.assertEqual(messages[1:3], history[2:])
        self.assertLessEqual(
            sum(len(message["content"]) for message in messages[1:-1]),
            brain.MAX_CONVERSATION_CHARS,
        )


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

    def test_requested_literary_works_are_available_for_revision(self):
        expected = {
            "pour un oui pour un non": ("oeuvre_sarraute", "sous-conversation"),
            "discours de la servitude volontaire": ("oeuvre_laboetie", "tyran"),
            "cahiers de douai": ("oeuvre_rimbaud", "1870"),
            "chevalier à la charrette": ("oeuvre_chretien", "Guenièvre"),
        }

        for question, (entry_id, detail) in expected.items():
            with self.subTest(question=question):
                entry = self.kb.find_keyword_match(question)

                self.assertIsNotNone(entry)
                self.assertEqual(entry["id"], entry_id)
                self.assertIn(detail, entry["reponse_longue"])

    def test_works_have_detailed_exam_metadata_and_memory_keys(self):
        works = {
            "pour un oui ou pour un non": "Educatee/Bac/Oeuvres/Sarraute",
            "discours de la servitude volontaire": "Educatee/Bac/Oeuvres/LaBoetie",
            "cahiers de douai": "Educatee/Bac/Oeuvres/Rimbaud",
            "chevalier de la charrette": "Educatee/Bac/Oeuvres/ChretienDeTroyes",
        }
        with open(self.kb.path, encoding="utf-8") as knowledge_file:
            raw_entries = {
                entry["id"]: entry
                for entry in json.load(knowledge_file)["dialogue_knowledge_base"]
            }

        for question, memory_key in works.items():
            with self.subTest(question=question):
                entry = self.kb.find_keyword_match(question)

                self.assertTrue(raw_entries[entry["id"]].get("notions_cles"))
                self.assertIn(memory_key, self.kb.get_almemory_snapshot())


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
