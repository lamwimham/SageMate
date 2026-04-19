# -*- coding: utf-8 -*-
"""WeChat iLink API Data Types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Authentication Types
# ---------------------------------------------------------------------------


@dataclass
class QRCodeResponse:
    """Response from get_bot_qrcode."""

    ret: int = 0
    qrcode: str = ""
    qrcode_img_content: str = ""  # Base64 image data or URL depending on implementation


@dataclass
class QRStatusResponse:
    """Response from get_qrcode_status."""

    status: str = "wait"  # wait | scaned | confirmed | expired
    bot_token: Optional[str] = None
    ilink_bot_id: Optional[str] = None
    base_url: Optional[str] = None
    ilink_user_id: Optional[str] = None
    ret: int = 0
    msg: str = ""


# ---------------------------------------------------------------------------
# Account Token Storage
# ---------------------------------------------------------------------------


@dataclass
class WechatAccountData:
    """Credentials stored locally."""

    token: str = ""
    user_id: str = ""
    base_url: str = "https://ilinkai.weixin.qq.com"
    bot_id: str = ""
    saved_at: str = ""
