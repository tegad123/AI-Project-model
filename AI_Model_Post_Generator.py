import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import base64
import json
import os
import threading
import urllib.request
import time
import webbrowser
from pathlib import Path

# ── Import config ────────────────────────────────────────────────────────────
try:
    from config import (
        AMBER_DEFAULT_PATH, WAVESPEED_API_KEY, ANTHROPIC_API_KEY,
        WAVESPEED_MODEL, ASPECT_RATIO, RESOLUTION, COST_PER_IMAGE,
        MODEL_NAME, MODEL_DESCRIPTION, CHROME_DEBUG_PORT
    )
except ImportError:
    messagebox.showerror(
        "Missing config.py",
        "config.py not found!\n\nMake sure config.py is in the same folder as this file."
    )
    raise SystemExit

# ── Prompts ──────────────────────────────────────────────────────────────────
WAVESPEED_PROMPT_TEMPLATE = (
    "Extract scene parameters from the uploaded reference image JSON and generate a "
    "photorealistic portrait of the input model inserted into the exact same "
    "environment/setting. Match lighting type (natural/artificial), direction, intensity, "
    "color temperature, and shadow profile perfectly. Replicate background elements "
    "including architecture, furniture, textures, colors - every detail except the original "
    "subject. Position {model_name} in identical pose with facial expression matching mood "
    "of original. Apply style filters for high-fashion editorial quality with tack-sharp "
    "focus on face/upper body fading into soft background depth-of-field. Output at 9:16 "
    "vertical aspect ratio optimized for social media display. "
    "Model description: {model_description} "
    "Here is the JSON: {scene_json}"
)

CLAUDE_PROMPT = (
    "Analyze this image and return ONLY a valid JSON object with no markdown, "
    "no explanation, just raw JSON using exactly this structure:\n\n"
    "{\"metadata\":{\"confidence_score\":\"...\",\"image_type\":\"...\",\"primary_purpose\":\"...\"},"
    "\"composition\":{\"rule_applied\":\"...\",\"aspect_ratio\":\"...\",\"layout\":\"...\","
    "\"focal_points\":[],\"visual_hierarchy\":\"...\",\"balance\":\"...\"},"
    "\"color_profile\":{\"dominant_colors\":[{\"color\":\"...\",\"hex\":\"...\","
    "\"percentage\":\"...\",\"role\":\"...\"}],\"color_palette\":\"...\","
    "\"temperature\":\"...\",\"saturation\":\"...\",\"contrast\":\"...\"},"
    "\"lighting\":{\"type\":\"...\",\"source_count\":\"...\",\"direction\":\"...\","
    "\"directionality\":\"...\",\"quality\":\"...\",\"intensity\":\"...\","
    "\"contrast_ratio\":\"...\",\"mood\":\"...\","
    "\"shadows\":{\"type\":\"...\",\"density\":\"...\",\"placement\":\"...\",\"length\":\"...\"},"
    "\"highlights\":{\"treatment\":\"...\",\"placement\":\"...\"},"
    "\"ambient_fill\":\"...\",\"light_temperature\":\"...\"},"
    "\"technical_specs\":{\"medium\":\"...\",\"style\":\"...\",\"texture\":\"...\","
    "\"sharpness\":\"...\",\"grain\":\"...\",\"depth_of_field\":\"...\",\"perspective\":\"...\"},"
    "\"artistic_elements\":{\"genre\":\"...\",\"influences\":[],\"mood\":\"...\","
    "\"atmosphere\":\"...\",\"visual_style\":\"...\"},"
    "\"subject_analysis\":{\"primary_subject\":\"...\",\"positioning\":\"...\","
    "\"scale\":\"...\",\"interaction\":\"...\","
    "\"facial_expression\":{\"mouth\":\"...\",\"smile_intensity\":\"...\",\"eyes\":\"...\","
    "\"eyebrows\":\"...\",\"overall_emotion\":\"...\",\"authenticity\":\"...\"},"
    "\"hair\":{\"length\":\"...\",\"cut\":\"...\",\"texture\":\"...\","
    "\"texture_quality\":\"...\",\"natural_imperfections\":\"...\",\"styling\":\"...\","
    "\"styling_detail\":\"...\",\"part\":\"...\",\"volume\":\"...\",\"color_detail\":\"...\"},"
    "\"makeup\":{\"eyes\":\"...\",\"brows\":\"...\",\"lips\":\"...\","
    "\"foundation\":\"...\",\"overall_style\":\"...\"},"
    "\"accessories\":{},"
    "\"clothing\":{\"garment\":\"...\",\"fabric\":\"...\",\"neckline\":\"...\","
    "\"sleeve\":\"...\",\"fit\":\"...\",\"details\":\"...\"},"
    "\"body_positioning\":{\"posture\":\"...\",\"angle\":\"...\","
    "\"weight_distribution\":\"...\",\"shoulders\":\"...\"},"
    "\"hands_and_gestures\":{\"right_hand\":\"...\",\"left_hand\":\"...\","
    "\"hand_tension\":\"...\",\"naturalness\":\"...\"}},"
    "\"background\":{\"setting_type\":\"...\",\"spatial_depth\":\"...\","
    "\"elements_detailed\":[{\"item\":\"...\",\"position\":\"...\",\"distance\":\"...\","
    "\"size\":\"...\",\"condition\":\"...\",\"specific_features\":\"...\"}],"
    "\"wall_surface\":{\"material\":\"...\",\"surface_treatment\":\"...\",\"texture\":\"...\","
    "\"finish\":\"...\",\"color\":\"...\",\"color_variation\":\"...\","
    "\"features\":\"...\",\"wear_indicators\":\"...\"},"
    "\"floor_surface\":{\"material\":\"...\",\"color\":\"...\",\"pattern\":\"...\"},"
    "\"objects_catalog\":\"...\",\"background_treatment\":\"...\"},"
    "\"generation_parameters\":{\"prompts\":[\"...\",\"...\"],\"keywords\":[],"
    "\"technical_settings\":\"...\",\"post_processing\":\"...\"}}"
)

