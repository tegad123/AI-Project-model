# AI MODEL POST GENERATOR

Analyzes a reference scene photo using Claude AI, then generates a 4K 9:16 image
of the active model placed into that exact scene using WaveSpeed Nano Banana Pro.

---

## Files

| File | Description |
|------|-------------|
| `AI_Model_Post_Generator.py` | Main app — safe to share |
| `config.py` | Your private keys and settings — share only with trusted collaborators |
| `README.md` | This file |

---

## Setup

### 1 — Install Python
Download from python.org if you don't have it.

### 2 — Install required libraries
Open Command Prompt and run:
```
pip install selenium webdriver-manager pyperclip anthropic
```

### 3 — Edit config.py
Open `config.py` and update:
- `AMBER_DEFAULT_PATH` — full path to your model reference image on your PC
- `WAVESPEED_API_KEY` — your WaveSpeed API key (wavespeed.ai → API Keys)
- `ANTHROPIC_API_KEY` — your Anthropic API key (console.anthropic.com) — optional but recommended

### 4 — Run the app
Double-click `AI_Model_Post_Generator.py` or run:
```
python AI_Model_Post_Generator.py
```

---

## Analysis Modes

The app has two ways to analyze scene photos:

**Anthropic API (recommended)**
- Costs ~$0.02 per scene analysis
- No Chrome setup needed
- Just add your `ANTHROPIC_API_KEY` to config.py

**Claude.ai Browser (free)**
- Uses your logged-in Claude.ai session in Chrome
- Requires Chrome launched with remote debugging enabled
- See Chrome Setup section below

---

## Chrome Setup (browser mode only)

If using browser mode, Chrome must be launched with remote debugging enabled.

Create a batch file on your Desktop called `Chrome for AI.bat` with this content:
```
@echo off
taskkill /f /im chrome.exe >nul 2>&1
timeout /t 2 >nul
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --profile-directory=Default
```

Always use this to open Chrome before running the app in browser mode.

---

## How to Use

1. Open the app
2. Select analysis mode (API or Browser)
3. Click BROWSE and select a scene reference photo
4. Click GENERATE POST
5. The app will:
   - Analyze the scene and save a JSON file next to your photo
   - Send the JSON + model image to WaveSpeed
   - Download and save the generated 4K image next to your scene photo

---

## Cost Per Run

| Step | Cost |
|------|------|
| Scene analysis (API mode) | ~$0.02 |
| Scene analysis (browser mode) | Free |
| WaveSpeed 4K generation | $0.204 |
| **Total (API mode)** | **~$0.224** |
| **Total (browser mode)** | **$0.204** |

Top up WaveSpeed credits at: wavespeed.ai/pricing

---

## Output Files

For each run, two files are saved next to your scene photo:
- `[scene_name]_scene.json` — full scene analysis
- `[scene_name]_generated.jpg` — final 4K generated image
