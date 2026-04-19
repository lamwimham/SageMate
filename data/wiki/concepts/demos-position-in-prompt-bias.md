---
title: 'Demos' Position In Prompt Bias'
slug: demos-position-in-prompt-bias
category: concept
tags: ["llm", "prompt-engineering", "bias", "evaluation"]
sources: ["2507-22887v1_副本-pdf"]
---

Demos' Position In Prompt (DPP) bias is a positional vulnerability in in-context learning where relocating an unchanged block of demonstrations within a prompt's structure significantly alters task accuracy and prediction stability.

## Characteristics & Impact
- **Magnitude**: Moving demos from the start to the end of a prompt can swing accuracy by up to 50 percentage points and flip nearly half of model predictions.
- **Independence from Content**: The bias is purely spatial; identical demo content yields drastically different results based solely on placement relative to instructions and queries.
- **Model Sensitivity**: Smaller parameter models exhibit the highest volatility. Larger models are marginally less affected but still show sensitivity on complex tasks.
- **Practical Guideline**: Placing demonstrations at the start of the prompt generally yields the most stable and accurate outputs, with gains up to +6 accuracy points. Conversely, appending demos at the end of a user message flips over 30% of predictions in QA tasks without improving correctness.

## Related
- [[in-context-learning]]
- [[in-context-learning-demo-positions]]
- [[accuracy-change-metric]]
- [[prediction-change-metric]]
- [[primacy-bias-in-transformers]]