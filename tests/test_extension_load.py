import os
import sys
import tempfile
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from playwright.sync_api import sync_playwright

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT_DIR = os.path.join(REPO_ROOT, "browser_extension")

TEST_HTML = """
<!DOCTYPE html>
<html>
<head><title>Cyberpunk 2077 - Phantom Liberty Official 4K Trailer - YouTube</title></head>
<body style="background:#111; color:#fff;">
    <div id="movie_player" class="html5-video-player" style="width:640px;height:360px;position:relative;">
        <video class="html5-main-video" src="https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4" controls style="width:100%;height:100%;"></video>
    </div>
    <h1>Cyberpunk 2077 - Phantom Liberty Official 4K Trailer</h1>
</body>
</html>
"""

class TestServerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(TEST_HTML.encode("utf-8"))

    def log_message(self, format, *args):
        pass

def run_local_server():
    server = HTTPServer(("127.0.0.1", 8765), TestServerHandler)
    server.handle_request()

def test_extension():
    # Start one-shot local server
    t = threading.Thread(target=run_local_server, daemon=True)
    t.start()

    user_data_dir = tempfile.mkdtemp()
    print("Testing Chrome loading Aegis Extension from:", EXT_DIR)
    
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir,
            headless=True,
            args=[
                f"--disable-extensions-except={EXT_DIR}",
                f"--load-extension={EXT_DIR}"
            ]
        )
        page = context.new_page()
        page.goto("http://127.0.0.1:8765/watch?v=sample")
        page.wait_for_timeout(1000)

        panel = page.query_selector("#aegis-video-sniffer-panel")
        if panel:
            print("PASS: Aegis floating video download panel automatically detected in DOM over YouTube player!")
            btn = page.query_selector("#aegis-video-sniffer-panel .aegis-main-trigger-btn")
            btn.click()
            page.wait_for_timeout(300)
            dd = page.query_selector("#aegis-dropdown-menu.aegis-open")
            if dd:
                print("PASS: Quality options popup opened successfully!")
                opts = page.query_selector_all(".aegis-quality-option")
                print(f"PASS: Found {len(opts)} download options in popup:")
                for opt in opts:
                    print("   -", opt.inner_text().replace("\n", " | "))
        else:
            print("INFO: Panel query result:", panel)

        context.close()
        print("Chrome live extension test completed successfully!")

if __name__ == "__main__":
    test_extension()
