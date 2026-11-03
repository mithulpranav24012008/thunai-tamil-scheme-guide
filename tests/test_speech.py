"""Tests for the speech module: cleanup, language picking, file handling.

    python -m unittest discover tests
"""
import os
import tempfile
import unittest
import wave
from unittest.mock import patch, MagicMock

from agent import speech


class TestCleanup(unittest.TestCase):
    def test_cleanup_deletes_file(self):
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        self.assertTrue(os.path.isfile(path))
        speech.cleanup(path)
        self.assertFalse(os.path.isfile(path))

    def test_cleanup_silent_on_missing(self):
        speech.cleanup("/nonexistent/path/to/file.wav")
        speech.cleanup("")


class TestPickLanguageCode(unittest.TestCase):
    def test_tamil_script(self):
        self.assertEqual(speech.pick_language_code("எனக்கு வலி"), "ta-IN")

    def test_tanglish(self):
        self.assertEqual(speech.pick_language_code("enakku vali padugiren"), "ta-IN")

    def test_english(self):
        self.assertEqual(speech.pick_language_code("I need help"), "en-IN")

    def test_mixed_tamil_english(self):
        self.assertEqual(speech.pick_language_code("எனக்கு insurance venum"), "ta-IN")


class TestTranscribeFile(unittest.TestCase):
    def test_missing_file_raises_filenotfound(self):
        with self.assertRaises(FileNotFoundError):
            speech.transcribe_file("/nonexistent/audio.wav")

    def test_transcribe_file_returns_dict_format(self):
        """Mock the amazon_transcribe package and verify return format."""
        fd, tmp_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        with wave.open(tmp_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b"\x00" * 3200)

        try:
            mock_module = MagicMock()
            mock_client = MagicMock()
            mock_stream = MagicMock()
            mock_result = MagicMock()
            mock_alt = MagicMock()
            mock_alt.transcript = "hello"
            mock_alt.confidence = 0.9
            mock_result.transcript.results = [mock_result]
            mock_result.is_partial = False
            mock_stream.output_stream = [mock_result]
            mock_client.start_stream_transcription.return_value = mock_stream
            mock_module.TranscribeStreamingClient.return_value = mock_client

            with patch.dict("sys.modules", {"amazon_transcribe": mock_module,
                                             "amazon_transcribe.client": mock_module,
                                             "amazon_transcribe.handlers": mock_module}):
                result = speech.transcribe_file(tmp_path, "ta-IN")

            self.assertIsInstance(result, dict)
            self.assertIn("transcript", result)
            self.assertIn("confidence", result)
            self.assertIn("is_low_confidence", result)
            self.assertIn("language_code", result)
            self.assertEqual(result["language_code"], "ta-IN")
        finally:
            speech.cleanup(tmp_path)


if __name__ == "__main__":
    unittest.main()
