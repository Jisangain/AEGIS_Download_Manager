import subprocess
import time
import os
import sys

exe_path = os.path.abspath("dist/Aegis Download Manager.exe")
print(f"Testing execution of: {exe_path}")
print(f"File exists: {os.path.exists(exe_path)}, size: {os.path.getsize(exe_path):,} bytes")

# Launch the executable
proc = subprocess.Popen([exe_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
print(f"Launched process with PID: {proc.pid}")

# Wait 5 seconds to verify it remains alive and doesn't crash on startup
time.sleep(5)
poll = proc.poll()
if poll is None:
    print(f"SUCCESS: Process {proc.pid} is running stably without crashes.")
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
    print("Process terminated cleanly after verification.")
else:
    stdout, stderr = proc.communicate()
    print(f"FAILURE: Process exited with code {poll}")
    print(f"stdout: {stdout.decode(errors='replace')}")
    print(f"stderr: {stderr.decode(errors='replace')}")
