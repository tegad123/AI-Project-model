import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import base64
import json
import os
import threading
import urllib.request
import urllib.error
import time
import webbrowser
import io
from pathlib import Path
from PIL import Image

# ── Import config ────────────────────────────────────────────────────────────
try:
    from config import (
        AMBER_DEFAULT_PATH, WAVESPEED_API_KEY, ANTHROPIC_API_KEY,
        WAVESPEED_MODEL, ASPECT_RATIO, RESOLUTION, COST_PER_IMAGE,
        MODEL_NAME, MODEL_DESCRIPTION
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
    "Analyze this image and return ONLY raw valid JSON. No markdown. No explanation. No code fences.\n\n"
    "Use precisely this structure:\n\n"
    '{"pipeline_meta":{"task":"face_replacement_scene_reconstruction",'
    '"preserve_elements":["background","lighting","body_pose","clothing","accessories","camera_angle","depth_of_field","color_grading"],'
    '"replace_elements":["face_identity"],'
    '"model_reference_slot":"INSERT_MODEL_REFERENCE_IMAGE_PATH_HERE",'
    '"confidence_score":"...","image_type":"...","primary_purpose":"..."},'

    '"camera_profile":{"shot_type":"...","focal_length_estimate":"...",'
    '"camera_distance_to_subject":"...","angle_relative_to_subject":"...",'
    '"lens_distortion":"...","sensor_type_estimate":"...",'
    '"selfie_or_photographer":"...","tilt_roll_degrees":"..."},'

    '"composition":{"rule_applied":"...","aspect_ratio":"...","layout":"...",'
    '"focal_points":[],"visual_hierarchy":"...","balance":"...",'
    '"subject_frame_percentage":"...","head_position_in_frame":"...","crop_tight_loose":"..."},'

    '"color_profile":{"dominant_colors":[{"color":"...","hex":"...",'
    '"percentage":"...","role":"..."}],"color_palette":"...",'
    '"temperature":"...","saturation":"...","contrast":"...",'
    '"lut_style":"...","vignette":"...","color_grading_notes":"..."},'

    '"lighting":{"type":"...","source_count":"...","direction":"...",'
    '"directionality":"...","quality":"...","intensity":"...",'
    '"contrast_ratio":"...","mood":"...",'
    '"shadows":{"type":"...","density":"...","placement":"...","length":"..."},'
    '"highlights":{"treatment":"...","placement":"..."},'
    '"ambient_fill":"...","light_temperature":"...",'
    '"skin_lighting_interaction":"...","catch_lights_in_eyes":"...","face_lighting_ratio":"..."},'

    '"technical_specs":{"medium":"...","style":"...","texture":"...",'
    '"sharpness":"...","grain":"...","depth_of_field":"...",'
    '"bokeh_quality":"...","perspective":"...","motion_blur":"...","noise_level":"..."},'

    '"artistic_elements":{"genre":"...","influences":[],"mood":"...",'
    '"atmosphere":"...","visual_style":"...","editing_style":"..."},'

    '"face_transplant_guide":{"head_size_relative_to_frame":"...",'
    '"face_angle_yaw_degrees":"...","face_angle_pitch_degrees":"...",'
    '"face_angle_roll_degrees":"...","chin_position":"...","jaw_width_estimate":"...",'
    '"forehead_visibility":"...","occlusions_on_face":"...","neck_visibility":"...",'
    '"skin_tone_zone":"...","skin_tone_hex_estimate":"...",'
    '"expression_to_preserve":{"mouth":"...","smile_intensity":"...","eyes":"...",'
    '"eyebrows":"...","overall_emotion":"...","authenticity":"..."},'
    '"face_blend_notes":"..."},'

    '"subject_analysis":{"primary_subject":"...","positioning":"...",'
    '"scale":"...","interaction":"...",'
    '"hair":{"length":"...","cut":"...","texture":"...",'
    '"texture_quality":"...","natural_imperfections":"...","styling":"...",'
    '"styling_detail":"...","part":"...","volume":"...","color_detail":"...",'
    '"flyaways":"...","sheen":"..."},'
    '"makeup":{"eyes":"...","brows":"...","lips":"...",'
    '"foundation":"...","overall_style":"...","finish":"..."},'
    '"accessories":{},'
    '"clothing":{"garment":"...","fabric":"...","neckline":"...",'
    '"sleeve":"...","fit":"...","details":"...","color":"...","texture_description":"..."},'
    '"body_positioning":{"posture":"...","angle":"...",'
    '"weight_distribution":"...","shoulders":"...","visible_body_parts":"..."},'
    '"hands_and_gestures":{"right_hand":"...","left_hand":"...",'
    '"hand_tension":"...","naturalness":"..."}},'

    '"background":{"setting_type":"...","time_of_day":"...","weather_or_conditions":"...",'
    '"spatial_depth":"...",'
    '"elements_detailed":[{"item":"...","position":"...","distance":"...",'
    '"size":"...","condition":"...","specific_features":"..."}],'
    '"surface_materials":{"primary":"...","secondary":"...","texture_notes":"..."},'
    '"background_treatment":"...","background_blur_amount":"...","background_prompt":"..."},'

    '"generation_parameters":{"structured_prompts":{'
    '"scene_environment":"...",'
    '"subject_body_pose":"...",'
    '"face_replacement_directive":"photorealistic face of [MODEL_REFERENCE], [FACE_ANGLE_FROM_face_transplant_guide], [EXPRESSION_FROM_face_transplant_guide], seamlessly blended, skin tone matched to scene lighting",'
    '"lighting_directive":"...",'
    '"camera_lens_directive":"...",'
    '"style_quality_directive":"photorealistic, high resolution, 8K, sharp focus, professional photography, natural skin texture, no airbrushing"},'
    '"final_positive_prompt_assembly":"...",'
    '"negative_prompts":["deformed face","wrong face identity","blurry face","extra limbs",'
    '"bad anatomy","low quality","watermark","cartoon","painting","illustration",'
    '"distorted proportions","mismatched skin tone","double face","face artifacts"],'
    '"controlnet_hints":{"use_openpose":true,"use_depth_map":true,"use_face_id_adapter":true,'
    '"ip_adapter_face_strength":"0.8","controlnet_pose_strength":"0.7","controlnet_depth_strength":"0.5"},'
    '"technical_settings":{"sampler":"DPM++ 2M Karras","steps":"35","cfg_scale":"7",'
    '"denoising_strength":"0.55","face_restoration":"CodeFormer","face_restoration_weight":"0.7"},'
    '"post_processing":"..."}}'
)

