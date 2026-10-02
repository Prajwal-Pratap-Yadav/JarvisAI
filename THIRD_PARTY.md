# Third-party software and original assets

JARVIS source code is MIT licensed. The ring visual, mark, layout, CSS, and other project assets are original. No film artwork, sound recordings, logos, or screenshots are included.

Runtime dependencies retain their own licenses: FastAPI (MIT), Starlette (BSD-3-Clause), Pydantic and pydantic-core (MIT), HTTPX and httpcore (BSD-3-Clause), Uvicorn (BSD-3-Clause), psutil (BSD-3-Clause), websockets (BSD-3-Clause), and their transitive dependencies. `requirements.lock` records the exact release dependency set. Certifi distributes Mozilla's certificate authorities under MPL-2.0. Python retains the PSF license. Portable archives include collected dependency license files and the interpreter license.

Optional integrations are installed separately: Playwright (Apache-2.0) and its browser distribution licenses, PyAutoGUI (BSD-3-Clause), Pillow (HPND), pytesseract (Apache-2.0), pyperclip (BSD-3-Clause), and an independently installed Tesseract executable. Model weights are not distributed; their licenses depend on the model you choose. Cloud services have their own terms and fees. The application does not bundle credentials or promise free access to third-party services.

The frozen executable is built using PyInstaller's GPL license with its bootloader exception. Its license is included in portable archives. Dependency notices are evidence of included software, not promotional attribution.
