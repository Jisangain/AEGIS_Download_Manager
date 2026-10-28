# Aegis Download Manager — Quick Security Review and Fixes

**Date:** 2026-10-28  
**Scope:** Python download/automation/native-host code and the browser extension. This was a quick source review plus a targeted archive-extraction proof of concept, not a complete penetration test or formal audit.

## Summary

The review found four issues. All four have now been fixed, and seven focused regression tests pass. A crafted TAR archive was confirmed to write outside the selected extraction directory before the fix; the same traversal and link cases are now rejected.

## Findings

### AEGIS-SEC-001 — High: aria2 did not verify HTTPS certificates — Fixed

**Location:** `engine.py:399`

The aria2 command previously included `--check-certificate=false`, disabling certificate validation for HTTPS downloads and allowing an on-path attacker to impersonate a download server.

**Fix:** aria2 now receives `--check-certificate=true` (`engine.py:399`), preserving normal certificate validation.

### AEGIS-SEC-002 — Medium: TAR extraction escaped the chosen directory — Fixed

**Location:** `automation.py:193–294`

The former string-prefix guard allowed sibling paths whose names began with the destination name. A crafted TAR member named `../safe-escape/proof.txt` was confirmed to write outside the selected `safe` directory.

This is most relevant when automatic archive extraction is enabled (`ui.py:2712`) or a user extracts an untrusted archive.

**Fix:** Extraction now validates normalized paths with `os.path.commonpath`, rejects absolute paths, traversal, symlinks, hard links, and special TAR entries, then writes regular files explicitly. ZIP and TAR traversal, TAR symlink, and normal ZIP extraction regression tests pass (`test_security.py:23–69`).

### AEGIS-SEC-003 — Medium: PowerShell fallback could interpret a file path as a command — Fixed

**Location:** `automation.py:147–166`; called for automatic scans at `ui.py:2711–2716`.

The fallback previously inserted `filepath` inside PowerShell source. A path containing an apostrophe could terminate the quoted value and add commands; this affected the fallback path when Defender’s executable lookup failed.

**Fix:** The fallback now passes the absolute file path through the `AEGIS_SCAN_TARGET` environment variable; the fixed PowerShell script reads it as data. A regression test uses a path containing an apostrophe and confirms the path is absent from the command string (`test_security.py:72–84`).

### AEGIS-SEC-004 — Medium: unexpected Defender exit codes were reported as clean — Fixed

**Location:** `automation.py:160–178`; the UI displays `clean=True` as “Defender Scan Passed” at `ui.py:2715–2719`.

The previous implementation treated every nonzero code other than `2` as clean, so an error or unknown scanner result could appear as a passed scan. The PowerShell fallback also claimed “no threats detected” without checking the result.

**Fix:** Only the expected clean-success result from MpCmdRun returns clean. Threat, error, and unknown codes return false/inconclusive. The PowerShell fallback now reports its result as unverified instead of claiming a clean scan. Regression tests cover an unknown exit code and this fallback behavior (`test_security.py:72–103`).

## Checks performed and limits

- Reviewed download transport, filename handling, Defender invocation, archive extraction, IPC, native-message validation, and extension DOM insertion points.
- The original local TAR traversal proof of concept confirmed the issue. After the fix, `python -m unittest test_security -v` passed all seven focused tests, including traversal rejection and normal ZIP extraction.
- A mocked aria2 invocation confirms certificate validation is enabled and the disabling flag is absent.
- `python -m py_compile automation.py engine.py test_security.py` and `git diff --check` passed.
- Bandit and pip-audit are not installed in this environment, so automated source/dependency scans were not run. `requirements.txt` uses lower-bound versions without a lock file, so the exact dependency set cannot be reproduced from that file alone.
- I did not run malware samples, fuzz the packaged application, or test in an isolated Windows VM. This review does not establish that the whole application is secure.
