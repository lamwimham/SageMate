---
title: Formula Postprocessor
category: concept
tags: [sagemate, pdf, latex, formula]
created: 2026-04-21
---

# Formula Postprocessor

Normalizes LaTeX formulas extracted from PDFs.

## Unicode → LaTeX Mappings

| Unicode | LaTeX | Description |
|---------|-------|-------------|
| `²` | `^2` | Superscript 2 |
| `₃` | `_3` | Subscript 3 |
| `α` | `\alpha` | Greek alpha |
| `β` | `\beta` | Greek beta |
| `×` | `\times` | Multiplication |
| `≈` | `\approx` | Approximate |
| `∞` | `\infty` | Infinity |
| `∑` | `\sum` | Summation |

## Dollar Spacing Fix

```
$ ^ { \S + 1 } $    →    $^{\S+1}$
```

## Pipeline

```
PDF → pdftotext → FormulaPostProcessor.process() → Markdown
```

Integrated in `PDFParseStrategy.parse()` so all PDFs automatically get cleaned.

---
#sagemate #pdf
