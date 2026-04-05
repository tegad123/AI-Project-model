# ── AI MODEL POST GENERATOR — CONFIG ────────────────────────────────────────
# Keep this file private. Do not share publicly.
# Share only with trusted collaborators.
#
# Secrets are loaded from .env file. Copy .env.example to .env and fill in your values.

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Path to your reference model image (set in .env, works on Windows/macOS/Linux)
AMBER_DEFAULT_PATH = str(Path(os.getenv("AMBER_DEFAULT_PATH", "")))

# API keys (loaded from .env)
WAVESPEED_API_KEY = os.getenv("WAVESPEED_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# WaveSpeed model to use
WAVESPEED_MODEL = "google/nano-banana-pro/edit"

# Image output settings — do not change unless WaveSpeed updates pricing
ASPECT_RATIO   = "9:16"
RESOLUTION     = "4k"
COST_PER_IMAGE = 0.204

# Model description — used in the generation prompt
MODEL_NAME = "Amber"
MODEL_DESCRIPTION = (
    "Amber: young woman, warm olive skin, very long thick jet black wavy hair with "
    "voluminous beach waves falling past bust, large hazel amber-brown eyes, bold defined "
    "dark eyebrows, full lips with nude-pink color, natural glam makeup with warm bronze "
    "eyeshadow and lash extensions, diamond pave cross pendant necklace on silver chain."
)