CLAUDE_SYSTEM = (
    "You are an expert image analyst. Analyze the provided photo and return ONLY "
    "a valid JSON object with no markdown, no explanation, just raw JSON."
)


# ── Helpers ───────────────────────────────────────────────────────────────────
def to_b64(path):
    with open(path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode()

def get_media_type(path):
    return {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif"
    }.get(Path(path).suffix.lower(), "image/jpeg")


# ── Analysis — two methods ────────────────────────────────────────────────────
def analyze_via_api(image_path, log_fn):
    """Use Anthropic API directly — requires ANTHROPIC_API_KEY in config."""
    if not ANTHROPIC_API_KEY:
        raise ValueError(
            "No Anthropic API key in config.py.\n"
            "Add your key to ANTHROPIC_API_KEY in config.py.\n"
            "Get one free at console.anthropic.com"
        )
    log_fn("-> Sending to Claude API...")
    body = json.dumps({
        "model": "claude-opus-4-5",
        "max_tokens": 4096,
        "system": CLAUDE_SYSTEM,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image", "source": {
                    "type": "base64",
                    "media_type": get_media_type(image_path),
                    "data": to_b64(image_path)
                }},
                {"type": "text", "text": CLAUDE_PROMPT}
            ]
        }]
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01"
        },
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read())

    raw = data["content"][0]["text"].strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(raw)


