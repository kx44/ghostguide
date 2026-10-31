"""Muse Glimmer on Modal: the check ladder's rung 9c (engine/models/glimmer.py talks to it).

llama.cpp serves the 17 GB Q4_K_M GGUF plus the vision projector on one L40S (48 GB) in Asia-Pacific, so the whole
model sits on the GPU, with the DFlash draft for speculative decoding (~3 s per check in the model instead of ~5.5). The container scales to zero after SCALEDOWN_S idle seconds; the weights live in a Modal volume, so a
cold start only loads them (no download).

Contract (POST, JSON): {"image_b64": "...", "image_mime": "image/jpeg", "question": "...", "check": "..."}
                     → {"result": "done|not_yet|wrong", "why": "...", "seconds": 1.2}
Auth: header `Authorization: Bearer <GLIMMER_TOKEN>`, from the Modal secret `glimmer-token`; the engine sends
GLIMMER_MODAL_TOKEN from .env. Without it anyone with the URL could spend the credits.

One-time setup (Windows, from the repo folder):
  py -m modal secret create glimmer-token GLIMMER_TOKEN=<random string>   (same value as GLIMMER_MODAL_TOKEN)
  py -m modal run deploy/modal_glimmer.py::download                       (~18 GB into the volume, CPU only)
  py -m modal deploy deploy/modal_glimmer.py                              (prints the URL → GLIMMER_MODAL_URL)
"""
from __future__ import annotations

import modal

REPO = "meta-models/Muse-Glimmer-30B-GGUF"
MODEL = "Muse-Glimmer-30B-KQuant-17GB-Q4_K_M.gguf"
MMPROJ = "mmproj-Muse-Glimmer-30B-Q4_K_M.gguf"
DRAFT = "dflash-Muse-Glimmer-30B-Q4_K_M.gguf"   # DFlash speculative-decoding draft, ~1.6 GB
WEIGHTS = "/weights"
PORT = 8080
SCALEDOWN_S = 300       # idle seconds before the GPU is released (L40S ≈ $1.95/h × 1.15 for the region, while up)
MAX_TOKENS = 2048       # reasoning counts toward this; running out mid-thought returns empty content

MAX_IMAGE_B64 = 16 * 2 ** 20    # a 1920 px screenshot as a JPEG is far below this
IMAGE_MIMES = ("image/jpeg", "image/png")


def authorised(header, token: str) -> bool:
    """Fails closed when the secret is missing, and takes the same time however much of the token is right."""
    import hmac

    return bool(token) and isinstance(header, str) and hmac.compare_digest(header.encode(), f"Bearer {token}".encode())


def acceptable(image, mime) -> bool:
    return isinstance(image, str) and 0 < len(image) <= MAX_IMAGE_B64 and mime in IMAGE_MIMES


app = modal.App("ghostguide-glimmer-ap")
volume = modal.Volume.from_name("glimmer-weights", create_if_missing=True)

# Muse Glimmer needs llama.cpp b10353 or newer (dev.meta.ai/docs/muse-glimmer/deploy).
server_image = (
    modal.Image.from_registry("ghcr.io/ggml-org/llama.cpp:server-cuda", add_python="3.11")
    .entrypoint([])
    .pip_install("fastapi[standard]", "httpx")
)
download_image = modal.Image.debian_slim(python_version="3.11").pip_install("huggingface_hub[hf_transfer]")


@app.function(image=download_image, volumes={WEIGHTS: volume}, timeout=3600)
def download():
    import os
    from huggingface_hub import hf_hub_download

    os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"
    for name in (MODEL, MMPROJ, DRAFT):
        path = hf_hub_download(REPO, name, local_dir=WEIGHTS)
        print(f"{name}: {os.path.getsize(path) / 1e9:.1f} GB")
    volume.commit()


# region="ap" + routing via Mumbai: ~0.6 s of network per check from South-East Asia instead of ~1.6 s through us-east,
# for 1.15x the GPU price. routing_region can only be set on a function's first deploy (hence the -ap app name).
@app.cls(image=server_image, gpu="L40S", region="ap", routing_region="ap-south", volumes={WEIGHTS: volume},
         scaledown_window=SCALEDOWN_S,
         timeout=600, secrets=[modal.Secret.from_name("glimmer-token")])
@modal.concurrent(max_inputs=4)
class Glimmer:
    @modal.enter()
    def start(self):
        import subprocess
        import time

        import httpx

        self.proc = subprocess.Popen([
            "/app/llama-server", "-m", f"{WEIGHTS}/{MODEL}", "--mmproj", f"{WEIGHTS}/{MMPROJ}",
            "-a", "muse-glimmer", "-ngl", "99", "-c", "32768", "-np", "1",
            "--host", "127.0.0.1", "--port", str(PORT),
            "--chat-template-kwargs", '{"reasoning_strength":"low"}',
            # DFlash draft (flags from the dev.meta.ai llama.cpp docs); a "[spec] failed to measure" warning is harmless.
            "-md", f"{WEIGHTS}/{DRAFT}", "--spec-type", "draft-dflash", "-ngld", "99", "--spec-draft-n-max", "4",
        ])
        t0 = time.monotonic()
        while time.monotonic() - t0 < 540:
            if self.proc.poll() is not None:
                raise RuntimeError(f"llama-server exited with {self.proc.returncode}")
            try:
                if httpx.get(f"http://127.0.0.1:{PORT}/health", timeout=2).status_code == 200:
                    print(f"llama-server ready in {time.monotonic() - t0:.0f}s")
                    return
            except httpx.HTTPError:
                pass
            time.sleep(2)
        raise RuntimeError("llama-server didn't come up")

    @modal.exit()
    def stop(self):
        self.proc.terminate()

    @modal.asgi_app()
    def web(self):
        import json
        import os
        import re
        import time

        import httpx
        from fastapi import FastAPI, Header, HTTPException

        api = FastAPI()

        @api.post("/")
        def check(body: dict, authorization: str | None = Header(None)):
            if not authorised(authorization, os.environ.get("GLIMMER_TOKEN", "")):
                raise HTTPException(status_code=401, detail="bad token")
            t0 = time.monotonic()
            image = body.get("image_b64") or body.get("image_png_b64") or ""     # image_png_b64: the first contract
            mime = body.get("image_mime", "image/png")
            if not acceptable(image, mime):
                raise HTTPException(status_code=413, detail="that isn't a picture of a sensible size")
            # No temperature: Meta advises against greedy; llama.cpp applies the checkpoint's published sampling.
            r = httpx.post(f"http://127.0.0.1:{PORT}/v1/chat/completions", timeout=120, json={
                "model": "muse-glimmer", "max_tokens": MAX_TOKENS,
                "messages": [{"role": "user", "content": [
                    {"type": "text", "text": body["question"]},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image}"}},
                ]}],
            })
            r.raise_for_status()
            text = r.json()["choices"][0]["message"].get("content") or ""
            out = {"result": "unknown", "why": text[:160]}
            m = re.search(r"\{.*\}", text, re.S)
            if m:
                try:
                    out = json.loads(m.group(0))
                except ValueError:
                    pass
            out["seconds"] = round(time.monotonic() - t0, 2)
            return out

        return api
