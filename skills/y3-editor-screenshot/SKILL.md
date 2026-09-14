---
name: y3-editor-screenshot
description: >
  Y3 editor window screenshot tool. Captures Y3 editor main window or sub-windows
  (ObjectEditor, UIEditor, ResourceManager, etc.) and saves to skill result folder.
  ALWAYS use this skill when user mentions:
  screenshot editor, capture editor, take screenshot,
  editor screenshot, capture window, screenshot object editor,
  screenshot UI editor, screenshot scene editor.
---

# Y3 Editor Screenshot Skill

> Pure Python (stdlib only, no pip install needed). Captures Y3 editor windows via Win32 screen DC BitBlt.

## Usage

```bash
python .y3maker/skills/y3-editor-screenshot/scripts/editor_screenshot.py [OPTIONS]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--target TARGET` | `main` | Window to capture: main / object / ui / resource / trigger / scene / all |
| `--output-dir DIR` | `<skill>/result` | Custom output directory |
| `--list` | - | List all detectable windows and exit |
| `--delay SEC` | `0.5` | Delay before capture (seconds) |

## Supported Windows

| Target | Window Title (CN) | Description |
|--------|------------------|-------------|
| `main` | Y3 - xxx - EntryMap | Main editor window |
| `object` | object editor | Object/Unit editor panel |
| `ui` | UI editor | UI editor panel |
| `resource` | resource manager | Resource browser panel |
| `trigger` | trigger editor / ECA | Trigger/ECA editor panel |
| `scene` | scene editor | 3D scene editor panel |
| `all` | - | Capture all detectable windows |

## Output

- Path: `.y3maker/skills/y3-editor-screenshot/result/`
- Format: `<target>_<YYYYMMDD_HHMMSS>.png`
- Example: `main_20260911_151530.png`, `object_20260911_151532.png`

## Technical Notes

- Uses screen DC BitBlt (not PrintWindow) to correctly capture Qt5/OpenGL rendered content
- DWM extended frame bounds for accurate window rect on Windows 10/11
- Pure PNG output using stdlib zlib compression (no PIL/Pillow dependency)
- Window must be visible (not minimized) and not occluded by other windows