def analyze_via_browser(image_path, log_fn):
    """Use Claude.ai browser bot — free but requires Chrome for AI shortcut."""
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.action_chains import ActionChains
    from webdriver_manager.chrome import ChromeDriverManager
    import pyperclip

    log_fn("-> Connecting to Chrome...")
    opts = Options()
    opts.add_experimental_option("debuggerAddress", "127.0.0.1:" + str(CHROME_DEBUG_PORT))
    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    except Exception as ex:
        raise ValueError(
            "Cannot connect to Chrome.\n\n"
            "Steps:\n"
            "1. Close all Chrome windows\n"
            "2. Open Chrome using the 'Chrome for AI' batch file\n"
            "3. Go to claude.ai and log in\n"
            "4. Try again\n\n"
            "Or add your Anthropic API key to config.py to skip Chrome entirely.\n\n"
            "Detail: " + str(ex)
        )

    log_fn("Connected to Chrome")

    try:
        driver.get("https://claude.ai/new")
        log_fn("-> Waiting for Claude.ai to load...")
        time.sleep(7)

        if "challenge" in driver.current_url or "verify" in driver.current_url.lower():
            raise ValueError(
                "Cloudflare bot check detected.\n\n"
                "Go to Chrome, complete the verification, then try again.\n"
                "Or add your Anthropic API key to config.py to skip Chrome entirely."
            )

        abs_path = os.path.abspath(image_path)
        log_fn("-> Attaching image...")
        uploaded = False

        try:
            inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
            if inputs:
                driver.execute_script("arguments[0].style.display='block';", inputs[0])
                inputs[0].send_keys(abs_path)
                time.sleep(3)
                uploaded = True
                log_fn("Image attached")
        except Exception:
            pass

        if not uploaded:
            try:
                btns = driver.find_elements(By.CSS_SELECTOR,
                    "button[aria-label*='ttach'], button[aria-label*='ile']")
                if btns:
                    btns[0].click()
                    time.sleep(1)
                    inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
                    if inputs:
                        inputs[0].send_keys(abs_path)
                        time.sleep(3)
                        uploaded = True
            except Exception:
                pass

        if not uploaded:
            log_fn("Warning: Could not auto-attach image")

        log_fn("-> Finding input box...")
        time.sleep(2)
        text_el = None
        for sel in ["div[contenteditable='true']", "div.ProseMirror",
                    "div[role='textbox']", "textarea"]:
            try:
                els = driver.find_elements(By.CSS_SELECTOR, sel)
                for el in reversed(els):
                    if el.is_displayed() and el.is_enabled():
                        text_el = el
                        break
                if text_el:
                    break
            except Exception:
                pass

        if not text_el:
            raise ValueError("Could not find Claude input. Is claude.ai loaded?")

        text_el.click()
        time.sleep(0.5)
        pyperclip.copy(CLAUDE_PROMPT)
        ActionChains(driver).key_down(Keys.CONTROL).send_keys('v').key_up(Keys.CONTROL).perform()
        time.sleep(1.5)

        log_fn("-> Sending to Claude...")
        sent = False
        try:
            for btn in reversed(driver.find_elements(By.CSS_SELECTOR,
                    "button[aria-label*='Send'], button[data-testid*='send']")):
                if btn.is_displayed() and btn.is_enabled():
                    btn.click()
                    sent = True
                    break
        except Exception:
            pass
        if not sent:
            ActionChains(driver).send_keys(Keys.RETURN).perform()

        log_fn("-> Claude analyzing... (up to 2 min)")
        time.sleep(10)

        json_text = None
        for i in range(45):
            time.sleep(3)
            try:
                for msel in ["[data-testid='assistant-message']",
                             ".font-claude-message", "div.prose"]:
                    for msg in reversed(driver.find_elements(By.CSS_SELECTOR, msel)):
                        try:
                            txt = msg.text.strip()
                            if txt.startswith("{") and "generation_parameters" in txt:
                                json_text = txt
                                break
                            for c in msg.find_elements(By.CSS_SELECTOR, "code, pre"):
                                t = c.text.strip()
                                if t.startswith("{") and "generation_parameters" in t:
                                    json_text = t
                                    break
                        except Exception:
                            pass
                        if json_text:
                            break
                    if json_text:
                        break
                if json_text:
                    break
            except Exception:
                pass
            if i % 4 == 0 and i > 0:
                log_fn("  Waiting... (" + str(i * 3) + "s)")

        if not json_text:
            try:
                for msel in ["[data-testid='assistant-message']", "div.prose"]:
                    msgs = driver.find_elements(By.CSS_SELECTOR, msel)
                    if msgs:
                        json_text = msgs[-1].text.strip()
                        break
            except Exception:
                pass

        if not json_text:
            raise ValueError("No JSON found. Try again or use API mode.")

        if "```" in json_text:
            for part in json_text.split("```"):
                p = part.strip().lstrip("json").strip()
                if p.startswith("{") and p.endswith("}"):
                    json_text = p
                    break

        parsed = json.loads(json_text)
        log_fn("Scene analysis complete!")
        return parsed

    except Exception:
        raise


# ── WaveSpeed ─────────────────────────────────────────────────────────────────
def get_balance():
    req = urllib.request.Request(
        "https://api.wavespeed.ai/api/v3/balance",
        headers={"Authorization": "Bearer " + WAVESPEED_API_KEY},
        method="GET"
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read())
    bal = (data.get("data", {}).get("balance")
           or data.get("balance")
           or data.get("data", {}).get("available_balance"))
    return float(bal) if bal else None

