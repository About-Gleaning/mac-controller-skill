import argparse
import contextlib
import importlib.util
import io
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APPS_PATH = ROOT / "scripts" / "apps.py"


spec = importlib.util.spec_from_file_location("apps_script", APPS_PATH)
apps = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(apps)


class AppsScriptTests(unittest.TestCase):
    def assert_exits_silently(self, expected_code, action):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as context:
                action()
        self.assertEqual(context.exception.code, expected_code)

    def test_text_literal_escapes_applescript_payload(self):
        self.assertEqual(apps.text_literal('Safari "工作"'), '"Safari \\"工作\\""')
        self.assertEqual(apps.text_literal(None), "missing value")

    def test_normalize_permission_error(self):
        message = apps.normalize_error("execution error: Not authorized to send Apple events. (-1743)")
        self.assertIn("权限", message)
        self.assertIn("辅助功能", message)

    def test_validate_pagination_rejects_large_limit(self):
        args = argparse.Namespace(limit=51, offset=0)
        self.assert_exits_silently(2, lambda: apps.validate_pagination(args))

    def test_open_requires_exactly_one_target(self):
        parser = apps.build_parser()
        self.assert_exits_silently(
            2,
            lambda: parser.parse_args(["open", "--name", "Safari", "--bundle-id", "com.apple.Safari"]),
        )

    def test_focus_window_requires_index_or_title(self):
        parser = apps.build_parser()
        self.assert_exits_silently(2, lambda: parser.parse_args(["focus-window", "--name", "Safari"]))

    def test_open_path_must_be_absolute_app_directory(self):
        with self.assertRaises(argparse.ArgumentTypeError) as context:
            apps.validate_app_path("Safari.app")
        self.assertIn("绝对路径", str(context.exception))

    def test_running_script_contains_pagination_contract(self):
        parser = apps.build_parser()
        args = parser.parse_args(["running", "--query", "Safari", "--limit", "10", "--offset", "5"])
        script = apps.build_running_script(args)
        self.assertIn("set limitValue to 10", script)
        self.assertIn("set offsetValue to 5", script)
        self.assertIn('"apps"', script)

    def test_focus_window_title_reports_ambiguous_matches(self):
        parser = apps.build_parser()
        args = parser.parse_args(["focus-window", "--name", "Safari", "--title", "文档"])
        script = apps.build_focus_window_script(args)
        self.assertIn("匹配到多个窗口", script)
        self.assertIn("titleFilter", script)


if __name__ == "__main__":
    unittest.main()
