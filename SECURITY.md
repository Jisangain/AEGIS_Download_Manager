# Security

## Scope and architecture

Aegis is a local desktop application built with Python/PyQt6. The application queues downloads in SQLite, invokes aria2 and yt-dlp where configured, and includes a Chromium browser extension connected through native messaging and local IPC. The reviewed code includes the desktop UI, download engine, archive extraction and automation helpers, native host, and browser extension. The separate `frontend/` Electron prototype is incomplete and is not the packaged PyQt application; it was not assessed as a supported release path.

The extension requests access across sites and observes browser download/media activity to provide link handoff. It communicates with the native host, which passes download requests to the desktop UI. Download URLs and filenames are user/browser supplied inputs. Aegis supports HTTP as well as HTTPS; HTTP does not provide transport encryption.

## Review performed

On 2026-10-28, the repository received a source-level security review focused on download transport, URL and message handling, filename/path use, process invocation, Defender scanning, archive extraction, IPC, extension DOM insertion, and dependency/build configuration. This review also retained findings and fixes from the earlier focused audit documented in `security_best_practices_report.md`.

The following checks were run in the current working tree:

- `python -m unittest test_security -v`: 7 focused security regression tests passed, including ZIP/TAR traversal rejection, TAR link rejection, normal ZIP extraction, Defender invocation/result handling, and aria2 certificate-validation configuration.
- `python test_file_management_automation.py`: 4 existing automation checks passed. The test output included a Defender result marked as flagged for its test input; this does not establish that a real malicious file was detected.
- `python test_new_features.py`: 5 feature checks passed when run with a temporary profile directory inside the workspace. The first attempt could not write to the environment’s default Downloads location.
- `python -m py_compile automation.py engine.py test_security.py` and `git diff --check` passed during the review.

These are source and regression checks, not a complete penetration test. They do not establish the security of every feature or packaged binary.

## Findings and remediation

| ID | Severity | Finding | Status and evidence |
| --- | --- | --- | --- |
| AEGIS-SEC-001 | High | aria2 previously disabled HTTPS certificate verification. | **Fixed.** aria2 now receives `--check-certificate=true`. A mocked invocation regression test verifies the setting; no live invalid-certificate test was run. |
| AEGIS-SEC-002 | Medium | TAR extraction previously used a string-prefix containment check that could permit traversal outside the chosen directory. | **Fixed.** ZIP/TAR member paths are checked with normalized, component-aware containment; absolute paths, traversal, links, and special TAR entries are rejected. Tests cover ZIP/TAR traversal, TAR symbolic links, and normal ZIP extraction. Resource quotas are not implemented (see below). |
| AEGIS-SEC-003 | Medium | A Defender fallback previously embedded a file path in PowerShell source. | **Fixed.** The path is passed as an environment value and read as data. A regression test covers a path containing an apostrophe and verifies it is absent from the command string. |
| AEGIS-SEC-004 | Medium | Unexpected Defender exit codes could be presented as a clean scan; the fallback also made an unverified clean claim. | **Fixed.** Only the expected clean result is reported as clean; unknown/error results are inconclusive, and the fallback no longer claims verification. Focused tests cover these cases. |

The fixes above are present in the reviewed working tree. Their presence does not mean a new release containing them has been published.

## Remaining risks and unverified areas

- **URL privacy in local logs and storage:** the native host writes incoming URLs to its log, and download URLs are stored in the local SQLite database. URLs can contain credentials or signed query parameters. Redaction and retention behavior have not been verified as sufficient; avoid sharing logs/database files without reviewing them.
- **Filename/path validation:** filenames are accepted from UI and browser-mediated input and are joined with the chosen save directory in multiple code paths. Consistent rejection of path separators and traversal components across all download paths has not been established. Treat this as an unresolved path-validation concern; add centralized validation and regression tests.
- **Archive resource exhaustion:** extraction rejects traversal and unsafe TAR entries but does not enforce total expanded size, member-count, or compression-ratio limits. A hostile archive may consume substantial disk, memory, or CPU.
- **Browser permissions:** the extension requests broad host access and runs a content script across sites. This supports media/link detection but gives the extension visibility into pages covered by those permissions. The permission set should be minimized if product behavior permits.
- **Network destinations and redirects:** no systematic SSRF/LAN-target or redirect-policy assessment was performed for user-entered URLs, crawler URLs, or downloader redirects. HTTP is supported and is not encrypted.
- **IPC and platform isolation:** message structure and native-host flow were reviewed, but no adversarial multi-process or cross-user IPC testing was performed. Windows named-pipe access-control behavior was not independently validated.
- **Dependencies and bundled tools:** `requirements.txt` uses lower bounds without a pinned Python lock file. Bandit and pip-audit were unavailable, so static analysis and dependency vulnerability scanning were not run. Bundled or externally configured aria2, ffmpeg, yt-dlp components, and packaged executables were not independently audited.
- **Release testing:** no isolated Windows VM test, packaged-binary malware analysis, fuzzing, live TLS failure test, or full browser matrix test was performed. The Electron prototype and Linux packaged artifact were not tested as release binaries.

## Reporting a vulnerability

Please report suspected vulnerabilities privately through GitHub’s **Report a vulnerability** feature for this repository, if enabled. If private reporting is unavailable, contact the maintainer through the GitHub profile and request a private channel. Include the affected version, impact, and a minimal reproduction where safe. Do not publish sensitive data or exploit details before coordinating a fix.

No response-time commitment or coordinated disclosure policy is currently established in this repository.

## Supported versions and updates

The repository does not currently define a formal supported-version matrix or security update SLA. Check the [GitHub releases page](https://github.com/jaberDevHub/AEGIS_Download_Manager/releases) for published versions and update to the latest available release. Security fixes in the working tree are not available to users until included in a published build.