def call_wavespeed(scene_path, model_path, prompt, log_fn):
    body = json.dumps({
        "images": [
            {"type": "base64", "media_type": get_media_type(model_path), "data": to_b64(model_path)},
            {"type": "base64", "media_type": get_media_type(scene_path), "data": to_b64(scene_path)}
        ],
        "prompt": prompt,
        "aspect_ratio": ASPECT_RATIO,
        "resolution": RESOLUTION,
        "enable_base64_output": False,
        "enable_sync_mode": False
    }).encode()

    req = urllib.request.Request(
        "https://api.wavespeed.ai/api/v3/" + WAVESPEED_MODEL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + WAVESPEED_API_KEY
        },
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        resp = json.loads(r.read())

    pred_id = resp.get("data", {}).get("id") or resp.get("id")
    if not pred_id:
        raise ValueError("No prediction ID: " + str(resp))

    poll_url = "https://api.wavespeed.ai/api/v3/predictions/" + pred_id + "/result"
    for i in range(120):
        time.sleep(3)
        pr = urllib.request.Request(
            poll_url,
            headers={"Authorization": "Bearer " + WAVESPEED_API_KEY},
            method="GET"
        )
        with urllib.request.urlopen(pr, timeout=30) as r:
            poll = json.loads(r.read())
        status = poll.get("data", {}).get("status") or poll.get("status", "")
        if status == "completed":
            outputs = poll.get("data", {}).get("outputs") or poll.get("outputs", [])
            if outputs:
                return outputs[0]
        elif status in ("failed", "error"):
            raise ValueError("WaveSpeed failed: " + str(poll))
        if i % 5 == 0 and i > 0:
            log_fn("  Generating... (" + str(i * 3) + "s)")
    raise TimeoutError("WaveSpeed timed out.")

def download_image(url, path):
    urllib.request.urlretrieve(url, path)


