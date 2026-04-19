# -*- coding: utf-8 -*-
"""WeChat iLink API Client."""

from __future__ import annotations

import json
import logging
import secrets
import base64
from typing import Optional

import httpx

from .types import QRCodeResponse, QRStatusResponse
from .constants import (
    DEFAULT_BASE_URL, 
    SAGEMATE_CHANNEL_VERSION,
    DEFAULT_API_TIMEOUT_MS,
    DEFAULT_LONG_POLL_TIMEOUT_MS
)

logger = logging.getLogger(__name__)


class WechatApiClient:
    """Client for WeChat iLink Bot API."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        token: Optional[str] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.token = token
        
        # ⚠️ FIX 1: 固定 UIN (User Identification Number)
        # 之前每次发送都随机生成，容易被微信风控判定为异常。
        # 现在生成一次后在实例生命周期内保持不变。
        self.uin = secrets.randbits(32)
        
        # ⚠️ FIX 2: 设置合理的超时时间 (30秒)
        # 禁用 trust_env 防止本地 Socks5 代理拦截微信 API 请求导致 Hang
        self._client = httpx.AsyncClient(timeout=30.0, trust_env=False)

    # ------------------------------------------------------------------
    # Authentication Endpoints
    # ------------------------------------------------------------------

    async def fetch_qr_code(self, bot_type: str = "3") -> dict:
        """Get QR code for login. No auth required."""
        url = f"{self.base_url}/ilink/bot/get_bot_qrcode"
        params = {"bot_type": bot_type}
        try:
            resp = await self._client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            return data
        except Exception as e:
            logger.error(f"Failed to fetch QR code: {e}")
            raise

    async def poll_qr_status(self, qrcode: str) -> dict:
        """Poll QR code status."""
        url = f"{self.base_url}/ilink/bot/get_qrcode_status"
        params = {"qrcode": qrcode}
        headers = {"iLink-App-ClientVersion": "1"}
        try:
            resp = await self._client.get(url, params=params, headers=headers, timeout=40.0)
            if resp.status_code == 200:
                return resp.json()
            return {"status": "wait"}
        except httpx.TimeoutException:
            return {"status": "wait"}
        except Exception as e:
            logger.error(f"Poll QR error: {e}")
            raise

    async def get_updates(self, get_updates_buf: str = "") -> dict:
        """Long poll for new messages."""
        if not self.token:
            raise ValueError("Token required for get_updates")

        url = f"{self.base_url}/ilink/bot/getupdates"
        body = {
            "get_updates_buf": get_updates_buf,
            "base_info": {"channel_version": SAGEMATE_CHANNEL_VERSION},
        }
        
        headers = {
            "Authorization": f"Bearer {self.token}",
            "AuthorizationType": "ilink_bot_token",
            "Content-Type": "application/json",
        }

        try:
            resp = await self._client.post(url, json=body, headers=headers, timeout=40.0)
            resp.raise_for_status()
            data = resp.json()
            
            # 只有当有新消息时才打印详细日志，减少干扰
            if data.get("msgs"):
                logger.debug(f"📡 Raw Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
            
            return data
        except httpx.ReadTimeout:
            # Timeout is normal for long polling (35s), return empty
            logger.debug("⏳ Polling timeout (normal). Retrying...")
            return {"ret": 0, "msgs": []}
        except Exception as e:
            logger.error(f"Get updates error: {e}")
            raise

    async def get_config(self, ilink_user_id: str, context_token: Optional[str] = None) -> dict:
        """获取用户配置（包含 typing_ticket）"""
        url = f"{self.base_url}/ilink/bot/getconfig"
        body_dict = {
            "ilink_user_id": ilink_user_id,
            "base_info": {"channel_version": SAGEMATE_CHANNEL_VERSION}
        }
        if context_token:
            body_dict["context_token"] = context_token

        body_str = json.dumps(body_dict, ensure_ascii=False)
        headers = {
            "Authorization": f"Bearer {self.token}",
            "AuthorizationType": "ilink_bot_token",
            "Content-Type": "application/json",
            "Content-Length": str(len(body_str.encode("utf-8"))),
            "X-WECHAT-UIN": self._get_wechat_uin(),
            "iLink-App-Id": "bot",
            "iLink-App-ClientVersion": "65536",
        }

        try:
            resp = await self._client.post(url, content=body_str, headers=headers)
            return resp.json() if resp.status_code == 200 else {}
        except Exception as e:
            logger.error(f"Get config error: {e}")
            return {}

    async def send_typing(self, ilink_user_id: str, typing_ticket: str, status: int = 1) -> bool:
        """发送输入状态 (1=Typing, 2=Cancel)"""
        if not typing_ticket:
            return False
            
        url = f"{self.base_url}/ilink/bot/sendtyping"
        body_dict = {
            "ilink_user_id": ilink_user_id,
            "typing_ticket": typing_ticket,
            "status": status,
            "base_info": {"channel_version": SAGEMATE_CHANNEL_VERSION}
        }

        body_str = json.dumps(body_dict, ensure_ascii=False)
        headers = {
            "Authorization": f"Bearer {self.token}",
            "AuthorizationType": "ilink_bot_token",
            "Content-Type": "application/json",
            "Content-Length": str(len(body_str.encode("utf-8"))),
            "X-WECHAT-UIN": self._get_wechat_uin(),
            "iLink-App-Id": "bot",
            "iLink-App-ClientVersion": "65536",
        }

        try:
            resp = await self._client.post(url, content=body_str, headers=headers)
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Send typing error: {e}")
            return False

    async def download_file(self, encrypt_query_param: str, aes_key: Optional[str] = None) -> bytes:
        """Download a file from WeChat CDN and decrypt if necessary."""
        cdn_base_url = "https://novac2c.cdn.weixin.qq.com/c2c"
        import urllib.parse
        url = f"{cdn_base_url}/download?encrypted_query_param={urllib.parse.quote(encrypt_query_param, safe='')}"
        
        async with httpx.AsyncClient(trust_env=False) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            encrypted_data = resp.content

        # If file already looks like a known format, return as-is
        if encrypted_data.startswith(b'%PDF') or encrypted_data.startswith(b'PK\x03\x04'):
            logger.debug("✅ File already valid, no decryption needed.")
            return encrypted_data

        # Decrypt if AES key is provided
        if aes_key and len(encrypted_data) > 0:
            try:
                key = self._parse_aes_key(aes_key)
                decrypted = self._decrypt_aes_128_ecb_raw(encrypted_data, key)
                logger.info(f"✅ Decrypted {len(encrypted_data)} -> {len(decrypted)} bytes")
                return decrypted
            except Exception as e:
                logger.warning(f"⚠️ Decryption failed: {e}")
                logger.warning("⚠️ Returning raw CDN data (may be unencrypted).")
        
        return encrypted_data

    @staticmethod
    def _parse_aes_key(aes_key_str: str) -> bytes:
        """
        Parse AES key from multiple possible encodings.
        """
        if not aes_key_str:
            raise ValueError("aes_key is empty or None")
            
        print(f"  🔑 [PARSE] Input key (first 40 chars): {aes_key_str[:40]}")
        # Try 1: raw hex string (32 hex chars = 16 bytes)
        if len(aes_key_str) == 32 and all(c in '0123456789abcdefABCDEF' for c in aes_key_str):
            try:
                result = bytes.fromhex(aes_key_str)
                if len(result) == 16:
                    print(f"  🔑 Parsed as raw hex string -> {result.hex()}")
                    return result
            except Exception:
                pass

        # Try 2: base64 decode
        decoded = base64.b64decode(aes_key_str)
        
        # 2a: base64 -> raw 16 bytes
        if len(decoded) == 16:
            print(f"  🔑 Parsed as base64(raw 16) -> {decoded.hex()}")
            return decoded
        
        # 2b: base64 -> 32 ASCII hex chars -> parse as hex
        if len(decoded) == 32 and all(c in b'0123456789abcdefABCDEF' for c in decoded):
            result = bytes.fromhex(decoded.decode('ascii'))
            print(f"  🔑 Parsed as base64(hex 32) -> {result.hex()}")
            return result

        # 2c: Maybe the hex is longer/shorter? Try general hex decode
        try:
            hex_str = decoded.decode('ascii', errors='ignore')
            if len(hex_str) >= 32 and all(c in '0123456789abcdefABCDEF' for c in hex_str[:32]):
                result = bytes.fromhex(hex_str[:32])
                print(f"  🔑 Parsed as base64->hex(variant) -> {result.hex()}")
                return result
        except Exception:
            pass

        raise ValueError(
            f"aes_key cannot be parsed. Raw str len={len(aes_key_str)}, "
            f"b64decoded len={len(decoded)}, b64decoded hex={decoded[:16].hex()}"
        )

    @staticmethod
    def _decrypt_aes_128_ecb_raw(data: bytes, key: bytes) -> bytes:
        """Decrypt data using AES-128-ECB with PKCS7 unpadding (raw key bytes)."""
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import unpad
        
        cipher = AES.new(key, AES.MODE_ECB)
        decrypted = cipher.decrypt(data)
        return unpad(decrypted, AES.block_size)

    async def get_config(self, ilink_user_id: str, context_token: Optional[str] = None) -> dict:
        """获取用户配置（包含 typing_ticket）"""
        url = f"{self.base_url}/ilink/bot/getconfig"
        body_dict = {
            "ilink_user_id": ilink_user_id,
            "base_info": {"channel_version": SAGEMATE_CHANNEL_VERSION}
        }
        if context_token:
            body_dict["context_token"] = context_token

        body_str = json.dumps(body_dict, ensure_ascii=False)
        headers = {
            "Authorization": f"Bearer {self.token}",
            "AuthorizationType": "ilink_bot_token",
            "Content-Type": "application/json",
            "Content-Length": str(len(body_str.encode("utf-8"))),
            "X-WECHAT-UIN": self._get_wechat_uin(),
            "iLink-App-Id": "bot",
            "iLink-App-ClientVersion": "65536",
        }

        try:
            resp = await self._client.post(url, content=body_str, headers=headers)
            return resp.json() if resp.status_code == 200 else {}
        except Exception as e:
            logger.error(f"Get config error: {e}")
            return {}

    async def send_typing(self, ilink_user_id: str, typing_ticket: str, status: int = 1) -> bool:
        """发送输入状态 (1=Typing, 2=Cancel)"""
        if not typing_ticket:
            return False
            
        url = f"{self.base_url}/ilink/bot/sendtyping"
        body_dict = {
            "ilink_user_id": ilink_user_id,
            "typing_ticket": typing_ticket,
            "status": status,
            "base_info": {"channel_version": SAGEMATE_CHANNEL_VERSION}
        }

        body_str = json.dumps(body_dict, ensure_ascii=False)
        headers = {
            "Authorization": f"Bearer {self.token}",
            "AuthorizationType": "ilink_bot_token",
            "Content-Type": "application/json",
            "Content-Length": str(len(body_str.encode("utf-8"))),
            "X-WECHAT-UIN": self._get_wechat_uin(),
            "iLink-App-Id": "bot",
            "iLink-App-ClientVersion": "65536",
        }

        try:
            resp = await self._client.post(url, content=body_str, headers=headers)
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Send typing error: {e}")
            return False

    async def send_message(self, to_user_id: str, text: str, context_token: Optional[str] = None) -> bool:
        """Send a text message."""
        if not self.token:
            raise ValueError("Token required")

        url = f"{self.base_url}/ilink/bot/sendmessage"
        
        # 1. Generate a NEW client_id for the outgoing message (do not reuse incoming client_id)
        # Format: sagemate-wechat:timestamp-random
        import time
        import secrets
        new_client_id = f"sagemate-wechat:{int(time.time() * 1000)}-{secrets.token_hex(4)}"
        
        # 2. Build the payload exactly matching openclaw-weixin structure
        body_dict = {
            "msg": {
                "from_user_id": "",  # Must be empty for bot messages
                "to_user_id": to_user_id,
                "client_id": new_client_id,
                "message_type": 2,  # BOT
                "message_state": 2, # FINISH
                "item_list": [
                    {"type": 1, "text_item": {"text": text}}
                ],
            },
            "base_info": {"channel_version": SAGEMATE_CHANNEL_VERSION}
        }
        
        if context_token:
            body_dict["msg"]["context_token"] = context_token

        # 3. Build Headers exactly matching openclaw-weixin
        body_str = json.dumps(body_dict, ensure_ascii=False)
        
        # Calculate ClientVersion: 1.0.0 -> 65536
        # ((major & 0xff) << 16) | ((minor & 0xff) << 8) | (patch & 0xff)
        client_version_int = 65536 
        
        headers = {
            "Authorization": f"Bearer {self.token}",
            "AuthorizationType": "ilink_bot_token",
            "Content-Type": "application/json",
            "Content-Length": str(len(body_str.encode("utf-8"))),
            "X-WECHAT-UIN": self._get_wechat_uin(),
            # CRITICAL: These headers were missing and likely causing silent drops!
            "iLink-App-Id": "bot",
            "iLink-App-ClientVersion": str(client_version_int),
        }

        try:
            print(f"\n🔥 [SEND_REQ] URL: {url}")
            print(f"🔥 [SEND_REQ] client_id: {new_client_id}")
            print(f"🔥 [SEND_REQ] Payload: {body_str}")
            
            resp = await self._client.post(url, content=body_str, headers=headers)
            
            print(f"🔥 [SEND_RES] Status: {resp.status_code}")
            print(f"🔥 [SEND_RES] Body: {resp.text[:300]}\n")
            
            if resp.status_code != 200:
                logger.error(f"❌ HTTP Error: {resp.status_code}")
                return False
            
            try:
                data = resp.json()
                ret_code = data.get("ret", 0)
                if ret_code != 0:
                    logger.error(f"❌ API Logic Error: ret={ret_code}, msg={data.get('errmsg')}")
                    return False
            except ValueError:
                logger.error("❌ Invalid API Response (Not JSON)")
                return False

            logger.info("✅ Message sent successfully!")
            return True
            
        except httpx.TimeoutException:
            print("❌ [SEND_ERR] Send Timeout")
            logger.error("❌ Send Timeout: Request took too long.")
            return False
        except Exception as e:
            print(f"❌ [SEND_ERR] {e}")
            logger.error(f"❌ Send Exception: {e}")
            return False

    def _get_wechat_uin(self) -> str:
        """Return the stable UIN for this client session."""
        return base64.b64encode(str(self.uin).encode()).decode()
