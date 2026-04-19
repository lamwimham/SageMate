---
title: 'Primacy Bias in Transformers'
slug: primacy-bias-in-transformers
category: concept
tags: ["transformers", "architecture", "attention", "bias"]
sources: ["2507-22887v1_副本-pdf"]
---

Primacy bias in transformers is a mechanistic tendency within transformer architectures to disproportionately attend to, weight, and retain tokens presented early in an input sequence, often causing early context to steer subsequent predictions.

## Mechanisms
- **Induction Heads**: Architectural components that reinforce the importance of early tokens, steering later generation.
- **Sequential Processing**: Intrinsic biases toward earlier context that degrade performance when crucial information appears later in the sequence.
- **Middle Position Degradation**: Tokens in the middle of sequences often receive less attention, creating a "lost in the middle" effect.
- **Memory Mechanisms**: Linked to underlying transformer memory and state tracking capabilities that prioritize initial context windows.

## Relation to Prompt Engineering
This bias explains phenomena like the [[demos-position-in-prompt-bias]], where placing demonstrations at the start of a prompt yields significantly better and more stable results than appending them at the end.

## Related
- [[demos-position-in-prompt-bias]]
- [[in-context-learning]]
- [[in-context-learning-demo-positions]]