CLAUDE_SYSTEM = (
    "You are a specialized computational photographer and AI image pipeline engineer. "
    "Your SOLE purpose is to analyze a reference scene photo and output a precision JSON "
    "object that will be used by a Wavespeed AI image generator to reconstruct the scene "
    "with a specific model's face injected in place of the original subject.\n\n"
    "You are NOT describing the image for human readers. You are producing structured "
    "generation data for a machine. Every field must be specific, technical, and actionable.\n\n"
    "YOUR TWO-PART TASK:\n"
    "1. Capture the SCENE (background, lighting, environment, camera settings) — preserve this exactly.\n"
    "2. Capture the SUBJECT POSE and BODY — preserve this exactly.\n"
    "3. Flag the FACE as the REPLACEMENT ZONE — this will be swapped with the model reference.\n\n"
    "CRITICAL RULES:\n"
    "- Return ONLY raw valid JSON. No markdown. No explanation. No code fences.\n"
    "- Use precise, Stable Diffusion / Flux-compatible prompt language in all text fields.\n"
    "- Never describe the face identity of the original subject — only describe face geometry, "
    "angle, and expression (which must be preserved when the model's face is inserted).\n"
    "- All prompt fields must use comma-separated keyword phrases optimized for Wavespeed/Flux.\n"
    "- Distinguish clearly between elements to PRESERVE (scene, body, pose, lighting) "
    "and elements to REPLACE (face identity only)."
)


# ── Helpers ───────────────────────────────────────────────────────────────────
def to_b64(path, max_size=2048, quality=85):
    """Encode image as base64 JPEG, resizing if needed to reduce payload."""
    img = Image.open(path)
    img = img.convert("RGB")
    # Resize if either dimension exceeds max_size, preserving aspect ratio
    if max(img.size) > max_size:
        img.thumbnail((max_size, max_size), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return base64.standard_b64encode(buf.getvalue()).decode()

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
            "No Anthropic API key found.\n"
            "Add your key to ANTHROPIC_API_KEY in your .env file.\n"
            "Get one at console.anthropic.com"
        )
    log_fn("-> Sending to Claude API...")
    body = json.dumps({
        "model": "claude-opus-4-20250514",
        "max_tokens": 8192,
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
            to_b64(model_path),
            to_b64(scene_path)
        ],
        "prompt": prompt,
        "aspect_ratio": ASPECT_RATIO,
        "resolution": RESOLUTION,
        "enable_base64_output": False,
        "enable_sync_mode": False
    }).encode()

    resp = None
    for attempt in range(3):
        req = urllib.request.Request(
            "https://api.wavespeed.ai/api/v3/" + WAVESPEED_MODEL,
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + WAVESPEED_API_KEY
            },
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                resp = json.loads(r.read())
            break
        except urllib.error.HTTPError as e:
            error_body = e.read().decode()
            raise ValueError(f"WaveSpeed API error ({e.code}): {error_body}")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if attempt < 2:
                log_fn(f"  Upload attempt {attempt+1} failed, retrying in 5s...")
                time.sleep(5)
            else:
                raise
    if resp is None:
        raise ValueError("WaveSpeed upload failed after 3 attempts")

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
        tk.Label(hdr, text="Claude Sonnet Analysis  ->  WaveSpeed 4K  ->  9:16",
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
                                 text="GENERATE POST  --  $0.208",
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
        self._check_model()
        self._log("Ready. Select a scene photo and click Generate.")

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

            # Step 1 - Analyze scene via Claude API
            self._log("-> Analyzing scene via Claude API...")
            result = analyze_via_api(self.scene_file, self._log)

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
            self.root.after(0, lambda: self.gen_btn.config(text="GENERATE POST  --  $0.208"))


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
