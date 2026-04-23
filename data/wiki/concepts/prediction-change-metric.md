---
title: 'Prediction-Change Metric'
slug: prediction-change-metric
category: concept
tags: ["evaluation", "metrics", "volatility", "prompt-engineering"]
sources: ["2507-22887v1_副本-pdf"]
---

The Prediction-Change metric is a task-agnostic evaluation measure that quantifies output volatility by calculating the percentage of individual predictions that flip when prompt components are repositioned.

## Purpose & Usage
- **Measuring Volatility**: Captures instability in model outputs that accuracy alone might mask (e.g., high accuracy but 30% prediction flips).
- **Equivalent Forms**: Conceptually equivalent to "sensitivity" or "output flip rate" (`Prediction-Δ`) in prompt robustness studies.
- **Insight**: High prediction-change indicates the model is relying on superficial positional cues rather than stable semantic reasoning.

## Related
- [[accuracy-change-metric]]
- [[demos-position-in-prompt-bias]]
- [[in-context-learning]]