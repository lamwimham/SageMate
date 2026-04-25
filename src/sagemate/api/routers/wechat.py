"""WeChat Router — 微信插件 API

拆分自 app.py，独立管理微信相关的路由：
- QR 码登录
- 登录状态轮询
- 登出
- 账号信息查询
"""

from fastapi import APIRouter, HTTPException
import asyncio

from ..dependencies import WechatServiceDep, WechatChannelDep

router = APIRouter(prefix="/api/v1/wechat", tags=["WeChat"])


@router.post("/qr", response_model=dict)
async def wechat_fetch_qr(wechat_service: WechatServiceDep):
    """Fetch WeChat login QR code via service layer."""
    try:
        result = await wechat_service.fetch_qr()
        return {"success": True, **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"网络错误: {e}")


@router.post("/qr/poll", response_model=dict)
async def wechat_poll_qr(
    wechat_service: WechatServiceDep,
    wechat_channel: WechatChannelDep,
):
    """Poll WeChat QR login status via service layer."""
    try:
        result = await wechat_service.poll_qr()
        # On successful login, start the channel polling loop
        if result.get("status") == "confirmed":
            asyncio.create_task(wechat_channel.start())
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@router.post("/logout", response_model=dict)
async def wechat_logout(
    wechat_service: WechatServiceDep,
    wechat_channel: WechatChannelDep,
):
    """Log out of WeChat via service layer."""
    wechat_service.logout()
    wechat_channel._running = False  # Reset guard for next start
    return {"success": True}


@router.post("/start", response_model=dict)
async def wechat_start(wechat_channel: WechatChannelDep):
    """Manually start the WeChat Channel (e.g. after saving a token)."""
    if wechat_channel._running:
        return {"success": False, "detail": "Channel is already running"}
    asyncio.create_task(wechat_channel.start())
    return {"success": True, "detail": "Channel starting..."}


@router.get("/status", response_model=dict)
async def wechat_status(
    wechat_channel: WechatChannelDep,
    wechat_service: WechatServiceDep,
):
    """Get WeChat Channel runtime status."""
    return {
        "running": wechat_channel._running,
        "logged_in": wechat_service.account.logged_in if wechat_service.account else False,
    }


@router.get("/account", response_model=dict)
async def wechat_account(wechat_service: WechatServiceDep):
    """Get current WeChat account status via service layer."""
    return wechat_service.get_account()
