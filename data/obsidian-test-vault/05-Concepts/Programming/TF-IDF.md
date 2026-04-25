---
title: TF-IDF
category: concept
tags: [concept, nlp, information-retrieval, baseline]
created: 2025-08-01
---

# TF-IDF

Term Frequency-Inverse Document Frequency. Classic IR weighting scheme.

## Formula

$$\text{TF-IDF}(t, d) = \text{tf}(t, d) \times \text{idf}(t)$$

Where:
- $\text{tf}(t, d) = \frac{f_{t,d}}{\sum_{t' \in d} f_{t',d}}$
- $\text{idf}(t) = \log \frac{N}{|\{d \in D : t \in d\}|}$

## Limitations

1. **Bag-of-words** — ignores word order
2. **Sparse vectors** — high dimensionality
3. **No semantics** — "king" and "queen" are unrelated

## SageMate Usage

Current baseline for wiki search. Plans to upgrade to:
- [[Dense Passage Retrieval]] (bi-encoder)
- [[Graph Neural Networks]] (structure-aware)

## Related

- [[BM25]] — probabilistic alternative
- [[Information Retrieval]] — parent topic
- [[Dense Passage Retrieval]] — neural alternative

---
#concept #nlp
