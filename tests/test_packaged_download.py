import subprocess
import os
import sys
import json
import time

exe_path = os.path.abspath("dist/Aegis Download Manager.exe")
dest_dir = os.path.abspath("test_pkg_dl")
os.makedirs(dest_dir, exist_ok=True)

test_url = "https://raw.githubusercontent.com/curl/curl/master/README.md"
expected_file = os.path.join(dest_dir, "README.md")
result_json = os.path.join(dest_dir, "aegis_cli_result.json")

# Clean prior files if any
for p in [expected_file, result_json]:
    if os.path.exists(p):
        try:
            os.remove(p)
        except Exception:
            pass

print(f"Executing: {exe_path}")
print(f"Download URL: {test_url}")
print(f"Target Destination: {dest_dir}")

cmd = [exe_path, "--download", test_url, "--dest", dest_dir]
t0 = time.time()
proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
stdout, stderr = proc.communicate(timeout=60)
duration = time.time() - t0

print(f"Process return code: {proc.returncode}")
print(f"Execution duration: {duration:.2f}s")
if stdout:
    print(f"stdout: {stdout.decode(errors='replace').strip()}")
if stderr:
    print(f"stderr: {stderr.decode(errors='replace').strip()}")

file_exists = os.path.exists(expected_file)
file_size = os.path.getsize(expected_file) if file_exists else 0
print(f"Downloaded file exists: {file_exists}, size: {file_size} bytes")

res_data = {}
if os.path.exists(result_json):
    with open(result_json, "r", encoding="utf-8") as f:
        res_data = json.load(f)
    print(f"Result JSON: {res_data}")

if file_exists and file_size > 0 and proc.returncode == 0:
    print("\n>>> TEST 7 RESULT: PASS <<<")
    print(f"Verified standalone Windows EXE launched and successfully downloaded: {expected_file} ({file_size} bytes)")
    sys.exit(0)
else:
    print("\n>>> TEST 7 RESULT: FAIL <<<")
    sys.exit(1)
