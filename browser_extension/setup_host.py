"""
Aegis Download Manager - Browser Integration Setup
Executes Stage 1 (Native Host Registration & Verification) and Stage 2 (Extension Inspection).
"""

import os
import sys
import json
import winreg
from typing import List, Dict, Tuple, Set

EXT_DIR = os.path.dirname(os.path.abspath(__file__))
CHROME_MANIFEST = os.path.join(EXT_DIR, "com.aegis.downloadmanager.json")
EDGE_MANIFEST = os.path.join(EXT_DIR, "com.aegis.downloadmanager.edge.json")
HOST_EXE = os.path.join(EXT_DIR, "aegis_host.exe")
HOST_BAT = os.path.join(EXT_DIR, "aegis_host.bat")

BROWSER_PREF_PATHS = [
    ("Google Chrome", os.path.expanduser(r"~\AppData\Local\Google\Chrome\User Data\Default\Secure Preferences")),
    ("Google Chrome", os.path.expanduser(r"~\AppData\Local\Google\Chrome\User Data\Default\Preferences")),
    ("Brave Browser", os.path.expanduser(r"~\AppData\Local\BraveSoftware\Brave-Browser\User Data\Default\Secure Preferences")),
    ("Brave Browser", os.path.expanduser(r"~\AppData\Local\BraveSoftware\Brave-Browser\User Data\Default\Preferences")),
    ("Microsoft Edge", os.path.expanduser(r"~\AppData\Local\Microsoft\Edge\User Data\Default\Secure Preferences")),
    ("Microsoft Edge", os.path.expanduser(r"~\AppData\Local\Microsoft\Edge\User Data\Default\Preferences")),
]

def scan_installed_extensions() -> Dict[str, Set[str]]:
    """Scans browser preferences to detect installed Aegis extension IDs."""
    detected = {"Google Chrome": set(), "Brave Browser": set(), "Microsoft Edge": set()}
    norm_ext_dir = os.path.normpath(EXT_DIR).lower()

    for browser_name, pref_path in BROWSER_PREF_PATHS:
        if not os.path.exists(pref_path):
            continue
        try:
            with open(pref_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            exts = data.get("extensions", {}).get("settings", {})
            for ext_id, ext_info in exts.items():
                inst_path = os.path.normpath(ext_info.get("path", "")).lower()
                name = ext_info.get("manifest", {}).get("name", "").lower()
                if inst_path == norm_ext_dir or "aegis download manager" in name:
                    detected[browser_name].add(ext_id)
        except Exception:
            pass
    return detected

def run_stage_1(detected_ids: Set[str]) -> bool:
    """Stage 1: Verify host, generate manifests, register in registry, and verify registration."""
    print("\n========================================================")
    print("STAGE 1: Native Messaging Host Installation & Verification")
    print("========================================================")

    # 1. Verify host binary
    if os.path.exists(HOST_EXE):
        target_bin = HOST_EXE
        print(f"[OK] Found native host executable: {target_bin}")
    elif os.path.exists(HOST_BAT):
        target_bin = HOST_BAT
        print(f"[WARN] Native host executable missing; using fallback batch: {target_bin}")
    else:
        print(f"[ERROR] Native host executable not found in {EXT_DIR}!")
        return False

    # 2. Build allowed_origins list
    base_ids = {"olhghfhliadcobalbkamekmbdgcgmhee", "icdicciedmiojchchcagghmpkbenkccj"}
    all_ids = sorted(list(base_ids | detected_ids))

    chrome_origins = [f"chrome-extension://{eid}/" for eid in all_ids]
    edge_origins = [f"chrome-extension://{eid}/" for eid in all_ids] + [f"edge-extension://{eid}/" for eid in all_ids]

    # 3. Write Chrome manifest
    chrome_manifest_data = {
        "name": "com.aegis.downloadmanager",
        "description": "Aegis Download Manager Native Messaging Host",
        "path": target_bin,
        "type": "stdio",
        "allowed_origins": chrome_origins
    }
    with open(CHROME_MANIFEST, "w", encoding="utf-8") as f:
        json.dump(chrome_manifest_data, f, indent=2)
    print(f"[OK] Generated Chrome/Brave manifest: {CHROME_MANIFEST}")

    # 4. Write Edge manifest
    edge_manifest_data = {
        "name": "com.aegis.downloadmanager",
        "description": "Aegis Download Manager Native Messaging Host",
        "path": target_bin,
        "type": "stdio",
        "allowed_origins": edge_origins
    }
    with open(EDGE_MANIFEST, "w", encoding="utf-8") as f:
        json.dump(edge_manifest_data, f, indent=2)
    print(f"[OK] Generated Microsoft Edge manifest: {EDGE_MANIFEST}")

    # 5. Register in Windows Registry
    registrations = [
        ("Google Chrome (64-bit)", r"Software\Google\Chrome\NativeMessagingHosts\com.aegis.downloadmanager", CHROME_MANIFEST),
        ("Google Chrome (32-bit)", r"Software\Wow6432Node\Google\Chrome\NativeMessagingHosts\com.aegis.downloadmanager", CHROME_MANIFEST),
        ("Brave Browser (64-bit)", r"Software\BraveSoftware\Brave-Browser\NativeMessagingHosts\com.aegis.downloadmanager", CHROME_MANIFEST),
        ("Brave Browser (32-bit)", r"Software\Wow6432Node\BraveSoftware\Brave-Browser\NativeMessagingHosts\com.aegis.downloadmanager", CHROME_MANIFEST),
        ("Microsoft Edge (64-bit)", r"Software\Microsoft\Edge\NativeMessagingHosts\com.aegis.downloadmanager", EDGE_MANIFEST),
        ("Microsoft Edge (32-bit)", r"Software\Wow6432Node\Microsoft\Edge\NativeMessagingHosts\com.aegis.downloadmanager", EDGE_MANIFEST),
    ]

    all_registered = True
    for label, subkey, manifest_file in registrations:
        try:
            k = winreg.CreateKey(winreg.HKEY_CURRENT_USER, subkey)
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, manifest_file)
            winreg.CloseKey(k)
        except Exception as e:
            print(f"[ERROR] Failed to register {label}: {e}")
            all_registered = False

    if not all_registered:
        return False

    # 6. Verify registrations
    print("\nVerifying Native Host Registry Integrity:")
    all_verified = True
    for label, subkey, expected_manifest in registrations:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, subkey) as k:
                val, _ = winreg.QueryValueEx(k, "")
                if val.lower() == expected_manifest.lower() and os.path.exists(val):
                    print(f"  - {label}: [VERIFIED]")
                else:
                    print(f"  - {label}: [FAILED] Mismatch or missing file ({val})")
                    all_verified = False
        except Exception as e:
            print(f"  - {label}: [FAILED] {e}")
            all_verified = False

    return all_verified

