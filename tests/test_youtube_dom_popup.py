"""
Aegis Download Manager - DOM Stream Sniffer & YouTube Popup Test
Verifies that the Aegis floating video download panel injects into the YouTube video DOM,
opens the quality dropdown popup, and triggers the download payload.
"""

import os
import sys
import json
import time
from playwright.sync_api import sync_playwright

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXT_DIR = os.path.join(REPO_ROOT, "browser_extension")
CONTENT_JS_PATH = os.path.join(EXT_DIR, "content.js")
CONTENT_CSS_PATH = os.path.join(EXT_DIR, "content.css")

def run_test():
    with open(CONTENT_JS_PATH, "r", encoding="utf-8") as f:
        content_js = f.read()

    with open(CONTENT_CSS_PATH, "r", encoding="utf-8") as f:
        content_css = f.read()

    # YouTube mock page HTML
    youtube_html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Cyberpunk 2077 - Phantom Liberty Official 4K Trailer - YouTube</title>
        <style>
            body { margin: 0; background-color: #0f0f0f; color: #fff; font-family: Roboto, Arial, sans-serif; }
            #content { max-width: 1200px; margin: 20px auto; padding: 0 16px; }
            #player-container { width: 100%; max-width: 960px; height: 540px; background: #000; position: relative; }
            #movie_player { width: 100%; height: 100%; position: relative; background: #111; overflow: hidden; }
            video.html5-main-video { width: 100%; height: 100%; object-fit: contain; }
            h1.title { font-size: 20px; font-weight: 600; margin-top: 14px; }
        </style>
    </head>
    <body>
        <div id="content">
            <div id="player-container">
                <div id="movie_player" class="html5-video-player">
                    <video class="html5-main-video" src="https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4" controls autoplay></video>
                </div>
            </div>
            <h1 class="title">
                <yt-formatted-string>Cyberpunk 2077 - Phantom Liberty Official 4K Trailer</yt-formatted-string>
            </h1>
        </div>
    </body>
    </html>
    """

    print("Launching Playwright Chromium...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        # Track messages dispatched by content script
        sent_messages = []
        page.expose_function("onChromeRuntimeMessage", lambda msg: sent_messages.append(msg))

        page.on("console", lambda msg: print("PAGE CONSOLE:", msg.text))
        page.on("pageerror", lambda err: print("PAGE ERROR:", err))

        # Mock chrome.runtime in page
        mock_chrome_script = """
        window.chrome = {
            runtime: {
                sendMessage: function(msg, callback) {
                    window.onChromeRuntimeMessage(msg);
                    if (callback) callback({ status: "ok" });
                },
                onMessage: {
                    addListener: function() {}
                }
            }
        };
        """
        page.add_init_script(mock_chrome_script)

        page.set_content(youtube_html)
        page.evaluate(mock_chrome_script)
        
        # Inject extension CSS and JS
        page.add_style_tag(content=content_css)
        try:
            page.evaluate(content_js)
        except Exception as e:
            print("EVAL ERROR:", e)

        time.sleep(0.5)

        # 1. Verify Floating Panel in DOM
        panel = page.query_selector("#aegis-video-sniffer-panel")
        if not panel:
            print("FAILED: #aegis-video-sniffer-panel not found in DOM!")
            sys.exit(1)
        print("PASS: #aegis-video-sniffer-panel successfully injected above YouTube player.")

        # 2. Verify button label
        btn_text = page.inner_text("#aegis-video-sniffer-panel .aegis-main-trigger-btn")
        print(f"PASS: Trigger button found with label: '{btn_text.strip()}'")

        # 3. Click trigger button to open dropdown popup
        trigger_btn = page.query_selector("#aegis-video-sniffer-panel .aegis-main-trigger-btn")
        trigger_btn.click()
        time.sleep(0.2)

        dropdown = page.query_selector("#aegis-dropdown-menu.aegis-open")
        if not dropdown:
            print("FAILED: Quality dropdown popup did not open on click!")
            sys.exit(1)
        print("PASS: Quality dropdown popup opened with .aegis-open class.")

        # 4. Inspect available quality options
        options = page.query_selector_all(".aegis-quality-option")
        print(f"PASS: Found {len(options)} download stream quality options in the popup:")
        for opt in options:
            print("   -", opt.inner_text().replace("\n", " | "))

        # Take screenshot of the open popup for visual verification
        screenshot_path = os.path.join(REPO_ROOT, "tests", "assets", "youtube_dom_popup_screenshot.png")
        page.screenshot(path=screenshot_path)
        print(f"PASS: Saved visual screenshot to: {screenshot_path}")

        # 5. Click on the 1080p Full HD option
        opt_1080p = None
        for opt in options:
            if "1080p" in opt.inner_text():
                opt_1080p = opt
                break

        if not opt_1080p:
            print("FAILED: 1080p option not found in dropdown!")
            sys.exit(1)

        opt_1080p.click()
        time.sleep(0.3)

        # 6. Verify confirmation toast in DOM
        toast = page.query_selector(".aegis-success-toast")
        if toast:
            print(f"PASS: Confirmation toast appeared in DOM: '{toast.inner_text()}'")
        else:
            print("WARNING: Toast element not detected immediately.")

        # 7. Verify message payload sent to Aegis
        if len(sent_messages) > 0:
            msg = sent_messages[-1]
            print("PASS: Payload successfully dispatched to Aegis Download Manager:")
            print(json.dumps(msg, indent=2))
        else:
            print("FAILED: No message dispatched on quality selection!")
            sys.exit(1)

        browser.close()
        print("\nALL DOM YOUTUBE SNIFFER POPUP TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_test()
