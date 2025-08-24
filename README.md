# Novel Translator — README

A command-line tool that scrapes one or more chapters from a web-novel open in your browser, sends them to an LLM for high-quality literary translation, and updates per-novel translation notes (glossary, style, character info) based on the returned translations. The project glue and CLI live in `app.py`; browser automation helpers are in `webhandler.py`.

---

## Features / Overview

* Attach to an already-running Chrome/Chromium instance (with DevTools remote debugging) and read the currently open tab(s).
* Collect multiple chapters (you navigate from chapter to chapter in the browser), chunk them to respect model token limits, and translate them in batches.
* Save translation output to `novels/<NovelName>/chapter<start>-<end>.txt` and also keep `oriText.txt` / `transText.txt` for debugging.
* Maintain a `novelSpecific.txt` per-novel (notes / glossary / style instructions) which the tool updates after each translation.
* Automatic API key rotation on rate-limit errors using multiple keys stored in `Info/keys.txt`. If all keys are exhausted the program exits with an error message.

---

## Requirements

Install python packages from `requirements.txt`: `openai`, `ftfy`, `beautifulsoup4`, `playwright`, `tiktoken`, `requests`.

Example install:

```bash
python -m pip install -r requirements.txt
# then install browser binaries for playwright:
playwright install
# if you only need chromium:
playwright install chromium
```

(Installing Playwright browsers is required so Playwright can attach/connect properly.)

---

## Project layout (important files)

```
.
├─ app.py                    # main CLI & translation logic (reads Info/ and novels/)
├─ webhandler.py             # launches Chrome/CDP + Playwright connector
├─ requirements.txt
├─ Info/
│  ├─ connect.config         # config for model, api_key index, context
│  ├─ keys.txt               # newline-separated API keys
│  ├─ generalPrompt.txt      # global translation requirements
│  ├─ template.txt           # template used to initialise novelSpecific.txt
│  └─ ...                    # other support files
└─ novels/                   # created automatically, contains per-novel outputs
```

---

## Configuration

### 1) `Info/connect.config` (required)

`app.py` expects a `connect.config` file under `Info/` with a `[info]` section containing at least:

```ini
[info]
model = <model-name-or-id>
api_key = 0         ; integer index into keys.txt (0-based)
context = 32768     ; model context token size (used to compute safe chunk size)
```

The program uses `context` to compute a safe chunking limit (it currently uses `context/4` to be conservative).

### 2) `Info/keys.txt`

One API key per line. The `api_key` value in `connect.config` selects which key index to start with. The tool rotates keys on `RateLimitError`. Keep this file secret and out of version control.

Example:

```
sk-AAAA...
sk-BBBB...
sk-CCCC...
```

### 3) `Info/generalPrompt.txt`, `Info/template.txt`

* `generalPrompt.txt` contains the global translation requirements that the translator prompt injects before each translation.
* `template.txt` provides a skeleton for `novelSpecific.txt` (the per-novel notes). On first run, `app.py` will create `novelSpecific.txt` from `template.txt` if missing.

---

## How it works (high level)

1. `webhandler.launch_chrome()` spawns Chrome with `--remote-debugging-port` and a persistent user-data dir. The script waits for the DevTools HTTP endpoint to be ready. You must log into the site using the launched Chrome if the novel requires authentication.
2. `app.py` asks you to navigate to the current chapter in that browser and press Enter. It then attaches Playwright to Chrome over the CDP endpoint and reads the page content. The script watches for `framenavigated` events; you navigate to the next chapter in your browser and the script will automatically collect multiple chapters.
3. All chapter texts are concatenated and chunked using `tiktoken` encoding and a conservative token limit to avoid model context overflow. Chunks are sent to the model for translation.
4. After translation, the tool sends a second prompt to analyze the original vs translated text and update `novelSpecific.txt` (glossary, style notes, character info) — the updated note replaces the file on disk.

---

## Usage

```bash
python app.py <NovelName> <CurrentChapterNumber> <LanguageCodeOrName>
```

Example:

```bash
python app.py "MyNovel" 123 "English"
```

Notes:

