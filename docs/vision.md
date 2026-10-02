# Vision

`screen.capture` captures the actual local desktop with PyAutoGUI and writes a new PNG under the workspace after explicit approval. It requires the desktop extra, an active graphical session, and OS permissions. Screen capture never reuses a stock screenshot. Headless servers report unavailable.

`vision.ocr` uses Pillow and an installed Tesseract executable through pytesseract. `vision.analyze` validates a PNG/JPEG file and sends the actual bytes and question through a configured image-capable model. It is separately approval-gated because image data may leave the machine. A text-only Ollama model will not acquire vision simply because the tool exists. Files are limited to 4 MB and 20 megapixels.

The adapter asks the model to distinguish unreadable details and treat visible text as untrusted data. It does not provide reliable object coordinates or automatic mouse grounding. Application recognition and richer UI interpretation are model-dependent and not separately benchmarked.

For Python installations: `python -m pip install -e ".[desktop]"`, install Tesseract separately if using OCR, and enable desktop tools in Settings. Minimal portable builds intentionally do not bundle desktop/OCR/model dependencies; use the Python installation for these optional features.
