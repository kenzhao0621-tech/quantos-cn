"""Playwright assist — simple Mac broker flow."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from gateway.brokers.playwright_assist import has_saved_session, session_status


class TestPlaywrightAssist(unittest.TestCase):
    def test_session_status_shape(self):
        s = session_status("eastmoney_manual")
        self.assertIn("saved", s)
        self.assertIn("playwright_ready", s)

    @patch("gateway.brokers.playwright_assist.session_path")
    def test_has_saved_session(self, mock_path):
        from pathlib import Path
        p = Path("/tmp/fake.json")
        mock_path.return_value = p
        with patch.object(Path, "exists", return_value=True), patch.object(Path, "stat") as st:
            st.return_value.st_size = 200
            self.assertTrue(has_saved_session("eastmoney_manual"))


if __name__ == "__main__":
    unittest.main()