* `NovelName` becomes a directory under `novels/`. A `novelSpecific.txt` will be created on first run using `Info/template.txt`.
* The script expects you to interactively navigate in the launched Chrome: log in if necessary, open the first chapter, then press Enter in the terminal so the script starts collecting pages. Navigate to the next chapter tab/page in the browser when you want the script to capture the next chapter.

---

## Important implementation details & tips

* **Chrome path & profile**: `webhandler.py` contains a `CHROME_PATH` constant that determines which Chrome binary to launch. Adjust it if your Chrome is in a non-standard location. The script creates a persistent profile directory (under your OS's conventional appdata or XDG path by default).
* **DevTools port**: default is `9222`. If that port is already used, change `DEBUG_PORT` in `webhandler.py` and ensure the port matches in both files.
* **Playwright CDP attach**: Playwright attaches to a running Chrome via CDP. Don’t run another Playwright instance that manages its own browser at the same time (it may conflict).
* **Token encoding**: `tiktoken.get_encoding("cl100k_base")` is used to measure tokens and chunk. If you switch models, update `connect.config` and adjust strategy if needed.
* **API client**: The code instantiates `OpenAI` with a provider base URL and uses chat completions. Be aware of how your API provider expects requests and adjust accordingly.

---

## Troubleshooting

* **DevTools endpoint not reachable**: Confirm Chrome launched with `--remote-debugging-port=9222`. You can visit `http://127.0.0.1:9222/json/version` in a browser to verify the DevTools endpoint.
* **Playwright fails to connect**: Ensure the port in `webhandler.py` matches the port Chrome was launched with, no firewall blocks local HTTP, and you launched Chrome with the same user-data directory.
* **Rate limit / API errors**: The app will try to rotate keys in `Info/keys.txt` on a `RateLimitError`. If all keys are exhausted, the script exits with a message. Add more valid keys or wait.
* **Token limit / chunking issues**: If translations are failing because prompts are too long, increase the conservative limit logic or reduce `connect.config`'s `context` value. The code currently uses `limit = context // 4`.

---

## Security & Best Practices

* **Secrets**: `Info/keys.txt` contains API keys—do **not** commit it. Add `Info/keys.txt` to `.gitignore`.
* **Least privilege**: If possible, use API keys with limited permissions and rotate them periodically.
* **Local profile**: The script uses a persistent Chrome profile directory. If you want a fresh temporary profile, adjust `webhandler.make_profile_dir()` or the `--user-data-dir` option in `webhandler.launch_chrome()`.

---

## Development notes

* The translation/analysis prompts and I/O format are defined inside `app.py`. If you want to switch the LLM, change `connect.config` and update prompt/response handling as needed.
* Dependencies are listed in `requirements.txt`. Keep them up-to-date and test with a virtual environment.

---

## Example minimal `.gitignore`

```
Info/keys.txt
Info/connect.config
novels/
*.pyc
__pycache__/
```

---

## Example `connect.config` (copy into `Info/connect.config`)

```ini
[info]
model = gpt-4o-mini  ; replace with your model id
api_key = 0
context = 32768
```

---

## Example run (step-by-step)

1. Install deps:

```bash
python -m pip install -r requirements.txt
playwright install
```

2. Create `Info/` and populate `connect.config`, `keys.txt`, and other prompt/template files.
3. Launch the tool:

```bash
python app.py "MyNovel" 100 "English"
```

4. The script will launch Chrome. Log in and open the first chapter in that Chrome window. Return to the terminal and press Enter. Then navigate to the next chapters in your Chrome window; the script will detect the navigation and collect pages automatically.

---

## Known limitations

* The tool assumes manual navigation between chapters in the launched browser (it is interactive). Fully automated crawling is not implemented.
* Prompt/response format is strict. If the model outputs unexpected separators, you may need to tune prompts or add validation.

---

## Where to look in code

* Main flow, chunking, translation prompts, and file writes: `app.py`.
* Chrome launching, DevTools readiness check, Playwright CDP attach: `webhandler.py`.
* Dependencies list: `requirements.txt`.

---

## Contributing

* Feel free to create PRs for:

  * automated crawling / next-link detection,
  * better token-chunking strategies,
  * adding unit tests for prompt validation,
  * optional non-interactive mode (supply a list of URLs instead of manually navigating).


