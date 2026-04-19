---
title: 'In-Context Learning'
slug: in-context-learning
category: concept
tags: ["machine-learning", "llm", "prompt-engineering"]
sources: ["2507-22887v1_副本-pdf"]
---

In-context learning (ICL) is a paradigm enabling large language models (LLMs) to adapt to novel tasks by processing a small set of demonstrations (demos) embedded directly in the input prompt, without requiring parameter updates. This approach facilitates few-shot and zero-shot generalization across diverse tasks such as classification, question answering, and summarization.

## Key Characteristics
- **Dynamic Adaptation**: Models infer task instructions and formats implicitly from the provided context.
- **Prompt Sensitivity**: Performance is highly brittle to superficial prompt characteristics, including demo ordering, template phrasing, and spatial placement.
- **Brittleness**: Minor perturbations in demo selection or sequence can degrade performance unpredictably, challenging assumptions about robust systematic reasoning.

## Related
- [[demos-position-in-prompt-bias]]
- [[in-context-learning-demo-positions]]
- [[primacy-bias-in-transformers]]