# ── Main App ──────────────────────────────────────────────────────────────────
class App:
    def __init__(self, root):
        self.root = root
        self.root.title("AI MODEL POST GENERATOR")
        self.root.geometry("660x720")
        self.root.resizable(False, False)
        self.root.configure(bg="#0a0a0a")
        self.scene_file = None
        self.use_api = tk.BooleanVar(value=bool(ANTHROPIC_API_KEY))
        self._build_ui()
        threading.Thread(target=self._refresh_balance, daemon=True).start()

    def _build_ui(self):
        BG   = "#0a0a0a"
        CARD = "#141414"
        GOLD = "#c9a84c"
        DIM  = "#888"
        TEXT = "#f0ece0"

        # Header
        hdr = tk.Frame(self.root, bg=BG)
        hdr.pack(fill="x", padx=30, pady=(22, 0))
        tk.Label(hdr, text="AI MODEL POST GENERATOR",
                 font=("Georgia", 18, "bold"), fg=GOLD, bg=BG).pack(anchor="w")
        tk.Label(hdr, text="Scene Analysis  ->  WaveSpeed 4K  ->  9:16",
                 font=("Georgia", 9), fg=DIM, bg=BG).pack(anchor="w")
        tk.Frame(self.root, bg=GOLD, height=1).pack(fill="x", padx=30, pady=(10, 14))

        # Balance
        acct = tk.Frame(self.root, bg=CARD, padx=16, pady=12)
        acct.pack(fill="x", padx=30, pady=(0, 10))
        top = tk.Frame(acct, bg=CARD)
        top.pack(fill="x")
        tk.Label(top, text="WAVESPEED ACCOUNT", font=("Courier", 9, "bold"),
                 fg=DIM, bg=CARD).pack(side="left")
        tk.Button(top, text="Refresh", font=("Courier", 8), bg="#222", fg=DIM,
                  relief="flat", cursor="hand2", padx=6,
                  command=self._click_refresh).pack(side="right")
        bal_row = tk.Frame(acct, bg=CARD)
        bal_row.pack(fill="x", pady=(8, 0))
        tk.Label(bal_row, text="Credit Balance:", font=("Courier", 10),
                 fg=DIM, bg=CARD).pack(side="left")
        self.balance_label = tk.Label(bal_row, text="Loading...",
                                      font=("Courier", 14, "bold"), fg=GOLD, bg=CARD)
        self.balance_label.pack(side="left", padx=(8, 0))
        tk.Button(bal_row, text="+ Add Credits", font=("Courier", 9, "bold"),
                  bg=GOLD, fg="#000", relief="flat", cursor="hand2", padx=10,
                  command=lambda: webbrowser.open("https://wavespeed.ai/pricing")).pack(side="right")
        tk.Label(acct, text="4K  9:16  Nano Banana Pro  15% OFF until Apr 15",
                 font=("Courier", 8), fg=DIM, bg=CARD, anchor="w").pack(fill="x", pady=(6, 0))

        # Model
        mc = tk.Frame(self.root, bg=CARD, padx=16, pady=12)
        mc.pack(fill="x", padx=30, pady=(0, 10))
        tr = tk.Frame(mc, bg=CARD)
        tr.pack(fill="x")
        tk.Label(tr, text="ACTIVE MODEL", font=("Courier", 9, "bold"), fg=DIM, bg=CARD).pack(side="left")
        self.model_status = tk.Label(tr, text="", font=("Courier", 9), fg=GOLD, bg=CARD)
        self.model_status.pack(side="right")
        tk.Label(mc, text=MODEL_NAME + "  .  Pre-loaded",
                 font=("Courier", 11, "bold"), fg=TEXT, bg=CARD, anchor="w").pack(fill="x", pady=(4, 0))
        tk.Label(mc, text=AMBER_DEFAULT_PATH, font=("Courier", 8),
                 fg=DIM, bg=CARD, anchor="w").pack(fill="x")
        self._check_model()

        # Analysis mode toggle
        mode_card = tk.Frame(self.root, bg=CARD, padx=16, pady=10)
        mode_card.pack(fill="x", padx=30, pady=(0, 10))
        tk.Label(mode_card, text="ANALYSIS MODE", font=("Courier", 9, "bold"),
                 fg=DIM, bg=CARD).pack(anchor="w")
        mode_row = tk.Frame(mode_card, bg=CARD)
        mode_row.pack(fill="x", pady=(6, 0))
        tk.Radiobutton(mode_row, text="Anthropic API  (paid ~$0.02, no Chrome needed)",
                       variable=self.use_api, value=True,
                       font=("Courier", 9), fg=TEXT, bg=CARD,
                       selectcolor="#222", activebackground=CARD,
                       command=self._update_mode).pack(anchor="w")
        tk.Radiobutton(mode_row, text="Claude.ai Browser  (free, requires Chrome for AI)",
                       variable=self.use_api, value=False,
                       font=("Courier", 9), fg=TEXT, bg=CARD,
                       selectcolor="#222", activebackground=CARD,
                       command=self._update_mode).pack(anchor="w")
        self.mode_hint = tk.Label(mode_card, text="", font=("Courier", 8),
                                  fg=DIM, bg=CARD, anchor="w")
        self.mode_hint.pack(fill="x", pady=(4, 0))
        self._update_mode()

        # Scene picker
        sc = tk.Frame(self.root, bg=CARD, padx=16, pady=12)
        sc.pack(fill="x", padx=30, pady=(0, 10))
        tk.Label(sc, text="SCENE REFERENCE PHOTO", font=("Courier", 9, "bold"),
                 fg=DIM, bg=CARD).pack(anchor="w")
        sr = tk.Frame(sc, bg=CARD)
        sr.pack(fill="x", pady=(6, 0))
        self.scene_label = tk.Label(sr, text="No scene selected", font=("Courier", 10),
                                    fg=DIM, bg="#111", anchor="w", padx=10)
        self.scene_label.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 8))
        tk.Button(sr, text="BROWSE", font=("Courier", 9, "bold"), bg="#2a2a2a", fg=TEXT,
                  relief="flat", cursor="hand2", command=self._browse, padx=12).pack(side="right")

        # Generate button
        self.gen_btn = tk.Button(self.root,
                                 text="GENERATE POST  --  $0.204",
                                 font=("Georgia", 14, "bold"),
                                 bg=GOLD, fg="#000", relief="flat",
                                 cursor="hand2", pady=16,
                                 command=self._start)
        self.gen_btn.pack(fill="x", padx=30, pady=(0, 10))

        # Progress
        self.progress = ttk.Progressbar(self.root, mode="indeterminate")
        self.progress.pack(fill="x", padx=30)
        s = ttk.Style()
        s.theme_use("default")
        s.configure("TProgressbar", background=GOLD, troughcolor="#1a1a1a")

        # Log
        lc = tk.Frame(self.root, bg=CARD, padx=16, pady=12)
        lc.pack(fill="both", expand=True, padx=30, pady=(10, 20))
        tk.Label(lc, text="LOG", font=("Courier", 9, "bold"), fg=DIM, bg=CARD).pack(anchor="w")
        self.log = tk.Text(lc, height=6, bg="#0f0f0f", fg=TEXT, font=("Courier", 10),
                           relief="flat", bd=0, state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True, pady=(6, 0))
        self._log("Ready. Select a scene photo and click Generate.")

    def _update_mode(self):
        if self.use_api.get():
            if ANTHROPIC_API_KEY:
                self.mode_hint.config(text="API key found in config.py  Ready to go", fg="#4caf50")
            else:
                self.mode_hint.config(
                    text="No API key in config.py  Add ANTHROPIC_API_KEY to use this mode",
                    fg="#c94c4c")
        else:
            self.mode_hint.config(
                text="Make sure Chrome for AI is open and claude.ai is loaded",
                fg="#c9a84c")

    def _check_model(self):
        if os.path.exists(AMBER_DEFAULT_PATH):
            self.model_status.config(text="Ready", fg="#4caf50")
        else:
            self.model_status.config(text="Not found", fg="#c94c4c")
            self._log("Model image not found at: " + AMBER_DEFAULT_PATH)

    def _log(self, msg):
        self.log.config(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    def _refresh_balance(self):
        try:
            bal = get_balance()
            if bal is not None:
                runs = int(bal / COST_PER_IMAGE)
                txt = "$" + str(round(bal, 2)) + "  (~" + str(runs) + " images left)"
                color = "#4caf50" if bal > 1 else "#c94c4c"
            else:
                txt, color = "Could not load", "#888"
        except Exception:
            txt, color = "Error loading balance", "#c94c4c"
        self.root.after(0, lambda: self.balance_label.config(text=txt, fg=color))

    def _click_refresh(self):
        self.balance_label.config(text="Loading...", fg="#888")
        threading.Thread(target=self._refresh_balance, daemon=True).start()

    def _browse(self):
        path = filedialog.askopenfilename(title="Select Scene Photo",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.webp"), ("All", "*.*")])
        if path:
            self.scene_file = path
            self.scene_label.config(text=os.path.basename(path), fg="#f0ece0")
            self._log("Scene: " + os.path.basename(path))

    def _set_busy(self, busy):
        self.gen_btn.config(state="disabled" if busy else "normal")
        self.progress.start(10) if busy else self.progress.stop()

    def _start(self):
        if not self.scene_file:
            messagebox.showwarning("No Scene", "Please select a scene photo first.")
            return
        if not os.path.exists(AMBER_DEFAULT_PATH):
            messagebox.showerror("Model Not Found",
                "Model image not found at:\n" + AMBER_DEFAULT_PATH +
                "\n\nUpdate AMBER_DEFAULT_PATH in config.py")
            return
        self._set_busy(True)
        self.gen_btn.config(text="Working...")
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        try:
            self._log("Starting pipeline...")

            # Step 1 - Analyze
            if self.use_api.get():
                self._log("-> Analyzing via Anthropic API...")
                result = analyze_via_api(self.scene_file, self._log)
            else:
                self._log("-> Analyzing via Claude.ai browser...")
                result = analyze_via_browser(self.scene_file, self._log)

            base = os.path.splitext(self.scene_file)[0]
            with open(base + "_scene.json", "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2)
            self._log("Scene analyzed and JSON saved")

            # Step 2 - Generate
            prompt = WAVESPEED_PROMPT_TEMPLATE.format(
                model_name=MODEL_NAME,
                model_description=MODEL_DESCRIPTION,
                scene_json=json.dumps(result)
            )
            self._log("-> Generating 4K image via WaveSpeed...")
            url = call_wavespeed(self.scene_file, AMBER_DEFAULT_PATH, prompt, self._log)

            out = base + "_generated.jpg"
            download_image(url, out)
            self._log("Done! Saved: " + os.path.basename(out))

            self.root.after(0, self._refresh_balance)
            self.root.after(0, lambda: messagebox.showinfo(
                "Done!", "4K image saved!\n\n" + out))

        except Exception as ex:
            err = str(ex)
            self._log("Error: " + err)
            self.root.after(0, lambda msg=err: messagebox.showerror("Error", msg))
        finally:
            self.root.after(0, lambda: self._set_busy(False))
            self.root.after(0, lambda: self.gen_btn.config(text="GENERATE POST  --  $0.204"))


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
