# Margin

Margin is a personal note-taking app for lectures and study sessions. You write short, rough notes while you listen, and Margin turns them into clear, organized study notes with definitions, formulas, examples, diagrams, key takeaways and flashcards, ready to download as a PDF.
It runs on your own computer and you use it in your web browser.

> **Status:** complete: library, subjects and tags, autosaving notes, search, **Enhance notes**, diagrams (with full-screen zoom), per-section regenerate with undo, **PDF export**, settings, backup/restore, and optional **phone access** over home Wi-Fi.
> New to the code? Read **[docs/how-it-works.md](docs/how-it-works.md)**: it follows a note from the keyboard to the PDF.

---

**Contents:** [1. Installation guide](#1-installation-guide) · [2. Using Margin](#2-using-margin) · [3. Phone access](#3-phone-access-optional-home-wi-fi-only) · [4. Your data](#4-your-data) · [5. Troubleshooting](#5-troubleshooting) · [6. For developers](#6-for-developers)

---

## 1. Installation guide

This guide assumes no technical experience. Installing takes about **10–15 minutes**, most of it waiting for downloads. You only do it once.

**What you need:**
- A computer with **Windows 10/11** or **Linux** (for example Fedora or Ubuntu) and an internet connection
- **Google Chrome** or **Microsoft Edge** (Edge is already part of Windows; on Linux, Chrome or Chromium)
- A **Google account** (for the free Gemini API key that *Enhance notes* uses)
- About **400 MB** of free disk space

### Step A: Get your free Gemini API key (Windows and Linux)

1. Open **https://aistudio.google.com** and sign in with your Google account.
2. Click **Get API key**, then **Create API key**.
3. Copy the key (it starts with `AIza…`) and keep it somewhere safe for Step C.

Treat the key like a password: don't share it or post it anywhere. If it ever leaks, delete it in AI Studio and create a new one.

---

### Install on Windows

**Step B1: Install Python** (skip if you already have Python 3.11 or newer)

1. Go to **https://www.python.org/downloads/** and click the yellow **Download Python** button.
2. Open the downloaded file.
3. On the first screen, **tick the box "Add python.exe to PATH"** at the bottom. This is important.
4. Click **Install Now** and wait until it says *Setup was successful*. Click **Close**.

**Step B2: Download Margin**

1. Open the Margin page on GitHub: **https://github.com/huzexe/margin**
2. Click the green **Code** button, then **Download ZIP**.
3. Open your **Downloads** folder, right-click **margin-main.zip** and choose **Extract All…**, then **Extract**.
4. Move the extracted **margin-main** folder to your **Documents** folder and rename it to **Margin**.
   (Keep it there: Margin runs from this folder, and your notes are stored inside it.)

**Step B3: Run the installer**

1. Open the **Margin** folder in File Explorer.
2. Click the **address bar** at the top (where it shows the folder path), type **`cmd`** and press **Enter**. A black Command Prompt window opens in the Margin folder.
3. Type this and press **Enter**:
   ```
   py start.py --install
   ```
4. Wait until it says **"Margin is in your Start Menu and on your Desktop"** (a few minutes the first time; it downloads what Margin needs).
   If you see *'py' is not recognized*, Python isn't installed correctly: repeat Step B1 and make sure the PATH box is ticked.

**Step C: Add your API key**

1. In the same black window, type this and press **Enter**:
   ```
   notepad .env
   ```
2. Notepad opens. Find the line `GEMINI_API_KEY=` and paste your key right after the `=` (no spaces), for example `GEMINI_API_KEY=AIzaSy...`.
3. Press **Ctrl + S** to save, then close Notepad and the black window.

**Step D: Open Margin**

Double-click **Margin** on your Desktop (or find it in the Start Menu). It opens in its own window after a few seconds. That's it. See [2. Using Margin](#2-using-margin) to get started.

---

### Install on Linux

These steps use the **Terminal** app. Commands are shown for **Fedora**; on **Ubuntu/Debian** use the `apt` lines instead.

**Step B1: Install what Margin needs** (most of it is usually already there)

```bash
# Fedora
sudo dnf install python3 git

# Ubuntu / Debian
sudo apt install python3 python3-venv git
```

You also need **Google Chrome** (from google.com/chrome) or **Chromium**. On Ubuntu, the Google Chrome download works best.
Check the Python version with `python3 --version`: it must be **3.11 or newer**.

**Step B2: Download Margin**

Either open **https://github.com/huzexe/margin**, click **Code → Download ZIP**, and extract it into your home folder as `Margin`, or use the terminal:

```bash
cd ~
git clone https://github.com/huzexe/margin.git Margin
```

**Step B3: Run the installer**

```bash
cd ~/Margin
python3 start.py --install
```

Wait until it says **"Margin is in your app menu"** (a few minutes the first time).

**Step C: Add your API key**

```bash
nano .env
```

Paste your key after `GEMINI_API_KEY=` (no spaces), then press **Ctrl + O**, **Enter** to save and **Ctrl + X** to close.

**Step D: Open Margin**

Press the **Super (Windows) key**, type **Margin** and click its icon. To keep it in the dock: right-click the icon and choose **Pin to Dash** (GNOME) or **Pin to Task Manager** (KDE).

---

### Good to know (both systems)

- **Closing Margin:** close its window. Margin keeps running quietly for about 3 minutes (so reopening is instant), then stops by itself. To stop it immediately, use **Quit Margin** (Windows: Start Menu; Linux: right-click the icon).
- **Your notes** are saved automatically in the `data` folder inside the Margin folder. Make a backup now and then: *Settings → Download backup*.
- **Running from a terminal instead** (handy for testing): Windows: double-click `run.bat`; Linux: `./run.sh`. Then open http://127.0.0.1:8000 in your browser and stop it with **Ctrl + C**.
- Something not working? See [5. Troubleshooting](#5-troubleshooting). Startup errors are written to `data/margin.log`.

### Updating to a newer version

**If you downloaded the ZIP:**
1. In Margin, make a backup: *Settings → Download backup*.
2. Download and extract the new ZIP as in Step B2, into a new folder.
3. Copy **`.env`** and the **`data`** folder from your old Margin folder into the new one (replace if asked).
4. Run the installer in the new folder again (Step B3), then delete the old folder.

**If you used `gh repo clone` / git:** in the Margin folder run `git pull`. New packages install automatically the next time Margin starts.

### Uninstalling

1. **Keep your notes?** First use *Settings → Download backup* and save the file somewhere safe.
2. Open a terminal in the Margin folder (Windows: address bar → `cmd`) and run:
   - Windows: `py start.py --uninstall`
   - Linux: `python3 start.py --uninstall`

   This removes the Start Menu, Desktop or app-menu shortcuts.
3. Delete the Margin folder. **This also deletes your notes** (they live in its `data` folder).

---

## 2. Using Margin

**Library (home page)**
- **New note** (top right) opens an empty note. If a subject is selected in the sidebar, the new note goes into that subject.
- **Subjects** in the left sidebar: click one to see only its notes. Hover over a subject to **rename** (pencil) or **delete** (bin) it.
  Deleting a subject never deletes notes. They move to *No subject*.
- **Tags** appear under *Tags* in the sidebar once a note has one. Click a tag to show only those notes (click again to clear); it combines with the subject filter.
- **Search** looks through titles, topics, note text and tags. Partial words work (`inert` finds *inertia*; `#ex` finds the tag *exam*).
- **Sort** by last edited, created, or title.

**Note page**
- Type a title, choose a subject, add a topic, then write your rough notes.
- To create a subject from a note, open the **Subject** dropdown and choose **+ Add subject…**.
- **Tags:** type in the *Tags* box and press **Enter** (or type a comma). Existing tags are suggested. Remove one with its **×**, or press Backspace in the empty box. Up to 20 tags per note; tags no note uses any more disappear automatically.
- Everything **saves automatically** while you type. The status at the top shows *Saving…* or *Saved*.
  If saving fails (for example, if Margin was stopped), the status shows *Not saved* with a **Retry** link, and it keeps trying.
- An empty new note is never saved, so the library doesn't fill up with blank notes.
- **Delete** (top right) removes the note after you confirm.

**Enhance notes**
- Rough notes are on the left, enhanced notes on the right (on a phone, switch with the *Rough notes / Enhanced* tabs).
- Choose what to include, then press **Enhance notes** (or `Ctrl + Enter`):

  | Option | What it does |
  |---|---|
  | Simplify | Plain words, jargon explained, everyday examples |
  | Diagrams | 1–3 flowcharts, sequence diagrams, mind maps etc. where a picture helps |
  | Flashcards | 5–10 question/answer cards at the end |
  | Applications | A *Practical applications* section |
  | Detail | **Concise** (revision sheet), **Standard**, or **Detailed** (thorough explanations) |

  Every result always includes organized sections, definitions, formulas, examples where useful, and key takeaways.
- It usually takes 10–40 seconds. **Cancel** stops waiting and keeps what you had.
- Small markers in your rough notes help: start a line with `?` for a question you want answered, `def:` for a definition, `!` for something important.
- **Please verify** boxes mark things that may be wrong or unclear in your notes, for example a date or name that doesn't match what is usually taught. They catch many problems but not all: a number that some textbooks state differently (for example how much ATP respiration makes) may be repeated as-is. Always check important facts and numbers against your lecture material.
- The enhanced notes are fully **editable**: click to type, select text for bold/italic/code, use the **+** button for new blocks (heading, list, callout, formula, table, code, flashcards), and the **⋮⋮** button to move, delete or change a block (for example, switch a box between Definition / Example / Key takeaways / Please verify). Click a formula to edit its LaTeX.
- Flashcards: press **Practice** to hide the answers and reveal them one by one.
- **Enlarge a diagram:** hover over it and press **Enlarge** for a full-screen view. Use **+ / −**, **Fit**, **100%**, or Ctrl + mouse wheel to zoom, scroll to move around, and **Esc** to close.
- **Diagrams:** hover over a diagram and press **Edit diagram** to change its code; the picture updates as you type. Labels go in double quotes, e.g. `A["Step one"] --> B["Step two"]`. If a diagram can't be drawn, Margin tries one automatic fix; if that fails too, it shows the diagram's main points as a list with **Try again** and **Edit diagram** buttons, never a broken picture. You can also add a diagram yourself with the **+** button.
  Diagrams can't show everything: circuits, chemical structures, geometry and graphs of functions are explained in text instead.
- **Regenerate one section:** hover over a section heading and press **Regenerate**. Pick a quick request (*Simpler*, *More detail*, *Add an example*, *Shorter*) or type your own, then press **Regenerate**. Only that section is rewritten; the rest stays exactly as it is. (Not available for the Flashcards section.)
- **Undo:** after a section is regenerated, or after *Enhance notes* replaces existing enhanced notes, a message with **Undo** appears at the bottom for 15 seconds. Undo puts back exactly what was there before (edits you made after the change are undone too).
- Enhancing again replaces the enhanced notes. If you edited them, Margin asks first. If nothing changed since last time, it also asks, so you don't use your daily limit by accident.

**Export to PDF**
- On a note, press **Preview & export**. You'll see the actual PDF as a preview.
- Choose what to include: **Table of contents** (with page numbers), **Flashcards** (on their own last page), **Original rough notes** (as an appendix), plus **Text size** and **Margins**. The preview updates after each change (1–3 seconds).
- Press **Download PDF**. The file is saved as e.g. `Binary-Search.pdf` in your Downloads folder. *Open in new tab* shows it in the browser's PDF viewer.
- PDFs are made invisibly by the Chrome, Edge or Chromium already on your computer (nothing extra is downloaded).
- Every PDF is A4 with the title, subject, topic and date at the top and *title · page / total* at the bottom. Diagrams and formulas are sharp at any zoom, and boxes, diagrams, tables rows and flashcards are never split across pages.
- A note without enhanced notes exports its rough notes.
- Limitations: links inside the notes become plain text, and a very tall diagram is scaled down to fit on one page.

**Shortcuts**

| Keys | Action |
|---|---|
| `/` | Jump to search (library) |
| `Enter` in the title | Jump to the notes area |
| `Ctrl + Enter` | Enhance notes |
| `Ctrl + S` | Save now (it also saves on its own) |

**Settings** (top bar → *Settings*)
- **Default options for new notes:** which boxes (Simplify, Diagrams, Flashcards, Applications) and which detail level a new note starts with. Each note still has its own choice.
- **Appearance:** *Match system*, *Light* or *Dark*. The moon/sun button in the top bar switches quickly too.
- **Backup:** *Download backup* saves all notes, subjects and settings in one file (`margin-backup-<date>.json`).
- **Restore:** choose a backup file, then either **Add to my library** (keeps your notes, adds the backup's) or **Replace everything** (asks for confirmation, then makes the library exactly like the backup).

---

## 3. Phone access (optional, home Wi-Fi only)

Use Margin on your phone or tablet while your laptop runs it, for example to type notes in another room. It is **off by default**.

**What you get:** the laptop never asks for a PIN. Every other device must enter your PIN once, then stays unlocked for 30 days. After 5 wrong PINs a device is locked out for 5 minutes. *Settings → Sign out all phones* (on the laptop) locks every phone again.

**Important:** the connection between phone and laptop is **not encrypted** (plain `http`). Only use this on your own home Wi-Fi, never on public or university Wi-Fi.

**Turn it on**

1. Choose a PIN (6 or more digits is best) and add two lines to the `.env` file in the Margin folder
   (open it like in Step C of the installation guide: `notepad .env` on Windows, `nano .env` on Linux):
   ```
   MARGIN_PHONE_ACCESS=on
   MARGIN_PIN=482913
   ```
   (Use your own PIN, not this example.)
2. Restart Margin (*Quit Margin*, then open it again). The terminal now shows the address for your phone, e.g. `http://192.168.1.23:8000`. It's also on the *Settings* page.
3. Allow other devices through the firewall. **Windows:** the first time, Windows asks whether Python may communicate on **private networks**; choose **Allow**. **Fedora:** the firewall blocks other devices by default, so allow Margin's port:
   ```bash
   sudo firewall-cmd --add-port=8000/tcp                 # until the next restart of the laptop
   sudo firewall-cmd --add-port=8000/tcp --permanent     # optional: keep it after restarts
   ```
4. On the phone (same Wi-Fi), open that address and enter the PIN. Tip: add it to the home screen from the browser menu.

**Turn it off:** remove the two lines (or set `MARGIN_PHONE_ACCESS=off`), restart Margin, and close the port again with `sudo firewall-cmd --remove-port=8000/tcp` (add `--permanent` if you added it permanently).

Notes: the laptop must be on and running Margin. If your router gives the laptop a new address, the phone address changes; check the terminal or *Settings*. For use outside home, a private network app such as Tailscale (free for personal use) can connect phone and laptop securely; that is not built into Margin.

---

## 4. Your data

- All notes and subjects are stored in one file: **`data/margin.db`**.
- **Backup (easiest):** *Settings → Download backup*. Keep the file somewhere safe (USB drive, cloud storage). Restore it with *Settings → Restore*. This also moves your notes to another computer.
- **Backup (whole database file):** stop Margin (*Quit Margin*), then copy `data/margin.db` from the Margin folder to a safe place, for example with File Explorer (Windows) or the Files app (Linux).
  To restore it, stop Margin and copy it back to `data/margin.db`.
- The `data/` folder is never uploaded to GitHub (it is listed in `.gitignore`).

### What is sent to Google

- Only when you press **Enhance notes**, that note's **title, subject, topic and rough notes** are sent to Google's Gemini API. **Regenerate** also sends the section being rewritten and the headings of the note's other sections; a diagram fix sends only that diagram's code. Nothing is sent while you type, and other notes are never sent.
- **Free-tier privacy:** on Gemini's free tier, Google may use what you send to improve its products, and it may be read by human reviewers. Don't put personal or sensitive information (passwords, ID numbers, private details about people) in notes you enhance. A paid Gemini plan doesn't use your data this way.
- **Free-tier limits:** Google limits how many requests you can make per minute and per day. If you hit the limit, Margin shows *Service is busy* or *Daily limit reached*. Wait a minute (or until tomorrow) and try again.

---

## 5. Troubleshooting

| Problem | Fix |
|---|---|
| `Port 8000 is already in use` | Margin is probably already running: open http://127.0.0.1:8000. To use another port, add `MARGIN_PORT=8001` to `.env` |
| `./run.sh: Permission denied` (Linux) | Run `chmod +x run.sh` once, or use `python3 start.py` |
| `python3: command not found` (Linux) | `sudo dnf install python3` |
| `'py' is not recognized` (Windows) | Install Python from python.org with **Add python.exe to PATH** ticked, or try `python start.py` |
| Page says *Can't reach Margin* | Margin was stopped (Quit, Ctrl+C, or all windows were closed for a few minutes). Open it again |
| The app icon does nothing (Windows) | Run `py start.py --app` in a terminal to see the message, and check `data\margin.log` |
| Packages seem broken | Delete the `.venv` folder and open Margin again; it reinstalls everything |
| *The service key isn't set up* | Add your key to `.env` (section 1) and restart Margin |
| *The service key was rejected* | The key in `.env` is wrong or was deleted. Create a new one in AI Studio, update `.env`, restart |
| *Service is busy* | Google's free tier is overloaded or you sent many requests quickly. Wait a minute and try again |
| *Daily limit reached* | The free daily quota is used up. Try again tomorrow |
| *Couldn't connect* | Check your internet connection (Enhance needs internet; everything else, including PDF export, works offline) |
| *PDF export needs Google Chrome, Microsoft Edge or Chromium* | Install one of them (free), then try again. A browser in an unusual place can be set with `MARGIN_PDF_BROWSER=/path/to/browser` in `.env` |
| PDF preview stays blank | Your browser may block PDFs inside pages. Use **Open in new tab** or **Download PDF** |
| Phone can't open Margin | Same Wi-Fi as the laptop? Firewall port allowed (section 3, step 3)? Phone access on in `.env`, and Margin restarted? Use the address shown in the terminal |
| *Phone access is on … MARGIN_PIN is missing* | Add `MARGIN_PIN=` with at least 4 characters to `.env`, or turn phone access off |
| Phone keeps asking for the PIN | It was signed out (*Sign out all phones*) or 30 days passed. Enter the PIN again |

---

## 6. For developers

```bash
.venv/bin/pip install -r requirements-dev.txt   # test tools
.venv/bin/pytest                                # run the tests
```

```
app/                 Python backend (FastAPI)
  main.py            app setup, security headers, page routes, PIN unlock
  auth.py            phone access: PIN check, sign-in cookies, lockout
  db.py              SQLite tables, search index, small migrations
  schemas.py         input validation
  routes/            JSON API: notes.py (incl. enhance, PDF), subjects.py, settings.py (settings, backup, restore)
  services/llm.py    the only Gemini-specific code (swap provider here)
  services/prompts.py  instructions for enhancing notes
  services/enhance.py  reply format and conversion into editor blocks
  services/pdf.py    PDF export (Playwright prints /notes/<id>/print; pypdf finds page numbers)
static/              frontend (plain HTML, CSS, JavaScript)
  index.html         library page          js/library.js
  note.html          note page             js/note.js, js/editor.js, js/sections.js
  export.html        export page           js/export.js
  print.html         print layout for PDFs js/print.js, css/print.css
  settings.html      settings page         js/settings.js
  js/blocks/         custom editor blocks: callout, formula, flashcards
  css/tokens.css     colors, fonts, spacing (change the look here)
  fonts/, vendor/    bundled fonts and libraries (see vendor/VERSIONS.md), so the app works offline
design/              style preview from the design phase
docs/how-it-works.md a beginner's guide to the code
tests/               automated tests
data/                your notes database (created on first run)
```

Settings can be changed with environment variables or a `.env` file in the project folder:

| Variable | Default | Meaning |
|---|---|---|
| `MARGIN_PORT` | `8000` | Port the app runs on |
| `MARGIN_DB_PATH` | `data/margin.db` | Where notes are stored |
| `GEMINI_API_KEY` | (none) | Your Gemini API key |
| `GEMINI_MODEL` | `gemini-3.5-flash` | Main model |
| `GEMINI_FALLBACK_MODEL` | `gemini-3.5-flash-lite` | Used automatically when the main model is overloaded |
| `LLM_TIMEOUT_SECONDS` | `120` | Give up on a request after this long |
| `MARGIN_PDF_BROWSER` | (automatic) | Path to the browser used for PDFs, if Chrome/Edge/Chromium isn't found automatically |
| `MARGIN_AUTO_STOP_SECONDS` | `180` | How long Margin (started as an app) waits after its last window closes before stopping |
| `MARGIN_PHONE_ACCESS` | off | `on` lets devices on your Wi-Fi connect (with the PIN) |
| `MARGIN_PIN` | (none) | PIN other devices must enter; required when phone access is on |

The tests never call Gemini (they use a stand-in), so they don't use your quota.

---

Fonts: IBM Plex Sans, IBM Plex Mono and Source Serif 4, all under the SIL Open Font License.
