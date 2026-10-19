import os
import sys
import struct
import json
import subprocess
import time
import winreg

def test_pipeline():
    print("=== AEGIS DOWNLOAD MANAGER END-TO-END PIPELINE TEST ===")
    
    # 1. Registry verification
    reg_key = r"Software\Google\Chrome\NativeMessagingHosts\com.aegis.downloadmanager"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_key) as key:
            val, _ = winreg.QueryValueEx(key, "")
            print(f"[OK] Chrome registry key points to: {val}")
            if not os.path.isfile(val):
                print(f"[FAIL] Manifest file does not exist: {val}")
                return False
    except Exception as e:
        print(f"[FAIL] Registry lookup failed: {e}")
        return False

    # 2. Manifest verification
    with open(val, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    print(f"[OK] Manifest path: {manifest.get('path')}")
    print(f"[OK] Allowed origins count: {len(manifest.get('allowed_origins', []))}")
    host_exe = manifest.get("path")
    if not os.path.isfile(host_exe):
        print(f"[FAIL] aegis_host.exe does not exist at: {host_exe}")
        return False

    # 3. Native messaging simulation
    payload = {
        "action": "download",
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "filename": "Rick_Astley_Never_Gonna_Give_You_Up.mp4",
        "format_id": "bestvideo[height<=1080]+bestaudio/best"
    }
    encoded = json.dumps(payload).encode("utf-8")
    header = struct.pack("@I", len(encoded))
    
    print("[RUN] Sending native messaging payload to aegis_host.exe...")
    start_t = time.time()
    proc = subprocess.Popen(
        [host_exe],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    out, err = proc.communicate(input=header + encoded, timeout=15)
    elapsed = time.time() - start_t
    print(f"[INFO] Process completed in {elapsed:.2f}s, returncode: {proc.returncode}")
    
    if len(out) < 4:
        print(f"[FAIL] Output length < 4 bytes! Raw out: {out}, err: {err}")
        return False
        
    resp_len = struct.unpack("@I", out[:4])[0]
    resp_body = out[4:4+resp_len].decode("utf-8")
    print(f"[OK] Native Host Response Received: {resp_body}")
    
    # 4. Check log file
    app_data = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "AegisDownloadManager")
    log_file = os.path.join(app_data, "aegis_host.log")
    if os.path.isfile(log_file):
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        print("\n=== LAST 5 LOG ENTRIES FROM aegis_host.log ===")
        for line in lines[-5:]:
            print("  ", line.strip())

    print("\n[SUCCESS] End-to-end native messaging loop verified successfully!")
    return True

if __name__ == "__main__":
    success = test_pipeline()
    sys.exit(0 if success else 1)
