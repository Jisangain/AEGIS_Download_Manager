import io
import os
import tarfile
import tempfile
import unittest
import zipfile
from types import SimpleNamespace
from unittest.mock import patch

import automation
import engine


class ArchiveExtractionSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = self.temp_dir.name
        self.destination = os.path.join(self.root, "safe")
        os.makedirs(self.destination)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_tar_parent_traversal_is_rejected(self):
        archive = os.path.join(self.root, "traversal.tar")
        with tarfile.open(archive, "w") as tf:
            data = b"must not escape"
            member = tarfile.TarInfo("../safe-escape/proof.txt")
            member.size = len(data)
            tf.addfile(member, io.BytesIO(data))

        ok, _ = automation.extract_archive_safe(archive, self.destination)

        self.assertFalse(ok)
        self.assertFalse(os.path.exists(os.path.join(self.root, "safe-escape", "proof.txt")))

    def test_zip_parent_traversal_is_rejected(self):
        archive = os.path.join(self.root, "traversal.zip")
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("../safe-escape/proof.txt", "must not escape")

        ok, _ = automation.extract_archive_safe(archive, self.destination)

        self.assertFalse(ok)
        self.assertFalse(os.path.exists(os.path.join(self.root, "safe-escape", "proof.txt")))

    def test_tar_symbolic_links_are_rejected(self):
        archive = os.path.join(self.root, "symlink.tar")
        with tarfile.open(archive, "w") as tf:
            link = tarfile.TarInfo("pivot")
            link.type = tarfile.SYMTYPE
            link.linkname = "../outside"
            tf.addfile(link)

        ok, _ = automation.extract_archive_safe(archive, self.destination)

        self.assertFalse(ok)
        self.assertFalse(os.path.lexists(os.path.join(self.destination, "pivot")))

    def test_normal_zip_still_extracts(self):
        archive = os.path.join(self.root, "normal.zip")
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("folder/file.txt", "safe content")

        ok, _ = automation.extract_archive_safe(archive, self.destination)

        self.assertTrue(ok)
        with open(os.path.join(self.destination, "folder", "file.txt"), encoding="utf-8") as f:
            self.assertEqual(f.read(), "safe content")


class DefenderSecurityTests(unittest.TestCase):
    def test_fallback_path_is_passed_as_data_not_powershell_source(self):
        filepath = os.path.abspath("user's file.txt")
        fake_result = SimpleNamespace(returncode=0, stdout="", stderr="")

        with patch.object(automation.sys, "platform", "win32"), \
             patch.object(automation.os.path, "exists", side_effect=lambda path: path == filepath), \
             patch.object(automation.subprocess, "run", return_value=fake_result) as run:
            clean, message = automation.run_windows_defender_scan(filepath)

        self.assertFalse(clean, "PowerShell fallback must not claim a verified clean result")
        self.assertIn("cannot verify", message)
        args, kwargs = run.call_args
        self.assertNotIn(filepath, " ".join(args[0]))
        self.assertEqual(kwargs["env"]["AEGIS_SCAN_TARGET"], filepath)

    def test_unexpected_mpcmdrun_exit_code_is_not_clean(self):
        filepath = os.path.abspath("scan-target.txt")
        fake_result = SimpleNamespace(returncode=5, stdout="", stderr="")

        def exists(path):
            return path in (filepath, r"C:\Program Files\Windows Defender\MpCmdRun.exe")

        with patch.object(automation.sys, "platform", "win32"), \
             patch.object(automation.os.path, "exists", side_effect=exists), \
             patch.object(automation.subprocess, "run", return_value=fake_result):
            clean, message = automation.run_windows_defender_scan(filepath)

        self.assertFalse(clean)
        self.assertIn("inconclusive", message)


class DownloadTransportSecurityTests(unittest.TestCase):
    def test_aria2_keeps_tls_certificate_validation_enabled(self):
        process = SimpleNamespace(stdout=io.StringIO(""), poll=lambda: 1, wait=lambda: 1)
        with tempfile.TemporaryDirectory() as temp_dir, \
             patch.object(engine, "prevent_sleep"), \
             patch.object(engine, "find_tool_binary", return_value="aria2c.exe"), \
             patch.object(engine.subprocess, "Popen", return_value=process) as popen:
            worker = engine.Aria2Worker(1, "https://example.test/file.bin", "file.bin", temp_dir)
            worker.run()

        command = popen.call_args.args[0]
        self.assertIn("--check-certificate=true", command)
        self.assertNotIn("--check-certificate=false", command)


if __name__ == "__main__":
    unittest.main()
