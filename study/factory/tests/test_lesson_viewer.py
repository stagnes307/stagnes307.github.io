from __future__ import annotations

import unittest
from pathlib import Path


FACTORY_DIR = Path(__file__).resolve().parents[1]
STUDY_DIR = FACTORY_DIR.parent


class LessonViewerTest(unittest.TestCase):
    def test_cc_control_opens_the_iframe_document_directly(self) -> None:
        viewer = (STUDY_DIR / "assets" / "lesson-viewer.js").read_text(encoding="utf-8")

        self.assertIn("const openCc = () => location.assign(frame.src);", viewer)
        self.assertIn("if (name === 'cc')", viewer)
        self.assertIn("if (initialTab === 'cc') openCc();", viewer)

    def test_lesson_shell_cache_busts_the_direct_cc_viewer(self) -> None:
        template = (FACTORY_DIR / "templates" / "lesson.html").read_text(encoding="utf-8")

        self.assertIn("/study/assets/lesson-viewer.js?v=cc-direct-1", template)
        self.assertIn('id="cc-frame"', template)
        self.assertIn('src="./cc-view.html"', template)

    def test_cc_viewer_has_in_mode_navigation(self) -> None:
        template = (FACTORY_DIR / "templates" / "cc-view.html").read_text(encoding="utf-8")

        self.assertIn('src="./cc.html"', template)
        self.assertIn("{{PREVIOUS_CC_LINK}}", template)
        self.assertIn("{{NEXT_CC_LINK}}", template)
        self.assertIn("FF로 돌아가기", template)
        self.assertIn("Course 목차", template)


if __name__ == "__main__":
    unittest.main()
