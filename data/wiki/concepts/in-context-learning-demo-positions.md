---
title: 'In-Context Learning Demo Positions'
slug: in-context-learning-demo-positions
category: concept
tags: ["prompt-engineering", "llm", "configuration"]
sources: ["2507-22887v1_副本-pdf"]
---

In-context learning demo positions refer to four canonical structural placements for demonstration blocks within an instruction-tuned LLM prompt. These configurations are used to isolate spatial effects on model performance independent of demo content or order.

## Canonical Configurations
- **Start of System Prompt (ssp)**: Demos are placed at the very beginning of the system message, preceding all instructional content.
- **End of System Prompt (esp)**: Demos are placed at the end of the system message, after general instructions but before the user query.
- **Start of User Message (sum)**: Demos are inserted at the beginning of the user message, before the actual query text. (Often the default configuration).
- **End of User Message (eum)**: Demos are appended at the very end of the user message, following the query.

## Placement Recommendations
Strategic placement, such as clustering critical demos near task instructions (`ssp` or `sum`), leverages primacy effects to maximize stability and accuracy.

## Related
- [[demos-position-in-prompt-bias]]
- [[in-context-learning]]