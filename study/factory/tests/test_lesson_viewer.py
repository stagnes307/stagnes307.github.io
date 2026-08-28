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

    def test_lesson_shell_cache_busts_the_formatted_ff_viewer(self) -> None:
        template = (FACTORY_DIR / "templates" / "lesson.html").read_text(encoding="utf-8")

        self.assertIn("/study/assets/lesson-viewer.js?v=ff-format-1", template)
        self.assertIn("/study/assets/study-factory.css?v=ff-format-1", template)
        self.assertIn('href="{{COURSE_URL}}">목차</a>', template)
        self.assertNotIn("Course 목차", template)
        self.assertIn('id="cc-frame"', template)
        self.assertIn('src="./cc-view.html"', template)

    def test_ff_viewer_formats_only_legacy_ailey_plain_text(self) -> None:
        viewer = (STUDY_DIR / "assets" / "lesson-viewer.js").read_text(encoding="utf-8")
        stylesheet = (STUDY_DIR / "assets" / "study-factory.css").read_text(encoding="utf-8")

        self.assertIn("const isLegacyAiley", viewer)
        self.assertIn("ailey-bailey-custom-gpt", viewer)
        self.assertIn("line.includes('\\t')", viewer)
        self.assertIn("const formatLegacyMarkdown", viewer)
        self.assertIn("marked.parse(markdown, {gfm: true, breaks: legacy})", viewer)
        self.assertIn("DOMPurify.sanitize", viewer)
        self.assertIn("ff-legacy", viewer)
        for marker in (
            ".ff-content h1", ".ff-content h2", ".ff-content h3",
            ".ff-content h4", ".ff-content strong", ".ff-content li::marker",
            ".ff-content code", ".ff-content table", ".ff-content .ff-tags",
            ".ff-content .ff-key-line", ".ff-content .ff-plain-grid",
        ):
            self.assertIn(marker, stylesheet)

    def test_cc_viewer_has_in_mode_navigation(self) -> None:
        template = (FACTORY_DIR / "templates" / "cc-view.html").read_text(encoding="utf-8")

        self.assertIn('src="./cc.html"', template)
        self.assertIn('sandbox="allow-same-origin"', template)
        self.assertIn("{{PREVIOUS_CC_LINK}}", template)
        self.assertIn("{{NEXT_CC_LINK}}", template)
        self.assertIn("{{FLOATING_NEXT_CC_LINK}}", template)
        self.assertIn("cc-viewer.js?v=scroll-direction-1", template)
        self.assertIn(">돌아가기</a>", template)
        self.assertIn(">목차</a>", template)
        self.assertNotIn("FF로 돌아가기", template)
        self.assertNotIn("Course 목차", template)

    def test_mobile_cc_toolbar_hides_and_returns_with_scroll_direction(self) -> None:
        viewer = (STUDY_DIR / "assets" / "cc-viewer.js").read_text(encoding="utf-8")

        self.assertIn("frame.contentDocument?.scrollingElement", viewer)
        self.assertIn("frameWindow?.addEventListener('scroll'", viewer)
        self.assertIn("scrollTop < lastScrollTop", viewer)
        self.assertIn("scrollTop > lastScrollTop", viewer)
        self.assertIn("document.body.classList.toggle('toolbar-hidden'", viewer)
        self.assertIn("matchMedia('(max-width: 680px)')", viewer)


if __name__ == "__main__":
    unittest.main()