def run_stage_2(detected: Dict[str, Set[str]]):
    """Stage 2: Browser extension status and loading guidance."""
    print("\n========================================================")
    print("STAGE 2: Browser Extension Installation Status")
    print("========================================================")

    all_installed = True
    for browser in ("Google Chrome", "Brave Browser", "Microsoft Edge"):
        ids = detected.get(browser, set())
        if ids:
            id_str = ", ".join(ids)
            print(f"  - {browser}: [INSTALLED] (Extension ID: {id_str})")
        else:
            print(f"  - {browser}: [REQUIRES MANUAL LOADING]")
            all_installed = False

    if not all_installed:
        print("\nNote on Chromium Extension Security:")
        print("  Under standard Chromium security policies, unpacked extensions cannot")
        print("  be silently loaded into browser profiles via scripts.")
        print("\nTo load the Aegis extension in your browser:")
        print("  1. Open your browser extensions page:")
        print("     - Chrome: chrome://extensions")
        print("     - Brave:  brave://extensions")
        print("     - Edge:   edge://extensions")
        print("  2. Enable 'Developer mode' toggle (top right corner).")
        print("  3. Click 'Load unpacked' and select this folder:")
        print(f"     \"{EXT_DIR}\"")

def main():
    detected_by_browser = scan_installed_extensions()
    detected_all = set()
    for s in detected_by_browser.values():
        detected_all.update(s)

    stage_1_ok = run_stage_1(detected_all)
    run_stage_2(detected_by_browser)

    print("\n========================================================")
    print("INSTALLATION SUMMARY")
    print("========================================================")
    if stage_1_ok:
        print("Native Host:       [INSTALLED & VERIFIED]")
    else:
        print("Native Host:       [INSTALLATION FAILED]")

    for b in ("Google Chrome", "Brave Browser", "Microsoft Edge"):
        st = "INSTALLED" if detected_by_browser.get(b) else "REQUIRES MANUAL LOADING"
        print(f"{b:<18} [{st}]")
    print("========================================================")

if __name__ == "__main__":
    main()
