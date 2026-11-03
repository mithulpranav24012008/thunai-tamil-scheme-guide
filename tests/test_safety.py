"""The emergency check and the language check, without Bedrock.

    python -m unittest discover tests

Every emergency case in cases.jsonl must trip the gate and every ordinary case must not; on top of
that, the spoken Tamil, Tanglish and English phrasings below, which people really type.
"""
import json
import unittest
from pathlib import Path

from agent.safety import red_flags
from agent.tools import language_of

ROOT = Path(__file__).resolve().parents[1]

EMERGENCIES = [
    # Spoken Tamil
    ("நெஞ்சு வலிக்குது, மூச்சு வாங்குது", "chest hurts, out of breath"),
    ("நெஞ்சு வலி தாங்க முடியல", "chest pain, can't bear it"),
    ("நெஞ்சுவலி ரொம்ப அதிகமா இருக்கு", "chest pain written as one word"),
    ("மூச்சு விட முடியல", "can't breathe, spoken form"),
    ("அம்மாவுக்கு மூச்சு வாங்குது, பேச முடியல", "mother is breathless"),
    ("சாகணும் போல இருக்கு", "feel like dying"),
    ("செத்துடலாம்னு தோணுது", "thinking of dying"),
    ("வாழ பிடிக்கல, எல்லாத்தையும் முடிச்சுக்கணும்", "don't want to live"),
    ("தூக்க மாத்திரை நிறைய சாப்பிட்டேன்", "took a lot of sleeping pills"),
    ("நிறைய மாத்திரை முழுங்கிட்டேன்", "swallowed a lot of pills"),
    ("அப்பா மயங்கி விழுந்துட்டார்", "father fainted and fell"),
    ("ரத்தம் நிக்கல", "bleeding won't stop"),
    ("பாம்பு கடிச்சிருச்சு", "bitten by a snake"),
    ("விஷம் குடிச்சிட்டான்", "he drank poison"),
    # Tanglish: Tamil typed in English letters
    ("nenju vali, moochu vida mudiyala", "chest pain, can't breathe"),
    ("nenjuvali romba iruku", "a lot of chest pain"),
    ("moochu vaanguthu, help pannunga", "breathless, please help"),
    ("saaganum pola irukku", "feel like dying"),
    ("sethuralam nu thonuthu", "thinking of dying"),
    ("thookka mathirai niraya saapten", "took a lot of sleeping pills"),
    ("appa mayangi vizhundhutaru", "father fainted"),
    ("paambu kadichiduchu", "bitten by a snake"),
    # English, the way people say it
    ("my chest is killing me and I can't catch my breath", "chest pain idiom"),
    ("I cant breathe", "no apostrophe"),
    ("I can’t breathe", "curly apostrophe"),
    ("my father is having a stroke, his face is drooping", "stroke happening now"),
    ("I think I'm dying, everything is spinning", "dying, literally"),
]

ORDINARY = [
    ("I'm dying to get a scholarship for college", "idiom: wants it badly"),
    ("my grandfather had a stroke last year, any pension scheme?", "a past event"),
    ("heat stroke-la padikka mudiyala, bus pass venum", "Tanglish, a bus pass"),
    ("the stroke ward at the hospital is full, is there insurance?", "names a ward"),
    ("enakku health insurance venum, hospital la treatment edukanum", "Tanglish health question"),
    ("SC student, scholarship irukka?", "Tanglish scholarship question"),
    ("என் மகளுக்கு கல்வி உதவித்தொகை வேணும்", "a scholarship question"),
    ("மருத்துவமனை செலவு அதிகமா இருக்கு, scheme இருக்கா?", "hospital costs question"),
    ("my phone is dying, can I apply offline?", "a phone battery"),
]


def cases():
    with open(ROOT / "cases.jsonl", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


class Gate(unittest.TestCase):
    def test_every_emergency_case_trips(self):
        for c in cases():
            if c["expected"]["escalation"] == "emergency":
                with self.subTest(c["id"]):
                    self.assertTrue(red_flags(c["text"]), c["text"])

    def test_no_ordinary_case_trips(self):
        for c in cases():
            if c["expected"]["escalation"] == "none":
                with self.subTest(c["id"]):
                    self.assertEqual(red_flags(c["text"]), [], c["text"])

    def test_spoken_tamil_tanglish_and_english_emergencies(self):
        for text, meaning in EMERGENCIES:
            with self.subTest(meaning=meaning, text=text):
                self.assertTrue(red_flags(text), f"missed: {meaning}")

    def test_ordinary_questions_do_not_trip(self):
        for text, meaning in ORDINARY:
            with self.subTest(meaning=meaning, text=text):
                self.assertEqual(red_flags(text), [], f"false alarm: {meaning}")

    def test_reports_what_it_matched(self):
        self.assertIn("chest pain", red_flags("I'm having chest pain"))


class Language(unittest.TestCase):
    def test_script(self):
        self.assertEqual(language_of("எனக்கு உதவி வேணும்"), "ta")
        self.assertEqual(language_of("I need a scholarship for college"), "en")

    def test_tanglish_is_tamil(self):
        for text in ["enakku health insurance venum", "SC student, scholarship irukka?", "nenju vali, moochu vida mudiyala"]:
            with self.subTest(text):
                self.assertEqual(language_of(text), "ta")

    def test_english_with_a_tamil_name_stays_english(self):
        for text in ["I live in Madurai and need a bus pass", "Is the Amma scheme still open?", "what is the PM-JAY scheme"]:
            with self.subTest(text):
                self.assertEqual(language_of(text), "en")

    def test_labelled_cases(self):
        for c in cases():
            with self.subTest(c["id"]):
                self.assertEqual(language_of(c["text"]), c["lang"], c["text"])


if __name__ == "__main__":
    unittest.main()
