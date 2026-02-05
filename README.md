# Tripo Tools

PySide6 GUI and CLI for Tripo AI 3D generation — image-to-3D, multiview turnaround, and text-to-3D.

## Requirements

- **Python 3.9+**
- **PySide6**: `pip install PySide6`
- **requests**: `pip install requests`
- **Tripo API key**: Get one at [platform.tripo3d.ai](https://platform.tripo3d.ai)

## Usage

### GUI
```bash
python tripo_gui.py
```

Three input modes:
- **📷 Single Image** — one photo → 3D model
- **🔄 Multiview Turnaround** — 2-6 angle views for better reconstruction
- **✍️ Text Prompt** — describe what you want

### CLI
```bash
# Set your API key
export TRIPO_API_KEY=tsk_your_key_here   # Linux/Mac
$env:TRIPO_API_KEY = "tsk_your_key_here"  # PowerShell

# Image to 3D
python tripo_generate.py --image photo.png --output model.glb

# Text to 3D
python tripo_generate.py --prompt "a wooden barrel" --output barrel.glb

# Different format
python tripo_generate.py --image photo.png --output model.fbx --format fbx

# Check credits
python tripo_generate.py --balance
```

## Output Formats

GLB, FBX, OBJ, STL, USDZ

## Files

- `tripo_gui.py` — PySide6 GUI application
- `tripo_generate.py` — CLI script and Tripo API client
