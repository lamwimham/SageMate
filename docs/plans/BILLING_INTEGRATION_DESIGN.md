# SageMate 付费体系集成设计文档

> 对接 `sage-billing`（Go 微服务）与 `sagemate-core`（Python FastAPI），在 Web UI 上提供完整的购买、激活、管理闭环。  
> 核心原则：**sagemate-core 作为 billing 代理层**，前端不直连 billing 服务，license 状态本地缓存 + 离线可用。

---

## 一、架构总览

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              用户层（前端）                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ 顶部 License │  │ 设置页       │  │ 升级弹窗     │  │ 支付结果页   │    │
│  │ 状态指示器   │  │ License 分组 │  │ 产品列表     │  │ 成功/失败    │    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘    │
│         │                 │                 │                 │            │
│         └─────────────────┴─────────────────┴─────────────────┘            │
│                                    │                                        │
│                          HTTP (sagemate-core:8000)                         │
└────────────────────────────────────┼────────────────────────────────────────┘
                                     │
┌────────────────────────────────────┼────────────────────────────────────────┐
│                         sagemate-core (Python)                             │
│                                    │                                        │
│  ┌─────────────────────────────────┼────────────────────────────────────┐   │
│  │     License Proxy Layer         │                                    │   │
│  │  ┌────────────┐  ┌────────────┐ │  ┌────────────┐                    │   │
│  │  │ 本地缓存    │  │ 启动验证    │ │  │ Feature    │                    │   │
│  │  │ cache.json │  │ Verify     │ │  │ Gate       │                    │   │
│  │  └────────────┘  └────────────┘ │  │ Middleware │                    │   │
│  └─────────────────────────────────┼────────────────────────────────────┘   │
│                                    │                                        │
│  新增 API 路由：                    │                                        │
│  ├── GET    /api/v1/license        │                                        │
│  ├── POST   /api/v1/license/activate                                     │   │
│  ├── POST   /api/v1/license/deactivate                                   │   │
│  ├── GET    /api/v1/products       │                                        │
│  ├── POST   /api/v1/orders         │                                        │
│  ├── POST   /api/v1/orders/pay     │                                        │
│  └── GET    /api/v1/orders/:id     │                                        │
│                                    │                                        │
│  现有 API 受 Feature Gate 保护：    │                                        │
│  ├── POST   /api/v1/ingest  ───────┼──────► 检查 license  tier            │   │
│  ├── POST   /api/v1/query  ────────┼──────► 检查 license  tier            │   │
│  └── POST   /api/v1/projects       │        检查 project 配额             │   │
│                                    │                                        │
└────────────────────────────────────┼────────────────────────────────────────┘
                                     │
                          HTTP (sage-billing:8082)
                                     │
