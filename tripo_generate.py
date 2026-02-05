"""
Tripo AI — Image-to-3D and Text-to-3D generation.

Usage:
    # Image to 3D
    python tripo_generate.py --image photo.png --output model.glb

    # Text to 3D
    python tripo_generate.py --prompt "a wooden barrel" --output model.glb

    # With options
    python tripo_generate.py --image photo.png --output model.fbx \
        --format fbx --quality detailed

Environment:
    TRIPO_API_KEY=tsk_your_key_here

Requirements:
    pip install requests
"""

import argparse
import os
import sys
import time
import json
import requests
from pathlib import Path

API_BASE = "https://api.tripo3d.ai/v2/openapi"

# Task types
TASK_IMAGE_TO_MODEL = "image_to_model"
TASK_TEXT_TO_MODEL = "text_to_model"
TASK_MULTIVIEW_TO_MODEL = "multiview_to_model"
TASK_REFINE_MODEL = "refine_model"


class TripoClient:
    """Simple client for Tripo's 3D generation API."""

    def __init__(self, api_key):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_key}",
        })

    def upload_image(self, image_path):
        """Upload an image file and get an image token."""
        print(f"[tripo] Uploading image: {image_path}")

        with open(image_path, "rb") as f:
            resp = self.session.post(
                f"{API_BASE}/upload",
                files={"file": (os.path.basename(image_path), f)},
            )

        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            raise RuntimeError(f"Upload failed: {data.get('message', data)}")

        token = data["data"]["image_token"]
        print(f"[tripo] Image uploaded. Token: {token[:20]}...")
        return token

    def create_task(self, task_type, params):
        """Create a generation task."""
        body = {"type": task_type, **params}
        print(f"[tripo] Creating task: {task_type}")

        resp = self.session.post(
            f"{API_BASE}/task",
            json=body,
        )

        resp.raise_for_status()
        data = resp.json()

        if data.get("code") != 0:
            raise RuntimeError(f"Task creation failed: {data.get('message', data)}")

        task_id = data["data"]["task_id"]
        print(f"[tripo] Task created: {task_id}")
        return task_id

    def poll_task(self, task_id, poll_interval=3, timeout=600):
        """Poll a task until completion or failure."""
        print(f"[tripo] Waiting for task {task_id}...")
        start = time.time()

        while True:
            elapsed = time.time() - start
            if elapsed > timeout:
                raise TimeoutError(
                    f"Task {task_id} timed out after {timeout}s"
                )

            resp = self.session.get(f"{API_BASE}/task/{task_id}")
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != 0:
                raise RuntimeError(f"Poll failed: {data.get('message', data)}")

            task_data = data["data"]
            status = task_data.get("status")
            progress = task_data.get("progress", 0)

            # Print progress
            bar_len = 30
            filled = int(bar_len * progress / 100)
            bar = "█" * filled + "░" * (bar_len - filled)
            print(f"\r[tripo] [{bar}] {progress}% — {status}",
                  end="", flush=True)

            if status == "success":
                print()  # newline after progress bar
                return task_data

            if status in ("failed", "cancelled", "unknown"):
                print()
                raise RuntimeError(
                    f"Task {status}: {task_data.get('message', 'no details')}"
                )

            time.sleep(poll_interval)

    def download_model(self, task_data, output_path, fmt="glb"):
        """Download the generated model."""
        output = task_data.get("output", {})

        # Try to get the requested format
        model_url = output.get("model")

        # Check for specific format URLs in rendered result
        if not model_url:
            # Some tasks have pbr_model, base_model, etc.
            for key in ["pbr_model", "base_model", "model"]:
                if key in output and output[key]:
                    model_url = output[key]
                    break

        if not model_url:
            print(f"[tripo] Available output keys: {list(output.keys())}")
            raise RuntimeError("No model URL found in task output")

        print(f"[tripo] Downloading model...")

        resp = self.session.get(model_url, stream=True)
        resp.raise_for_status()

        # Ensure output directory exists
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        total = int(resp.headers.get("content-length", 0))
        downloaded = 0

        with open(output_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = int(100 * downloaded / total)
                    mb = downloaded / (1024 * 1024)
                    print(f"\r[tripo] Downloaded: {mb:.1f} MB ({pct}%)",
                          end="", flush=True)

        print(f"\n[tripo] Saved: {output_path} ({downloaded / (1024*1024):.1f} MB)")
        return output_path

    def get_balance(self):
        """Check remaining API credits."""
        resp = self.session.get(f"{API_BASE}/user/balance")
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"Balance check failed: {data.get('message', data)}")
        return data["data"]


