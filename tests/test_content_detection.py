import unittest

from content_detection import detect_content_type, detect_language, is_code


class ContentDetectionTests(unittest.TestCase):
    def test_python_is_not_misclassified_as_php(self):
        source = """from pathlib import Path

def read_name(path: Path) -> str:
    if path.exists():
        return path.read_text()
    return None
"""
        self.assertEqual(detect_language(source), "Python")
        self.assertEqual(is_code(source), 1)

    def test_php_requires_php_evidence(self):
        source = """<?php
function greet($name) {
    echo "Hello " . $name;
}
"""
        self.assertEqual(detect_language(source), "PHP")

    def test_javascript_does_not_fall_into_php(self):
        source = """const greet = (name) => {
    console.log(`Hello ${name}`);
};
"""
        self.assertEqual(detect_language(source), "JS")

    def test_common_words_stay_text(self):
        prose = "Please return the document to the class when the review is complete."
        self.assertEqual(detect_language(prose), "Text")
        self.assertEqual(is_code(prose), 0)

    def test_json_and_links(self):
        self.assertEqual(detect_language('{\n  "ready": true\n}'), "JSON")
        self.assertEqual(detect_content_type("https://example.com/path?q=1"), "link")


if __name__ == "__main__":
    unittest.main()
