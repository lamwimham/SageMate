---
title: 'Accuracy-Change Metric'
slug: accuracy-change-metric
category: concept
tags: ["evaluation", "metrics", "prompt-engineering"]
sources: ["2507-22887v1_副本-pdf"]
---

The Accuracy-Change metric is a task-agnostic evaluation measure that quantifies the net performance shift (delta) in task accuracy when structural components of a prompt are modified or repositioned.

## Purpose & Usage
- **Isolating Positional Effects**: By holding demo content and order constant, it measures how spatial rearrangement alone impacts final correctness.
- **Net Gain Assessment**: Helps identify optimal prompt layouts that yield consistent accuracy improvements (e.g., +6 points for early placement).
- **Equivalent Forms**: Conceptually equivalent to "performance delta" or `Accuracy-Δ` used in prompt sensitivity literature.

## Related
- [[prediction-change-metric]]
- [[demos-position-in-prompt-bias]]
- [[in-context-learning]]