┌────────────────────────────────────┼────────────────────────────────────────┐
│                         sage-billing (Go)                                  │
│                                    │                                        │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐          │
│  │ /verify    │  │ /activate  │  │ /orders    │  │ /products  │          │
│  │ /deactivate│  │ /callbacks │  │ /pay       │  │ /admin/*   │          │
│  └────────────┘  └────────────┘  └────────────┘  └────────────┘          │
│                                    │                                        │
│  SQLite: products, licenses, orders, audit_logs                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、sagemate-core 后端设计

### 2.1 新增配置项

**文件**：`src/sagemate/core/config.py`

```python
class Settings(BaseModel):
    # ... 现有配置 ...
    
    # ── License / Billing ────────────────────────────────────
    license_key: str = Field(default_factory=lambda: os.getenv("SAGEMATE_LICENSE_KEY", ""))
    billing_server_url: str = Field(default_factory=lambda: os.getenv("SAGEMATE_BILLING_URL", "http://localhost:8082"))
    billing_offline_grace_days: int = Field(default=7)  # 离线宽限天数
    
    # ── Feature Limits (fallback when billing unreachable) ───
    free_max_projects: int = Field(default=1)
    free_max_compiles_per_day: int = Field(default=5)
    free_max_queries_per_day: int = Field(default=20)
    std_max_projects: int = Field(default=3)
    pro_max_projects: int = Field(default=999)
```

### 2.2 License 服务层

**文件**：`src/sagemate/core/license_service.py`

```python
"""
License Service — 封装与 sage-billing 的交互。
职责：
1. 启动时验证 license
2. 本地缓存验证结果（支持离线使用）
3. 提供 feature flag 查询
4. 代理前端请求到 sage-billing
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LicenseTier:
    """Feature tier derived from license plan."""
    name: str           # "free" | "std" | "pro"
    max_projects: int
    max_compiles_per_day: int
    max_queries_per_day: int
    max_file_size_bytes: int   # 单次编译文件大小上限
    allow_obsidian_sync: bool
    allow_batch_ingest: bool
    allow_advanced_lint: bool


class LicenseService:
    """
    Manages license verification, caching, and feature gating.
    
    Offline strategy:
    - On startup: verify with billing server, cache result
    - During runtime: serve from cache
    - If cache expired and server unreachable: enter grace period (configurable days)
    - If grace expired: degrade to free tier
    """
    
    # max_file_size_bytes: Free 5MB, Std 20MB, Pro 100MB
    TIER_FREE = LicenseTier("free", 1, 5, 20, 5 * 1024 * 1024, False, False, False)
    TIER_STD = LicenseTier("std", 3, 50, 200, 20 * 1024 * 1024, True, False, False)
    TIER_PRO = LicenseTier("pro", 999, 9999, 9999, 100 * 1024 * 1024, True, True, True)
    
    PLAN_TO_TIER = {
        "": "free",           # No license key
        "std": "std",
        "pro": "pro",
        "sub_monthly": "pro",
        "sub_yearly": "pro",
    }
    
    def __init__(self, license_key: str, billing_url: str, data_dir: Path, 
                 grace_days: int = 7):
        self.license_key = license_key
        self.billing_url = billing_url.rstrip("/")
        self.cache_path = data_dir / "license_cache.json"
        self.grace_days = grace_days
        self._http = httpx.AsyncClient(timeout=10.0)
        
        # Runtime state
        self._cached_result: Optional[dict] = None
        self._cached_at: Optional[datetime] = None
        self._server_status: str = "unknown"  # active | inactive | expired | grace
        self._expires_at: Optional[datetime] = None
    
    async def initialize(self):
        """Called on app startup. Verify license and load cache."""
        # Try to load existing cache first
        self._load_cache()
        
        if not self.license_key:
            self._server_status = "free"
            logger.info("[License] No license key configured, running in free mode")
            return
        
        # Attempt server verification
        try:
            result = await self._verify_with_server()
            self._update_cache(result)
            logger.info(f"[License] Verified: {result.get('status', 'unknown')}")
        except Exception as e:
            logger.warning(f"[License] Server unreachable: {e}, using cache/grace period")
            self._apply_offline_fallback()
    
    async def _verify_with_server(self) -> dict:
        """Call sage-billing /api/v1/verify."""
        device_id = self._get_device_id()
        resp = await self._http.post(
            f"{self.billing_url}/api/v1/verify",
            json={"license_key": self.license_key, "device_id": device_id},
        )
        resp.raise_for_status()
        return resp.json()
    
    async def activate(self) -> dict:
        """Activate license on this device."""
        device_id = self._get_device_id()
        resp = await self._http.post(
            f"{self.billing_url}/api/v1/activate",
            json={"license_key": self.license_key, "device_id": device_id},
        )
        resp.raise_for_status()
        result = resp.json()
        self._update_cache(await self._verify_with_server())
        return result
    
    async def deactivate(self) -> dict:
        """Deactivate license on this device."""
        device_id = self._get_device_id()
        resp = await self._http.post(
            f"{self.billing_url}/api/v1/deactivate",
            json={"license_key": self.license_key, "device_id": device_id},
        )
        resp.raise_for_status()
        self._clear_cache()
        return resp.json()
    
    # ── Feature Gating ───────────────────────────────────────
    
    def current_tier(self) -> LicenseTier:
        """Return current feature tier."""
        if self._server_status in ("free", "unknown"):
            return self.TIER_FREE
        
        plan = (self._cached_result or {}).get("plan", "")
        tier_name = self.PLAN_TO_TIER.get(plan, "free")
        return getattr(self, f"TIER_{tier_name.upper()}", self.TIER_FREE)
    
    def is_feature_allowed(self, feature: str) -> bool:
        """Check if a feature is allowed in current tier."""
        tier = self.current_tier()
        feature_map = {
            "multiple_projects": tier.max_projects > 1,
            "obsidian_sync": tier.allow_obsidian_sync,
            "batch_ingest": tier.allow_batch_ingest,
            "advanced_lint": tier.allow_advanced_lint,
            "unlimited_queries": tier.max_queries_per_day >= 9999,
        }
        return feature_map.get(feature, False)
    
    def check_file_size(self, size_bytes: int) -> tuple[bool, str]:
        """Check if a file size is within the tier limit."""
        tier = self.current_tier()
        if size_bytes > tier.max_file_size_bytes:
            mb = tier.max_file_size_bytes / (1024 * 1024)
            return False, f"文件大小 {size_bytes / (1024 * 1024):.1f} MB 超出当前套餐限制（{mb:.0f} MB）。升级 Pro 可支持最大 100 MB 文件。"
        return True, ""
    
    def check_quota(self, action: str, today_count: int) -> tuple[bool, str]:
        """Check if user has quota remaining for an action."""
        tier = self.current_tier()
        limits = {
            "compile": tier.max_compiles_per_day,
            "query": tier.max_queries_per_day,
        }
        limit = limits.get(action)
        if limit is None:
            return True, ""
        if today_count >= limit:
            return False, f"今日 {action} 次数已用完（{limit}/{limit}）。升级 Pro 解锁无限次数。"
        return True, ""
    
    # ── Cache Management ─────────────────────────────────────
    
    def _load_cache(self):
        """Load verification result from local file."""
        try:
            if self.cache_path.exists():
                data = json.loads(self.cache_path.read_text())
                self._cached_result = data.get("result")
                self._cached_at = datetime.fromisoformat(data["cached_at"])
                self._server_status = data.get("status", "unknown")
        except Exception:
            pass
    
    def _update_cache(self, result: dict):
        """Save successful verification to local file."""
        self._cached_result = result
        self._cached_at = datetime.now()
        self._server_status = result.get("status", "unknown")
        if result.get("expires_at"):
            self._expires_at = datetime.fromisoformat(result["expires_at"])
        
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps({
            "result": result,
            "cached_at": self._cached_at.isoformat(),
            "status": self._server_status,
        }))
    
    def _apply_offline_fallback(self):
        """When server is unreachable, use cache or enter grace period."""
        if self._cached_result and self._cached_at:
            elapsed = datetime.now() - self._cached_at
            if elapsed <= timedelta(days=self.grace_days):
                self._server_status = "grace"
                logger.info(f"[License] Offline grace period active ({elapsed.days}d elapsed)")
                return
        
        self._server_status = "free"
        logger.warning("[License] Grace period expired, degraded to free tier")
    
    def _clear_cache(self):
        """Clear local cache (on deactivation)."""
        self._cached_result = None
        self._cached_at = None
        self._server_status = "inactive"
        if self.cache_path.exists():
            self.cache_path.unlink()
    
    def _get_device_id(self) -> str:
        """Generate a stable device identifier."""
        # Use machine-specific info: hostname + user + hardware UUID
        import platform
        import getpass
        import hashlib
        raw = f"{platform.node()}-{getpass.getuser()}-{platform.machine()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]
    
    def to_dict(self) -> dict:
        """Serialize current state for API response."""
        tier = self.current_tier()
        return {
            "status": self._server_status,
            "tier": tier.name,
            "license_key": self.license_key[:8] + "****" if self.license_key else "",
            "expires_at": self._expires_at.isoformat() if self._expires_at else None,
            "is_offline": self._server_status == "grace",
            "features": {
                "max_projects": tier.max_projects,
                "max_compiles_per_day": tier.max_compiles_per_day,
                "max_queries_per_day": tier.max_queries_per_day,
                "obsidian_sync": tier.allow_obsidian_sync,
                "batch_ingest": tier.allow_batch_ingest,
                "advanced_lint": tier.allow_advanced_lint,
            },
            "quotas": {
                "projects_used": 0,  # Populated by caller
                "compiles_today": 0,
                "queries_today": 0,
            }
        }
```

### 2.3 API 路由层

**文件**：`src/sagemate/api/app.py`（新增路由）

```python
# ── License / Billing API ──────────────────────────────────

@app.get("/api/v1/license", tags=["Billing"], response_model=dict)
async def get_license_status():
    """Return current license status and feature flags."""
    # Populate usage stats
    result = license_service.to_dict()
    result["quotas"]["projects_used"] = len(await store.list_projects())
    # TODO: track compiles_today and queries_today in a daily counter
    return {"license": result}


@app.post("/api/v1/license/activate", tags=["Billing"], response_model=dict)
async def activate_license(payload: dict):
    """Activate a license key on this device."""
    key = payload.get("license_key", "").strip()
    if not key:
        raise HTTPException(status_code=400, detail="License key is required")
    
    # Update the service's license key
    license_service.license_key = key
    try:
        result = await license_service.activate()
        return {"success": True, "message": result.get("message", "Activated")}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/v1/license/deactivate", tags=["Billing"], response_model=dict)
async def deactivate_license():
    """Deactivate license on this device."""
    if not license_service.license_key:
        raise HTTPException(status_code=400, detail="No active license")
    try:
        result = await license_service.deactivate()
        return {"success": True, "message": result.get("message", "Deactivated")}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/v1/products", tags=["Billing"], response_model=dict)
async def list_products():
    """Proxy product list from billing server."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{settings.billing_server_url}/api/v1/admin/products")
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        # Fallback: return hardcoded products if billing unreachable
        return {
            "products": [
                {"code": "std", "name": "SageMate Standard", "price": 6800, "validity": "lifetime"},
                {"code": "pro", "name": "SageMate Pro", "price": 12800, "validity": "lifetime"},
                {"code": "sub_monthly", "name": "AI Subscription (Monthly)", "price": 1500, "validity": "monthly"},
                {"code": "sub_yearly", "name": "AI Subscription (Yearly)", "price": 15000, "validity": "yearly"},
            ]
        }


@app.post("/api/v1/orders", tags=["Billing"], response_model=dict)
async def create_order(payload: dict):
    """Proxy order creation to billing server."""
    product_code = payload.get("product_code", "")
    if not product_code:
        raise HTTPException(status_code=400, detail="product_code is required")
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{settings.billing_server_url}/api/v1/orders",
                json={"product_code": product_code}
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Billing service error: {e}")


@app.post("/api/v1/orders/pay", tags=["Billing"], response_model=dict)
async def get_payment_url(payload: dict):
    """Proxy payment URL generation to billing server."""
    out_trade_no = payload.get("out_trade_no", "")
    provider = payload.get("provider", "")
    if not out_trade_no or not provider:
        raise HTTPException(status_code=400, detail="out_trade_no and provider are required")
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{settings.billing_server_url}/api/v1/orders/pay",
                json={"out_trade_no": out_trade_no, "provider": provider}
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Billing service error: {e}")


@app.get("/api/v1/orders/{out_trade_no}", tags=["Billing"], response_model=dict)
async def get_order_status(out_trade_no: str):
    """Proxy order status query to billing server."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{settings.billing_server_url}/api/v1/orders/{out_trade_no}"
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Billing service error: {e}")
```

### 2.4 Feature Gate 中间件

**文件**：`src/sagemate/api/middleware/license_gate.py`

```python
"""
License Gate Middleware — Enforce feature limits per tier.

Applied selectively to high-value endpoints:
- /api/v1/ingest (compile)
- /api/v1/query
- /api/v1/projects (create)
- /api/v1/obsidian/* (if implemented)
"""

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import logging

logger = logging.getLogger(__name__)

# Endpoint → action type mapping
ENDPOINT_LIMITS = {
    "/api/v1/ingest": "compile",
    "/api/v1/query": "query",
}

# Endpoints that require at least std tier
STD_ENDPOINTS = [
    # "/api/v1/obsidian/query",  # When obsidian feature is added
]


class LicenseGateMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method
        
        # Skip non-mutating methods
        if method not in ("POST", "PUT", "PATCH", "DELETE"):
            return await call_next(request)
        
        # Check endpoint-specific limits
        for prefix, action in ENDPOINT_LIMITS.items():
            if path.startswith(prefix):
                # TODO: look up today's usage count from a daily counter
                # For now, allow all and track for display
                break
        
        # Check tier-gated endpoints
        for gated in STD_ENDPOINTS:
            if path.startswith(gated):
                from ...api.app import license_service
                if license_service.current_tier().name == "free":
                    raise HTTPException(
                        status_code=403,
                        detail="This feature requires Standard or Pro license. Please upgrade."
                    )
        
        return await call_next(request)
```

### 2.5 启动时初始化

**文件**：`src/sagemate/api/app.py`（在 lifespan 中初始化）

```python
from ..core.license_service import LicenseService

# Global instance
license_service: Optional[LicenseService] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... existing init ...
    
    global license_service
    license_service = LicenseService(
        license_key=settings.license_key,
        billing_url=settings.billing_server_url,
        data_dir=settings.data_dir,
        grace_days=settings.billing_offline_grace_days,
    )
    await license_service.initialize()
    
    yield
    
    # ... existing cleanup ...
```

---

## 三、前端设计

### 3.1 数据模型扩展

**文件**：`frontend/src/types/license.ts`（新建）

```typescript
export interface LicenseStatus {
  status: 'free' | 'active' | 'inactive' | 'expired' | 'grace'
  tier: 'free' | 'std' | 'pro'
  license_key: string      // Masked, e.g. "SM-PRO****"
  expires_at: string | null
  is_offline: boolean
  features: {
    max_projects: number
    max_compiles_per_day: number
    max_queries_per_day: number
    max_file_size_mb: number
    obsidian_sync: boolean
    batch_ingest: boolean
    advanced_lint: boolean
  }
  quotas: {
    projects_used: number
    compiles_today: number
    queries_today: number
  }
}

export interface Product {
  code: string
  name: string
  price: number        // in cents
  validity: 'lifetime' | 'monthly' | 'yearly'
  description?: string
}

export interface Order {
  out_trade_no: string
  license_key: string
  amount: number
  currency: string
  status: 'pending' | 'paid' | 'cancelled'
}

export interface PaymentURLResponse {
  payment_url: string
  provider: 'wechat' | 'alipay'
}
```

### 3.2 API 仓库层

**文件**：`frontend/src/api/repositories/license.ts`（新建）

```typescript
import { apiClient } from '../client'
import type { LicenseStatus, Product, Order, PaymentURLResponse } from '@/types/license'

export const licenseRepo = {
  // License status
  getStatus: () => apiClient.get<{ license: LicenseStatus }>('/api/v1/license'),
  
  // Activate a license key
  activate: (licenseKey: string) =>
    apiClient.post<{ success: boolean; message: string }>('/api/v1/license/activate', { license_key: licenseKey }),
  
  // Deactivate current license
  deactivate: () =>
    apiClient.post<{ success: boolean; message: string }>('/api/v1/license/deactivate'),
  
  // Products
  listProducts: () => apiClient.get<{ products: Product[] }>('/api/v1/products'),
  
  // Orders
  createOrder: (productCode: string) =>
    apiClient.post<{ order: Order; message: string }>('/api/v1/orders', { product_code: productCode }),
  
  getPaymentURL: (outTradeNo: string, provider: 'wechat' | 'alipay') =>
    apiClient.post<PaymentURLResponse>('/api/v1/orders/pay', { out_trade_no: outTradeNo, provider }),
  
  getOrderStatus: (outTradeNo: string) =>
    apiClient.get<{ order: Order }>(`/api/v1/orders/${outTradeNo}`),
}
```

### 3.3 React Query Hooks

**文件**：`frontend/src/hooks/useLicense.ts`（新建）

```typescript
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { licenseRepo } from '@/api/repositories/license'
import { useState, useEffect, useCallback } from 'react'

export function useLicenseStatus() {
  return useQuery({
    queryKey: ['license'],
    queryFn: () => licenseRepo.getStatus(),
    refetchInterval: 5 * 60 * 1000, // Refetch every 5 minutes
  })
}

export function useActivateLicense() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (licenseKey: string) => licenseRepo.activate(licenseKey),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['license'] }),
  })
}

export function useDeactivateLicense() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => licenseRepo.deactivate(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['license'] }),
  })
}

export function useProducts() {
  return useQuery({
    queryKey: ['products'],
    queryFn: () => licenseRepo.listProducts(),
    staleTime: 60 * 60 * 1000, // Products rarely change
  })
}

export function useCreateOrder() {
  return useMutation({
    mutationFn: (productCode: string) => licenseRepo.createOrder(productCode),
  })
}

export function usePaymentURL() {
  return useMutation({
    mutationFn: ({ outTradeNo, provider }: { outTradeNo: string; provider: 'wechat' | 'alipay' }) =>
      licenseRepo.getPaymentURL(outTradeNo, provider),
  })
}

// ── Payment polling hook ──────────────────────────────────

export function usePollOrderStatus(outTradeNo: string | null, intervalMs = 3000) {
  const [order, setOrder] = useState<any>(null)
  const [isPolling, setIsPolling] = useState(false)

  const startPolling = useCallback(() => {
    if (!outTradeNo) return
    setIsPolling(true)
  }, [outTradeNo])

  const stopPolling = useCallback(() => {
    setIsPolling(false)
  }, [])

  useEffect(() => {
    if (!isPolling || !outTradeNo) return

    const poll = async () => {
      try {
        const result = await licenseRepo.getOrderStatus(outTradeNo)
        setOrder(result)
        if (result.order?.status === 'paid') {
          setIsPolling(false)
        }
      } catch (e) {
        // Continue polling on error
      }
    }

    poll() // Immediate first check
    const id = setInterval(poll, intervalMs)
    return () => clearInterval(id)
  }, [isPolling, outTradeNo, intervalMs])

  return { order, isPolling, startPolling, stopPolling }
}
```

### 3.4 UI 组件设计

#### 3.4.1 顶部 License 状态指示器

**文件**：`frontend/src/components/layout/LicenseBadge.tsx`（新建）

位置：顶部导航栏右侧，与主题切换按钮并排。

```
┌─────────────────────────────────────────────────────────────┐
│  SageMate                                    [🌙] [Free ▼] │
│                                               或 [Pro ✓]   │
└─────────────────────────────────────────────────────────────┘
```

状态映射：

| Tier | 显示文本 | 颜色 | 点击行为 |
|------|---------|------|---------|
| free | "Free" | 灰色 | 打开 Upgrade Modal |
| std | "Standard" | 蓝色 | 打开 License Detail Modal |
| pro | "Pro" | 紫色/金色 | 打开 License Detail Modal |
| grace | "Pro (Offline)" | 橙色 | 提示网络问题，提供刷新按钮 |
| expired | "Expired" | 红色 | 打开 Upgrade Modal |

#### 3.4.2 License Detail Modal

```
┌─────────────────────────────────────────┐
│  License Status                    [×]  │
├─────────────────────────────────────────┤
│                                         │
│  ┌─────────────────────────────────┐   │
│  │  🏆 Pro Plan                     │   │
│  │  Status: Active ✓               │   │
│  │  Key: SM-PRO-****-****          │   │
│  │  Expires: 2027-04-25            │   │
│  └─────────────────────────────────┘   │
│                                         │
│  Features:                              │
│  ✓ Unlimited Projects                   │
│  ✓ Unlimited Compiles                   │
│  ✓ Obsidian Sync                        │
│  ✓ Batch Ingest                         │
│                                         │
│  Usage:                                 │
│  Projects: 2 / ∞                        │
│  Compiles today: 12 / ∞                 │
│  Queries today: 45 / ∞                  │
│                                         │
│  [Deactivate on this device]            │
│                                         │
└─────────────────────────────────────────┘
```

#### 3.4.3 Upgrade Modal（产品列表 + 支付）

```
┌─────────────────────────────────────────┐
│  Upgrade SageMate                  [×]  │
├─────────────────────────────────────────┤
│                                         │
│  ┌────────────┐  ┌────────────┐        │
│  │  Standard  │  │    Pro     │        │
│  │   ¥68      │  │   ¥128     │        │
│  │  买断制    │  │  买断制    │        │
│  │            │  │            │        │
│  │ • 3 Projects│  │ • ∞ Projects│       │
│  │ • 50 编译/天│  │ • 无限编译  │        │
│  │ • 200 查询/天│ │ • 无限查询  │        │
│  │            │  │ • Obsidian  │        │
│  │            │  │ • 批量摄入  │        │
│  │ [选择]     │  │ [选择]     │        │
│  └────────────┘  └────────────┘        │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │  AI Subscription                │   │
│  │  ¥15/月 或 ¥150/年             │   │
│  │  等同于 Pro 的全部功能          │   │
│  │  [选择月付]  [选择年付]         │   │
│  └─────────────────────────────────┘   │
│                                         │
└─────────────────────────────────────────┘
```

选择产品后 → 创建订单 → 显示支付方式选择：

```
┌─────────────────────────────────────────┐
│  Payment                             [×]│
├─────────────────────────────────────────┤
│                                         │
│  Order: #SM-20260425-xxx                │
│  Amount: ¥128.00                        │
│                                         │
│  [微信支付]  [支付宝]                   │
│                                         │
│  （选择后显示二维码或跳转支付页）        │
│                                         │
│  Waiting for payment...                 │
│                                         │
└─────────────────────────────────────────┘
```

支付成功后 → 自动激活 → 刷新 license 状态 → 显示成功提示。

#### 3.4.4 设置页面 License 分组

**文件**：`frontend/src/views/Settings.tsx`（扩展 `SETTING_GROUPS`）

```typescript
// 在 SETTING_GROUPS 数组末尾新增：
{
  key: 'license',
  label: '授权',
  icon: <KeyIcon />,
  sections: [
    { key: 'status', label: '授权状态', icon: <ShieldIcon />, fields: [] },
    { key: 'activate', label: '激活', icon: <KeyIcon />, fields: [] },
  ],
}
```

**License Status Section**：
- 当前 tier 卡片（Free/Standard/Pro）
- 功能清单（带 ✓ / ✗）
- 用量统计条

**Activate Section**：
- License Key 输入框
- [激活] 按钮
- 已有 license 时显示 [解绑此设备] 按钮

#### 3.4.5 免费用户的功能限制提示

当免费用户触发限制时：

```
┌─────────────────────────────────────────┐
│  ⚠️ Free Plan Limit Reached             │
│                                         │
│  今日编译次数已用完（5/5）。              │
│                                         │
│  升级 Standard 解锁 50 次/天            │
│  升级 Pro 解锁无限次数                  │
│                                         │
│  [升级]              [知道了]           │
└─────────────────────────────────────────┘
```

出现在：
- Ingest 面板点击"编译"时（如果今日已达上限）
- 创建第 2 个 Project 时
- 调用 Obsidian 相关 API 时（如果 tier 不支持）

---

## 四、Feature Gate 策略矩阵

| 功能 | Free | Standard | Pro |
|------|------|----------|-----|
| **Projects** | 1 | 3 | 无限 |
| **编译（ingest）** | 5/天 | 50/天 | 无限 |
| **单次文件大小** | **5 MB** | **20 MB** | **100 MB** |
| **查询（query）** | 20/天 | 200/天 | 无限 |
| **批量 Ingest** | ✗ | ✗ | ✓ |
| **Obsidian Sync** | ✗ | ✓ | ✓ |
| **健康巡检** | 基础 | 基础 | 高级（矛盾检测） |
| **导出功能** | Markdown | Markdown + PDF | 全部格式 |
| **支持渠道** | 社区 | 社区 | 邮件支持 |

---

## 五、状态机与数据流

### 5.1 License 生命周期

```
                        ┌─────────────┐
                        │   No Key    │
                        │   (Free)    │
                        └──────┬──────┘
                               │ 输入 Key
                               ▼
                        ┌─────────────┐
         ┌─────────────►│  Inactive   │◄─────────────┐
         │ 解绑         │  (未激活)   │              │
         │              └──────┬──────┘              │
         │                     │ activate()          │
         │                     ▼                     │
         │              ┌─────────────┐              │
         │     ┌───────►│   Active    │───────┐      │
         │     │ 过期   │   (已激活)  │       │ 过期
         │     │        └──────┬──────┘       │
         │     │               │              │
         │     │         网络断开│              │
         │     │               ▼              │
         │     │        ┌─────────────┐       │
         │     │        │    Grace    │       │
         │     │        │ (离线宽限期) │       │
         │     │        └──────┬──────┘       │
         │     │               │ grace expired│
         │     │               ▼              │
         │     └────────┌─────────────┐       │
         │              │   Expired   │───────┘
         │              │   (已过期)  │
         │              └─────────────┘
         │                     │
         └─────────────────────┘ 续费/重新激活
```

### 5.2 支付流程

```
用户选择产品
    │
    ▼
POST /api/v1/orders ──► sage-billing /api/v1/orders
    │                         │
    │                         ▼
    │                    创建 Order + License (inactive)
    │                         │
    ▼                         │
返回 {out_trade_no, license_key}
    │
    ▼
用户选择支付方式（微信/支付宝）
    │
    ▼
POST /api/v1/orders/pay ──► sage-billing /api/v1/orders/pay
    │                              │
    │                              ▼
    │                         生成支付链接/二维码
    │                              │
    ▼                              │
返回 {payment_url}
    │
    ▼
用户完成支付（手机扫码或跳转）
    │
    ▼
支付平台回调 ──► sage-billing /api/v1/callbacks/wechat
    │               或 /api/v1/callbacks/alipay
    │
    ▼
sage-billing 更新 Order status = "paid"
    │
    ▼
前端轮询 GET /api/v1/orders/:out_trade_no
    │
    ▼
检测到 status = "paid"
    │
    ▼
POST /api/v1/license/activate
    │
    ▼
sage-billing 激活 License → 绑定 device_id
    │
    ▼
刷新 License 状态 → 用户获得 Pro 功能
```

---

## 六、实施计划

### Phase 1：后端代理层（3 天）

| # | 任务 | 文件 | 说明 |
|---|------|------|------|
| 1.1 | LicenseService 实现 | `core/license_service.py` | 验证、缓存、feature gating |
| 1.2 | 新增 API 路由 | `api/app.py` | /license, /products, /orders 代理端点 |
| 1.3 | 启动初始化 | `api/app.py` lifespan | 启动时 verify license |
| 1.4 | 配置扩展 | `core/config.py` | license_key, billing_url, grace_days |
| 1.5 | 本地测试 | — | 启动 billing 服务，验证端到端流程 |

### Phase 2：前端 UI（4 天）

| # | 任务 | 文件 | 说明 |
|---|------|------|------|
| 2.1 | 类型定义 | `types/license.ts` | LicenseStatus, Product, Order |
| 2.2 | API 仓库 | `api/repositories/license.ts` | licenseRepo |
| 2.3 | React Query Hooks | `hooks/useLicense.ts` | useLicenseStatus, useActivateLicense, usePollOrderStatus |
| 2.4 | LicenseBadge 组件 | `components/layout/LicenseBadge.tsx` | 顶部状态指示器 |
| 2.5 | LicenseDetail Modal | `components/license/LicenseDetailModal.tsx` | 状态详情、功能清单、用量 |
| 2.6 | UpgradeModal | `components/license/UpgradeModal.tsx` | 产品列表、支付选择 |
| 2.7 | 设置页 License 分组 | `views/Settings.tsx` | 激活/解绑界面 |
| 2.8 | 限制提示弹窗 | `components/license/LimitReachedToast.tsx` | Free 用户超限提示 |

### Phase 3：Feature Gate 集成（2 天）

| # | 任务 | 文件 | 说明 |
|---|------|------|------|
| 3.1 | Project 数量限制 | `api/app.py` create_project | 检查 tier.max_projects |
| 3.2 | 编译次数限制 | `api/app.py` ingest | 检查 tier.max_compiles_per_day |
| 3.3 | **编译文件大小限制** | `api/app.py` ingest | 读取 content 后调用 `license_service.check_file_size(len(content))` |
| 3.4 | 查询次数限制 | `api/app.py` query | 检查 tier.max_queries_per_day |
| 3.5 | 用量计数器 | `core/store.py` 或新模块 | 每日 compile/query 计数 |
| 3.6 | 前端限制提示 | 各功能页面 | 超限前预警、超限后引导升级；Ingest 面板显示当前 tier 的文件大小限制 |

### Phase 4：联调测试（2 天）

| # | 任务 | 说明 |
|---|------|------|
| 4.1 | 完整购买流程测试 | 创建订单 → 支付（mock）→ 激活 → 功能解锁 |
| 4.2 | 离线场景测试 | 断开 billing 服务，验证 grace period |
| 4.3 | 降级场景测试 | 过期后自动降级为 free，功能受限 |
| 4.4 | 解绑/换设备测试 | deactivate → 新设备 activate |

---

## 七、关键设计决策

### 7.1 为什么 sagemate-core 作为代理，而不是前端直连 billing？

| 方案 | 优点 | 缺点 | 选择 |
|------|------|------|------|
| **sagemate-core 代理**（选中） | 安全（API key 不暴露）、统一认证、可扩展本地逻辑 | 多一层转发延迟 | ✅ |
| 前端直连 billing | 少一层转发 | API key 暴露、前端需维护两套 baseURL、CORS 问题 | ❌ |

### 7.2 离线策略：为什么用本地文件缓存而不是纯内存？

- 桌面应用重启后需要记住 license 状态
- 用户可能在无网络环境（飞机、偏远地区）使用
- 缓存文件在 `data/license_cache.json`，随数据目录迁移

### 7.3 为什么买断制和订阅制都映射到 Pro tier？

简化前端逻辑：
- 用户只关心"我有哪些功能"
- 不关心付费方式是买断还是订阅
- sage-billing 负责到期提醒和续费，sagemate-core 只认 tier

---

## 八、接口契约速查表

### sagemate-core → sage-billing 代理映射

| sagemate-core 端点 | sage-billing 端点 | 方法 |
|-------------------|-------------------|------|
| GET /api/v1/products | GET /api/v1/admin/products | GET |
| POST /api/v1/orders | POST /api/v1/orders | POST |
| POST /api/v1/orders/pay | POST /api/v1/orders/pay | POST |
| GET /api/v1/orders/:id | GET /api/v1/orders/:id | GET |
| POST /api/v1/license/activate | POST /api/v1/activate | POST |
| POST /api/v1/license/deactivate | POST /api/v1/deactivate | POST |

### sagemate-core 内部端点（无代理）

| 端点 | 说明 |
|------|------|
| GET /api/v1/license | 返回本地缓存的 license 状态 + feature flags + 用量 |

---

> **文档版本**: v1.0  
> **编写日期**: 2026-04-25  
> **对应后端**: sage-billing v0.4.0  
> **对应前端**: sagemate-core frontend (React SPA)  
> **下一阶段动作**: 进入 Phase 1 开发，优先实现 LicenseService + API 代理路由
