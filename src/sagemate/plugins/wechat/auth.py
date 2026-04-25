# -*- coding: utf-8 -*-
"""WeChat Authentication & Terminal QR Display."""

from __future__ import annotations

import io
import json
import logging
import os
import asyncio
import time
from pathlib import Path

from PIL import Image

from .api import WechatApiClient
from .types import WechatAccountData

logger = logging.getLogger(__name__)


def _token_dir() -> Path:
    """Lazy-evaluated token directory using settings."""
    from sagemate.core.config import settings
    return settings.data_dir / "wechat" / "tokens"


def _default_account_file() -> Path:
    return _token_dir() / "default.json"


class QRDisplay:
    """Render QR code in terminal using ASCII art."""

    @staticmethod
    def render(url: str):
        """
        Render a QR code in the terminal from a URL.
        Uses the `qrcode` library for robust terminal rendering.
        """
        try:
            import qrcode
            
            print("\n" + "=" * 50)
            print("🔐 WeChat Login (SageMate)")
            print("=" * 50)
            print(f"URL: {url[:50]}...")
            
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=1,
                border=1,
            )
            qr.add_data(url)
            qr.make(fit=True)
            
            # Render to terminal
            qr.print_ascii(invert=True)
            
            print("=" * 50)
            print("👉 Open WeChat -> Scan to login")
            print("=" * 50 + "\n")
            
        except ImportError:
            # Fallback if qrcode library is missing
            print(f"\n❌ 'qrcode' library not found.")
            print(f"Please install it: pip install 'qrcode[pil]'")
            print(f"\nAlternatively, copy this URL into your browser:\n{url}\n")


class WechatAuthenticator:
    """Handles the login flow."""

    def __init__(self, client: WechatApiClient):
        self.client = client
        _token_dir().mkdir(parents=True, exist_ok=True)

    @property
    def _account_file(self) -> Path:
        return _default_account_file()

    def invalidate_account(self):
        """删除本地保存的 Token，强制下次登录重新扫码或获取新 Token。"""
        if self._account_file.exists():
            try:
                self._account_file.unlink()
                logger.info("🗑️ Saved account token invalidated/deleted.")
            except Exception as e:
                logger.error(f"Failed to delete account file: {e}")

    def load_account(self) -> WechatAccountData | None:
        """Load saved credentials."""
        if self._account_file.exists():
            try:
                data = json.loads(self._account_file.read_text())
                return WechatAccountData(**data)
            except Exception:
                return None
        return None

    def save_account(self, data: WechatAccountData):
        """Persist credentials."""
        self._account_file.write_text(json.dumps(data.__dict__, indent=2))
        logger.info(f"✅ Account saved to {self._account_file}")

    async def login(self) -> WechatAccountData | None:
        """
        Main login flow:
        1. Check local token (if valid).
        2. If missing/invalid, show QR and wait for scan.
        3. If QR expires, automatically fetch a new one.
        """
        # 1. Try local token first
        account = self.load_account()
        if account and account.token:
            logger.info(f"🔑 Found saved token for user {account.user_id}")
            self.client.token = account.token
            self.client.base_url = account.base_url
            return account

        # 2. QR Code Login Flow (Loop to handle QR expiration)
        logger.info("🚀 Starting WeChat login (QR Mode)...")
        
        while True:  # 外层循环：用于处理二维码过期自动刷新
            # Fetch QR
            try:
                qr_data = await self.client.fetch_qr_code()
                if qr_data.get("ret") != 0:
                    logger.error(f"❌ Failed to get QR code: {qr_data}")
                    await asyncio.sleep(5)
                    continue # 重试
            except Exception as e:
                logger.error(f"❌ Network error fetching QR: {e}")
                await asyncio.sleep(5)
                continue

            qrcode_str = qr_data.get("qrcode")
            qrcode_url = qr_data.get("qrcode_img_content") 
            
            if qrcode_url:
                QRDisplay.render(qrcode_url)
            elif qrcode_str:
                # 某些版本可能只返回字符串 ID
                print(f"🔐 QR Code ID: {qrcode_str}")
                print("⚠️ URL not available, might need manual handling.")
            else:
                logger.error("❌ Could not retrieve QR info from API response")
                await asyncio.sleep(5)
                continue

            # Poll for status
            logger.info("⏳ Waiting for scan...")
            while True:
                try:
                    status_data = await self.client.poll_qr_status(qrcode_str)
                    status = status_data.get("status", "wait")

                    if status == "confirmed":
                        logger.info("✅ Login confirmed!")
                        new_account = WechatAccountData(
                            token=status_data.get("bot_token"),
                            user_id=status_data.get("ilink_user_id"),
                            base_url=status_data.get("baseurl", self.client.base_url),
                            bot_id=status_data.get("ilink_bot_id"),
                            saved_at=time.strftime("%Y-%m-%d %H:%M:%S")
                        )
                        
                        self.client.token = new_account.token
                        self.client.base_url = new_account.base_url
                        
                        self.save_account(new_account)
                        return new_account
                    
                    elif status == "expired":
                        logger.warning("⏰ QR code expired. Automatically fetching a new one...")
                        break # 跳出内层 polling 循环，进入外层循环获取新二维码
                    
                    elif status == "scaned":
                        logger.info("👍 QR Scanned. Please confirm on phone...")
                    
                    await asyncio.sleep(2)
                except Exception as e:
                    logger.error(f"❌ Polling error: {e}")
                    await asyncio.sleep(2)
