Image Tinder Sorter

A small PyQt5 application to quickly sort images from the current folder into named folders using hotkeys.

Features
- Page 1: Define hotkey -> folder name mappings.
- Page 2: View images one-by-one, click folder buttons or press the hotkey to move images to `./==SORTED==/<FolderName>`.
- Undo (Ctrl+Z) to move last moved image back.
- Skip (Ctrl+N) to skip image (animation left).
- Simple slide animations for move/skip/undo.

Quick start
1. Install dependencies:

```bash
python -m pip install -r requirements.txt
```

2. Run:

```bash
python main.py
```

Notes
- Run the script in the folder containing your images.
- Supported extensions: jpg, jpeg, png, bmp, gif, webp.
- Use single-character hotkeys (letters or digits).

Limitations & next steps
- Hotkeys are single characters only.
- More robust key handling, persistent mappings, and better animations can be added.
