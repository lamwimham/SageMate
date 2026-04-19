"""
SageMate Doctor: Startup self-check module.
Ensures the environment is ready to run SageMate Core.
"""

import os
import shutil
import sys
from typing import List, Tuple

class Doctor:
    """
    Static class for environment validation.
    """

    @staticmethod
    def run() -> bool:
        """
        Run all system checks. 
        Returns True if healthy, False if fatal errors found.
        """
        if os.getenv("SAGEMATE_SKIP_DOCTOR"):
            return True

        print("🔍 SageMate Doctor: Running system checks...")
        
        errors: List[str] = []
        warnings: List[str] = []

        # 1. Python Version Check
        if sys.version_info < (3, 10):
            errors.append(f"Python 3.10+ required. Current: {sys.version.split()[0]}")

        # 2. Core Python Packages
        required_pkgs = [
            ("aiosqlite", "aiosqlite"), 
            ("fastapi", "fastapi"), 
            ("uvicorn", "uvicorn"), 
            ("pydantic", "pydantic"), 
            ("watchdog", "watchdog"), 
            ("pdf2image", "pdf2image"),
            ("PIL", "Pillow")
        ]
        
        for module_name, display_name in required_pkgs:
            try:
                __import__(module_name)
            except ImportError:
                errors.append(f"Missing package: {display_name} (run 'pip install {display_name}')")

        # 3. Environment Variables
        if not os.getenv("SAGEMATE_LLM_API_KEY"):
            errors.append("Missing env: SAGEMATE_LLM_API_KEY. Please set it in your .env file.")
        else:
            print("✅ Env: Text LLM API Key found.")

        if not os.getenv("SAGEMATE_VISION_API_KEY"):
            warnings.append(
                "Missing env: SAGEMATE_VISION_API_KEY. PDF Vision Parsing will fallback or fail. "
                "Please set it in your .env file if you plan to parse PDFs."
            )
        else:
            print("✅ Env: Vision LLM API Key found.")

        # 4. System Dependencies (Poppler for PDF Vision Parsing)
        # We check for 'pdftoppm' which is part of the poppler-utils package
        if not shutil.which("pdftoppm"):
            warnings.append(
                "System dependency 'poppler' not found. PDF Vision Parsing will fail. "
                "Install via: 'brew install poppler' (macOS) or 'apt install poppler-utils' (Linux)."
            )
        else:
            print("✅ System: Poppler found.")

        # 5. Data Directory
        data_dir = os.getenv("SAGEMATE_DATA_DIR", "./data")
        if not os.path.isdir(data_dir):
            warnings.append(f"Data directory '{data_dir}' does not exist. Will be created on startup.")

        # Report
        print("-" * 40)
        if warnings:
            for w in warnings:
                print(f"⚠️  WARNING: {w}")
        
        if errors:
            print("\n❌ FATAL ERRORS:")
            for e in errors:
                print(f"   - {e}")
            print("\n🛑 SageMate cannot start. Please fix the errors above.")
            return False
        
        print("✅ All checks passed. Ready to start.")
        print("-" * 40)
        return True
