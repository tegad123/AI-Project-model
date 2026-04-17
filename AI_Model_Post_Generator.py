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
        MODEL_NAME, MODEL_DESCRIPTION,
        VENICE_API_KEY, VENICE_MODEL, VENICE_COST_PER_IMAGE,
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


# ── Venice prompt generator ──────────────────────────────────────────────────
# Venice's qwen-edit model sees both images directly, so the prompt must NOT
# describe the scene. It should be a short imperative edit directive focused
# only on the face swap. Claude generates this prompt from MODEL_DESCRIPTION.
VENICE_CLAUDE_SYSTEM = (
    "You help generate one instruction string for Venice.ai's image multi-edit API.\n\n"
    "Target endpoint:\n"
    "- POST https://api.venice.ai/api/v1/image/multi-edit\n"
    '- modelId: "qwen-edit"\n'
    "- images[0] = base scene photo\n"
    "- images[1] = clear reference portrait of the target person\n"
    "- safe_mode is handled by the client, you do not mention it.\n\n"
    "The API already sees both images, so you MUST NOT describe the background, "
    "pose, camera, clothing, furniture, or environment. You only describe the "
    "target person's facial identity.\n\n"
    "Your job:\n"
    "1) Insert the provided model_name into the fixed face-swap template below.\n"
    "2) Construct a concise model_description (max ~200 characters) describing "
    "only the face: face shape, skin tone, eyes, nose, lips, hair, age range, "
    "and general expression.\n\n"
    "Use this exact template, replacing {model_name} and {model_description}:\n\n"
    '"Use the first image as the base photo.\n'
    "Use the second image only as a reference for the face of {model_name}.\n"
    "Replace only the face in the base photo with the face from the reference image.\n"
    "Do not change the body shape, curves, pose, camera angle, crop, or position of the body.\n"
    "Do not change the hair length, hair style, clothing, jewelry, hands, or any objects in the room.\n"
    "Do not change the background, furniture, pillows, windows, or lighting.\n"
    "Keep the composition and shadows exactly the same as in the base photo.\n"
    "Make the edit photorealistic and seamless so it looks like a real, unedited photograph of {model_name}.\n"
    'Their facial identity should match this description: {model_description}."\n\n'
    "Output requirements:\n"
    "- Return ONE plain text string: the final prompt with {model_name} and {model_description} filled in.\n"
    "- No JSON, no Markdown, no extra commentary.\n"
    "- Total length must stay well under 1500 characters."
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
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 4096,
        "system": CLAUDE_SYSTEM,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image", "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
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
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        raise ValueError(f"Claude API error ({e.code}): {error_body}")

    raw = data["content"][0]["text"].strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(raw)


def generate_venice_prompt(model_name, face_traits, log_fn):
    """Ask Claude to produce the Venice edit-directive string from face traits."""
    if not ANTHROPIC_API_KEY:
        raise ValueError("No Anthropic API key. Add ANTHROPIC_API_KEY to .env")
    user_msg = (
        f"model_name: {model_name}\n\n"
        f"Face traits for model_description:\n{face_traits}\n\n"
        "Generate the final prompt string using the template from the system message.\n"
        "Return only that single prompt line, nothing else."
    )
    body = json.dumps({
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 1024,
        "system": VENICE_CLAUDE_SYSTEM,
        "messages": [{"role": "user", "content": user_msg}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    log_fn("-> Generating Venice edit prompt via Claude...")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise ValueError(f"Claude API error ({e.code}): {e.read().decode()}")
    text = data["content"][0]["text"].strip()
    # Strip accidental code fences
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return text



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


# ── Venice.ai ─────────────────────────────────────────────────────────────────
def build_venice_prompt(scene_json, model_description, max_chars=1400):
    """Build a concise prompt from the Claude analysis JSON for Venice models.

    Uses the pre-assembled prompt fields in the JSON if available, otherwise
    composes a short directive. Caps at max_chars to fit qwen-edit's 1500 limit.
    """
    gen = scene_json.get("generation_parameters", {}) if isinstance(scene_json, dict) else {}
    final = gen.get("final_positive_prompt_assembly")
    structured = gen.get("structured_prompts", {})

    if final and isinstance(final, str):
        core = final
    elif structured:
        parts = [
            structured.get("scene_environment", ""),
            structured.get("subject_body_pose", ""),
            structured.get("lighting_directive", ""),
            structured.get("camera_lens_directive", ""),
            structured.get("style_quality_directive", ""),
        ]
        core = ", ".join(p for p in parts if p)
    else:
        core = "photorealistic portrait, high quality, 4K"

    directive = (
        f"Replace the face of the subject in image 2 (scene) with the face of the model in image 1. "
        f"Model: {model_description} Scene: {core}"
    )
    if len(directive) > max_chars:
        directive = directive[:max_chars - 3] + "..."
    return directive


def call_venice(scene_path, model_path, prompt, log_fn, negative_prompt=None):
    """Call Venice.ai /image/multi-edit with safe_mode=False. Returns (kind, payload)."""
    if not VENICE_API_KEY:
        raise ValueError("No Venice API key. Add VENICE_API_KEY to .env")
    # Venice requires data URI prefix so it can detect image format.
    # For /image/multi-edit, images[0] is the base and subsequent images are
    # edit layers — so scene goes first and the face reference goes second.
    def _data_uri(path):
        return "data:image/jpeg;base64," + to_b64(path)
    payload = {
        "modelId": VENICE_MODEL,
        "prompt": prompt,
        "images": [_data_uri(scene_path), _data_uri(model_path)],
        "safe_mode": False,
    }
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        "https://api.venice.ai/api/v1/image/multi-edit",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + VENICE_API_KEY,
        },
        method="POST",
    )
    log_fn("-> Generating via Venice.ai (safe_mode=off)...")
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            resp_bytes = r.read()
            content_type = r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        raise ValueError(f"Venice API error ({e.code}): {e.read().decode()}")

    if content_type.startswith("image/"):
        return ("bytes", resp_bytes)
    resp = json.loads(resp_bytes)
    url = resp.get("url") or resp.get("data", {}).get("url")
    if url:
        return ("url", url)
    b64 = (resp.get("image")
           or resp.get("data", {}).get("image")
           or (resp.get("images", [None])[0] if resp.get("images") else None))
    if b64:
        return ("b64", b64)
    raise ValueError(f"Unexpected Venice response: {resp}")


def save_output(kind, payload, path):
    """Save a generator result to disk, given its (kind, payload) form."""
    if kind == "url":
        download_image(payload, path)
    elif kind == "bytes":
        with open(path, "wb") as f:
            f.write(payload)
    elif kind == "b64":
        with open(path, "wb") as f:
            f.write(base64.b64decode(payload))
    else:
        raise ValueError(f"Unknown output kind: {kind}")


def compress_image(path, quality=82):
    """Re-save JPEG at reduced quality, preserving ICC profile and resolution."""
    img = Image.open(path)
    source_format = img.format
    icc = img.info.get("icc_profile")
    if img.mode != "RGB":
        img = img.convert("RGB")
    save_kwargs = {
        "format": "JPEG",
        "quality": quality,
        "optimize": True,
    }
    if source_format == "JPEG":
        save_kwargs["subsampling"] = "keep"
    if icc:
        save_kwargs["icc_profile"] = icc
    img.save(path, **save_kwargs)


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
        self.gen_btn.pack(fill="x", padx=30, pady=(0, 6))

        # Venice generate button (permissive mode)
        self.venice_btn = tk.Button(self.root,
                                    text=f"GENERATE (VENICE) — ${VENICE_COST_PER_IMAGE:.3f}",
                                    font=("Georgia", 13, "bold"),
                                    bg="#8a5aff", fg="#fff", relief="flat",
                                    cursor="hand2", pady=12,
                                    command=self._start_venice)
        self.venice_btn.pack(fill="x", padx=30, pady=(0, 10))

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
        self.venice_btn.config(state="disabled" if busy else "normal")
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

    def _start_venice(self):
        if not self.scene_file:
            messagebox.showwarning("No Scene", "Please select a scene photo first.")
            return
        if not os.path.exists(AMBER_DEFAULT_PATH):
            messagebox.showerror("Model Not Found",
                "Model image not found at:\n" + AMBER_DEFAULT_PATH +
                "\n\nUpdate AMBER_DEFAULT_PATH in config.py")
            return
        self._set_busy(True)
        self.venice_btn.config(text="Working...")
        threading.Thread(target=self._run_venice, daemon=True).start()

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
            original_size = os.path.getsize(out)
            compress_image(out)
            compressed_size = os.path.getsize(out)
            self._log(f"  Compressed: {original_size // 1024}KB -> {compressed_size // 1024}KB")
            self._log("Done! Saved to: " + out)

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

    def _run_venice(self):
        try:
            self._log("Starting pipeline (Venice)...")
            base = os.path.splitext(self.scene_file)[0]

            # Step 1 - Generate a concise edit directive via Claude.
            # Venice/qwen-edit sees both images directly, so we do NOT describe
            # the scene — only the face identity. MODEL_DESCRIPTION feeds the
            # face traits; Claude returns the final prompt string.
            venice_prompt = generate_venice_prompt(
                MODEL_NAME, MODEL_DESCRIPTION, self._log
            )
            # Safety cap for qwen-edit's 1500 char limit
            if len(venice_prompt) > 1400:
                venice_prompt = venice_prompt[:1400]
            self._log(f"  Venice prompt: {len(venice_prompt)} chars")

            # Step 2 - Call Venice with scene as base image, reference as layer
            kind, payload = call_venice(
                self.scene_file, AMBER_DEFAULT_PATH, venice_prompt, self._log
            )

            out = base + "_venice.jpg"
            save_output(kind, payload, out)
            original_size = os.path.getsize(out)
            compress_image(out)
            compressed_size = os.path.getsize(out)
            self._log(f"  Compressed: {original_size // 1024}KB -> {compressed_size // 1024}KB")
            self._log("Done! Saved to: " + out)

            self.root.after(0, lambda: messagebox.showinfo(
                "Done!", "Venice image saved!\n\n" + out))

        except Exception as ex:
            err = str(ex)
            self._log("Error: " + err)
            self.root.after(0, lambda msg=err: messagebox.showerror("Error", msg))
        finally:
            self.root.after(0, lambda: self._set_busy(False))
            self.root.after(0, lambda: self.venice_btn.config(
                text=f"GENERATE (VENICE) — ${VENICE_COST_PER_IMAGE:.3f}"))


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
