import subprocess
import time
import platform
import sys
import os
from pathlib import Path
import requests

#For debug
from ftfy import fix_text
from bs4 import BeautifulSoup


from playwright.sync_api import sync_playwright as p

# ─────────────────────────────────────────────────────────────────────
# 1. CONFIGURATION: adjust these paths/flags for your setup
# ─────────────────────────────────────────────────────────────────────

# Path to your Chrome/Chromium binary:
#  • On Windows it might be under Program Files
#  • On macOS: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
#  • On Linux: "google-chrome" or "chromium"
CHROME_PATH = {
    "Windows": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "Darwin": "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "Linux": "google-chrome"
}[platform.system()]

# The profile you’re already signed into:
#  • On Windows: usually in %LOCALAPPDATA%\Google\Chrome\User Data\Default
#  • macOS: ~/Library/Application Support/Google/Chrome/Default
#  • Linux: ~/.config/google-chrome/Default
def make_profile_dir(app_name="MyApp"):
    """
    Returns a Path to a writable profile/data directory for your tool,
    creating it if necessary. Works on Windows, macOS, and Linux.
    """
    system = sys.platform
    home   = Path.home()

    if system.startswith("win"):
        # On Windows, use %LOCALAPPDATA%
        base = Path(os.getenv("LOCALAPPDATA", home / "AppData" / "Local"))
        profile_dir = base / app_name / "browser"
    elif system == "darwin":
        # On macOS, use ~/Library/Application Support
        profile_dir = home / "Library" / "Application Support" / app_name / "browser"
    else:
        # On Linux/Unix, follow XDG spec or fallback to ~/.config
        xdg = os.getenv("XDG_CONFIG_HOME", home / ".config")
        profile_dir = Path(xdg) / app_name / "browser"

    profile_dir.mkdir(parents=True, exist_ok=True)
    return profile_dir
USER_DATA_DIR = make_profile_dir()

# DevTools port
DEBUG_PORT = 9222

# How long to wait (seconds) for Chrome to open its DevTools
STARTUP_TIMEOUT = 10.0


#Launch Chrome with remote-debugging, login if needed
def launch_chrome():
    cmd = [
        CHROME_PATH,
        f"--remote-debugging-port={DEBUG_PORT}",
        f"--user-data-dir={USER_DATA_DIR}",
        # optionally force a specific profile subfolder:
        # f"--profile-directory=Default",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    print("Launching Chrome:", " ".join(cmd))
    # Use Popen so it doesn’t block this script
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    wait_for_cdp(DEBUG_PORT)
    return proc


#Wait for DevTools endpoint to be available and ask the user to login if needed
def wait_for_cdp(port, timeout=STARTUP_TIMEOUT):
    url = f"http://127.0.0.1:{port}/json/version"
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = requests.get(url)
            if resp.status_code == 200:
                print("DevTools endpoint is live.")
                return True
        except requests.ConnectionError:
            pass
        time.sleep(0.2)
    raise RuntimeError(f"Timed out waiting for Chrome DevTools on port {port}")


# Get all the necessary components to work with web
def getWeb(port=DEBUG_PORT):
    
    
    #Start playwright
    pw = p().start()

    #Connect playwright with the running Chrome
    ws_url = f"http://127.0.0.1:{port}"
    print("Connecting Playwright over CDP to", ws_url)
    browser = pw.chromium.connect_over_cdp(ws_url)

    # Choose the context & create a new page you want (usually your first/open tab)
    context = browser.contexts[0]
    page = context.pages[0]

    return [pw, browser, context], page


#Close all components for opening a web
def close_all(webs):
    #Check input
    if len(webs) != 3:
        raise RuntimeError(f"close_all got {len(webs)} args, expected 4")

    #Close context
    webs[2].close()
    
    #Close browser
    webs[1].close()

    #Close playwright 
    webs[0].stop()




def main():
    str = ""
    chrome = launch_chrome()
    input("Press Enter when you're done")
    while str != "break":
        try:

            # 3) attach & scrape
            webs, page = getWeb(DEBUG_PORT)

        finally:
            # (optional) kill Chrome when done:
            # chrome_proc.terminate()
            pass
        

        
        
        soup = BeautifulSoup(page.content(), "html.parser", from_encoding="utf-8")
        text = soup.get_text(separator="\n", strip=True)
        text = fix_text(text)
        print(text)
        
        

        


if __name__ == "__main__":
    main()

