---
title: 'Agent Skill Integration'
slug: agent-skill-integration
category: concept
tags: ["ai-agents", "api-design", "tool-use", "documentation"]
sources: ["1775149860336-docx"]
source_pages: [1]
---

A framework and documentation standard for enabling AI agents to explicitly invoke external processes, local services, or sidecar binaries to perform specialized tasks such as P2P networking, data retrieval, or blockchain transactions.

## Core Principles
- **Explicit Invocation**: Agents call sidecar tools via well-defined local APIs rather than relying on transparent proxies or hidden background processes.
- **Protocol Mapping**: Tool definitions (often in a `SKILL.md` file) must strictly align with the sidecar's HTTP endpoints, ensuring predictable input/output schemas and error handling.
- **Asynchronous Execution**: Supports patterns like optimistic execution where an action is initiated immediately while secondary processes (e.g., payment confirmation) run asynchronously.

## Implementation Context
For the [[solana-p2p-sidecar]], the Skill integration defines the exact contract between the AI agent and the Sidecar. The documentation outlines required functions for peer discovery, P2P messaging, and wallet operations, ensuring the HTTP API design remains strictly compatible with the agent's tool-use expectations.

## Related
- [[solana-p2p-sidecar]]
- [[sandwich-architecture]]