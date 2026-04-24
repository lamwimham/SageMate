# -*- coding: utf-8 -*-
"""WeChat Service Layer — QR Login, Session Management, Account State.

Separates WeChat business logic from HTTP routing (app.py).
Provides clean interfaces for QR code generation, polling, and account management.
"""

from __future__ import annotations

import base64
import io
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .types import WechatAccountData
from .api import WechatApiClient
from .auth import WechatAuthenticator

logger = logging.getLogger(__name__)


class QRStatus(str, Enum):
    """QR code scan status."""
    WAIT = "wait"
    SCANED = "scaned"
    CONFIRMED = "confirmed"
    EXPIRED = "expired"


@dataclass
class QRSession:
    """Holds the state of an active QR login session."""
    qrcode_str: str = ""
    qr_img_base64: str = ""
    last_qrcode_str: str = ""


class WeChatService:
    """Manages WeChat login lifecycle: QR generation, polling, account persistence."""

    def __init__(self, api_client: WechatApiClient, auth: WechatAuthenticator):
        self.client = api_client
        self.auth = auth
        self._session = QRSession()

    # ── Account State ──────────────────────────────────────────

    def get_account(self) -> dict:
        """Return current account status."""
        account = self.auth.load_account()
        if account and account.token:
            return {
                "logged_in": True,
                "user_id": account.user_id,
                "bot_id": account.bot_id,
                "saved_at": account.saved_at,
            }
        return {"logged_in": False}

    def logout(self):
        """Clear saved account token."""
        self.auth.invalidate_account()
        self.client.token = None
        self._session = QRSession()

    # ── QR Code ────────────────────────────────────────────────

    async def fetch_qr(self) -> dict:
        """
        Fetch a new QR code from iLink API, generate PNG image, return base64.

        Returns:
            {"qrcode_str": str, "qr_img_base64": str} on success
        Raises:
            Exception on API failure
        """
        qr_data = await self.client.fetch_qr_code()
        if qr_data.get("ret") != 0:
            raise ValueError(f"API 返回错误: ret={qr_data.get('ret')}, msg={qr_data.get('errmsg', '')}")

        qrcode_str = qr_data.get("qrcode", "")
        qrcode_url = qr_data.get("qrcode_img_content", "")

        # Generate QR code image from the URL string
        qr_img_base64 = self._generate_qr_image(qrcode_url or qrcode_str)

        self._session = QRSession(
            qrcode_str=qrcode_str,
            qr_img_base64=qr_img_base64,
            last_qrcode_str=qrcode_str,
        )

        return {"qrcode_str": qrcode_str, "qr_img_base64": qr_img_base64}

    async def poll_qr(self) -> dict:
        """
        Poll current QR session status.

        Returns:
            {"status": "wait"|"scaned"|"confirmed"|"expired", ...}
        """
        qrcode_str = self._session.qrcode_str or self._session.last_qrcode_str
        if not qrcode_str:
            raise ValueError("没有活跃的二维码会话，请先调用 fetch_qr")

        status_data = await self.client.poll_qr_status(qrcode_str)
        status = status_data.get("status", "wait")

        if status == "confirmed":
            account = WechatAccountData(
                token=status_data.get("bot_token"),
                user_id=status_data.get("ilink_user_id"),
                base_url=status_data.get("baseurl", self.client.base_url),
                bot_id=status_data.get("ilink_bot_id"),
                saved_at=time.strftime("%Y-%m-%d %H:%M:%S"),
            )
            self.client.token = account.token
            self.client.base_url = account.base_url
            self.auth.save_account(account)
            self._session = QRSession()  # Clear session after success
            return {"status": "confirmed", "user_id": account.user_id}

        elif status == "expired":
            self._session.qrcode_str = ""  # Invalidate current QR, keep last for retry hint
            return {"status": "expired"}

        elif status == "scaned":
            return {"status": "scaned"}

        return {"status": status}

    # ── Internal Helpers ───────────────────────────────────────

    @staticmethod
    def _generate_qr_image(text: str) -> str:
        """
        Generate a QR code PNG from text, return as base64 data URI.

        Falls back to a minimal 1x1 transparent PNG if qrcode library unavailable.
        """
        if not text:
            return _TRANSPARENT_PNG

        try:
            import qrcode
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=2,
            )
            qr.add_data(text)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")

            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            return "data:image/png;base64," + base64.b64encode(buf.read()).decode()
        except ImportError:
            logger.warning("'qrcode' library not available, using fallback QR image")
            return _TRANSPARENT_PNG
        except Exception as e:
            logger.error(f"QR image generation failed: {e}")
            return _TRANSPARENT_PNG


# Fallback: 1x1 transparent PNG (tiny base64)
_TRANSPARENT_PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
