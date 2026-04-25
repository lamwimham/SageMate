# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for SageMate desktop app sidecar.

Builds a single executable that bundles:
- Python runtime + all dependencies
- FastAPI app + all sagemate modules
- React SPA static files
- Data directory templates
"""

import sys
from pathlib import Path

# Project root — resolved from current working directory
PROJECT_ROOT = Path.cwd().resolve()
SAGEMATE_SRC = PROJECT_ROOT / "src" / "sagemate"
FRONTEND_DIST = PROJECT_ROOT / "src" / "sagemate" / "api" / "static" / "dist"

# Ensure frontend is built
if not FRONTEND_DIST.exists():
    raise FileNotFoundError(
        f"Frontend not built: {FRONTEND_DIST}\n"
        "Run: cd frontend && npm run build"
    )

block_cipher = None

a = Analysis(
    [str(SAGEMATE_SRC / "__main__.py")],
    pathex=[str(PROJECT_ROOT / "src")],
    binaries=[],
    datas=[
        # Frontend SPA static files
        (str(FRONTEND_DIST), "sagemate/api/static/dist"),
        # Jinja2 templates (if any)
        (str(SAGEMATE_SRC / "api" / "templates"), "sagemate/api/templates"),
        # Data schema templates
        (str(PROJECT_ROOT / "data" / "schema"), "data/schema"),
        # jieba dictionary files
        (str(Path(__import__("jieba").__file__).parent / "dict.txt"), "jieba"),
    ],
    hiddenimports=[
        # FastAPI / Uvicorn
        "uvicorn",
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        # FastAPI dependencies
        "fastapi",
        "fastapi.middleware.cors",
        "fastapi.responses",
        "fastapi.templating",
        "starlette",
        "starlette.middleware",
        # Pydantic
        "pydantic",
        "pydantic_core",
        # Database
        "aiosqlite",
        "sqlite3",
        # Async
        "anyio",
        "anyio._backends",
        "anyio._backends._asyncio",
        # HTTP clients
        "httpx",
        "httpcore",
        "certifi",
        # OpenAI
        "openai",
        # YAML
        "yaml",
        # Watchdog
        "watchdog",
        "watchdog.observers",
        "watchdog.observers.fsevents",  # macOS
        # Jinja2
        "jinja2",
        "jinja2.ext",
        # jieba
        "jieba",
        "jieba.posseg",
        "jieba.analyse",
        # Trafilatura
        "trafilatura",
        # Playwright (optional, may be large)
        # "playwright",
        # SageMate modules (auto-discovered)
        "sagemate.api.app",
        "sagemate.api.dependencies",
        "sagemate.api.routers.wechat",
        "sagemate.core.config",
        "sagemate.core.store",
        "sagemate.core.watcher",
        "sagemate.core.agent.pipeline",
        "sagemate.core.agent.router",
        "sagemate.core.agent.session",
        "sagemate.core.agent.intent_clarification",
        "sagemate.core.chat",
        "sagemate.core.slug",
        "sagemate.core.event_bus",
        "sagemate.models",
        "sagemate.ingest.compiler.compiler",
        "sagemate.ingest.compiler.pipeline",
        "sagemate.ingest.compiler.strategies",
        "sagemate.ingest.compiler.source_archive",
        "sagemate.ingest.compiler.unit_of_work",
        "sagemate.ingest.compiler.prompts",
        "sagemate.ingest.service",
        "sagemate.ingest.task_manager",
        "sagemate.ingest.adapters.file_parser",
        "sagemate.ingest.adapters.file_validator",
        "sagemate.ingest.adapters.archive_helper",
        "sagemate.ingest.adapters.url_collector",
        "sagemate.ingest.adapters.pdf_strategies",
        "sagemate.ingest.adapters.voice_parser",
        "sagemate.ingest.adapters.vision_parser",
        "sagemate.system.lint",
        "sagemate.system.cron_scheduler",
        "sagemate.system.cost_monitor",
        "sagemate.doctor",
        "sagemate.plugins.wechat.channel",
        "sagemate.plugins.wechat.service",
        "sagemate.plugins.wechat.auth",
        "sagemate.plugins.wechat.api",
        # Pillow (PIL) - required by wechat auth
        "PIL",
        "PIL.Image",
        "PIL.ImageDraw",
        "PIL.ImageFont",
    ],
    hookspath=[str(PROJECT_ROOT / "scripts" / "pyinstaller")],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude large optional dependencies to reduce binary size
        "matplotlib",
        "numpy",
        "pandas",
        "scipy",
        "sklearn",
        "torch",
        "torchvision",
        "torchaudio",
        "tensorflow",
        "numba",
        "llvmlite",
        "sympy",
        "openai-whisper",
        "whisper",
        # "PIL",  # Needed by wechat auth plugin
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="sagemate-server",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # Compress with UPX if available
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window in production
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch="arm64",  # macOS Apple Silicon
    codesign_identity=None,
    entitlements_file=None,
    icon=str(PROJECT_ROOT / "logo_sagemate.png"),
)