def image_to_3d(client, image_path, output_path, fmt="glb",
                model_version="default", texture=True):
    """Full pipeline: upload image → create task → poll → download."""
    # Upload
    image_token = client.upload_image(image_path)

    # Create task
    params = {
        "file": {"type": "image_token", "file_token": image_token},
    }

    if model_version != "default":
        params["model_version"] = model_version

    task_id = client.create_task(TASK_IMAGE_TO_MODEL, params)

    # Poll
    task_data = client.poll_task(task_id)

    # Download
    client.download_model(task_data, output_path, fmt)

    return task_data


def text_to_3d(client, prompt, output_path, fmt="glb",
               model_version="default"):
    """Full pipeline: prompt → create task → poll → download."""
    params = {
        "prompt": prompt,
    }

    if model_version != "default":
        params["model_version"] = model_version

    task_id = client.create_task(TASK_TEXT_TO_MODEL, params)

    # Poll
    task_data = client.poll_task(task_id)

    # Download
    client.download_model(task_data, output_path, fmt)

    return task_data


def main():
    parser = argparse.ArgumentParser(
        description="Tripo AI — Image-to-3D and Text-to-3D generation"
    )

    # Input (one required)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--image", help="Input image file path")
    input_group.add_argument("--prompt", help="Text prompt for 3D generation")

    # Output
    parser.add_argument("--output", "-o", required=True,
                        help="Output file path (e.g., model.glb)")
    parser.add_argument("--format", "-f", default="glb",
                        choices=["glb", "fbx", "obj", "stl", "usdz"],
                        help="Output format (default: glb)")

    # Options
    parser.add_argument("--model-version", default="default",
                        help="Model version (default: latest)")
    parser.add_argument("--api-key",
                        help="Tripo API key (or set TRIPO_API_KEY env var)")
    parser.add_argument("--timeout", type=int, default=600,
                        help="Max wait time in seconds (default: 600)")
    parser.add_argument("--balance", action="store_true",
                        help="Check credit balance and exit")

    args = parser.parse_args()

    # Get API key
    api_key = args.api_key or os.environ.get("TRIPO_API_KEY")
    if not api_key:
        print("[tripo] ERROR: No API key. Set TRIPO_API_KEY or use --api-key")
        sys.exit(1)

    client = TripoClient(api_key)

    # Balance check
    if args.balance:
        balance = client.get_balance()
        print(f"[tripo] Credits remaining: {json.dumps(balance, indent=2)}")
        return

    # Validate input
    if args.image and not os.path.isfile(args.image):
        print(f"[tripo] ERROR: Image not found: {args.image}")
        sys.exit(1)

    # Ensure output has correct extension
    output_path = args.output
    expected_ext = f".{args.format}"
    if not output_path.lower().endswith(expected_ext):
        output_path = str(Path(output_path).with_suffix(expected_ext))
        print(f"[tripo] Output adjusted to: {output_path}")

    print(f"[tripo] Mode: {'Image → 3D' if args.image else 'Text → 3D'}")
    print(f"[tripo] Output: {output_path}")
    print()

    try:
        if args.image:
            task_data = image_to_3d(
                client, args.image, output_path,
                fmt=args.format,
                model_version=args.model_version,
            )
        else:
            task_data = text_to_3d(
                client, args.prompt, output_path,
                fmt=args.format,
                model_version=args.model_version,
            )

        print(f"\n[tripo] ✓ Done!")

    except KeyboardInterrupt:
        print("\n[tripo] Cancelled.")
        sys.exit(1)
    except Exception as e:
        print(f"\n[tripo] ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
