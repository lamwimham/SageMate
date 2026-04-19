# -*- coding: utf-8 -*-
"""WeChat iLink API Constants."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Channel Versioning
# ---------------------------------------------------------------------------

# SageMate WeChat Plugin Version
# Format: {project}-{channel}-{major}.{minor}.{patch}
SAGEMATE_CHANNEL_VERSION = "sagemate-wechat-1.0.0"

# Default API Base URL
DEFAULT_BASE_URL = "https://ilinkai.weixin.qq.com"
CDN_BASE_URL = "https://novac2c.cdn.weixin.qq.com/c2c"

# Timeouts
DEFAULT_LONG_POLL_TIMEOUT_MS = 35000
DEFAULT_API_TIMEOUT_MS = 15000
DEFAULT_CONFIG_TIMEOUT_MS = 10000
