---
title: 'Sandwich Architecture'
slug: sandwich-architecture
category: concept
tags: ["software-architecture", "system-design", "layered-pattern"]
sources: ["1775149860336-docx"]
source_pages: [1]
---

A software architectural pattern that structures an application into three distinct, vertically stacked layers: a northbound interface for external consumption, a middle layer for core business logic and state management, and a southbound layer for infrastructure, hardware, or network communication.

## Layer Responsibilities
- **Northbound (API/Client Facing)**: Handles client requests, data serialization, and exposes standardized endpoints. In P2P systems, this typically translates to HTTP/REST or gRPC interfaces.
- **Middle (Strategy & State)**: Contains the core decision-making logic, routing, policy enforcement, and state tracking. It decouples external interfaces from underlying network mechanics.
- **Southbound (Infrastructure/Network)**: Manages low-level connections, transport protocols (e.g., QUIC, TCP), peer discovery, and security/encryption.

## Application in Sidecar Systems
In the [[solana-p2p-sidecar]] design, this pattern cleanly separates the [[agent-skill-integration]] HTTP calls from the complex networking stack, allowing independent iteration on agent-facing APIs and P2P routing logic while maintaining a unified strategy engine.

## Related
- [[solana-p2p-sidecar]]
- [[agent-skill-integration]]