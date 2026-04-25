---
title: Graph Neural Networks
category: concept
tags: [concept, ml, gnn, graphs, deep-learning]
created: 2026-04-20
status: learning
---

# Graph Neural Networks

Neural networks that operate on graph-structured data.

## Why Graphs?

Many real-world problems are naturally graph-structured:
- Social networks
- Molecular structures
- Knowledge graphs ([[Knowledge Graph]])
- Recommendation systems

## Key Architectures

### GCN (Graph Convolutional Network)

$$H^{(l+1)} = \sigma(\tilde{D}^{-1/2} \tilde{A} \tilde{D}^{-1/2} H^{(l)} W^{(l)})$$

Where:
- $\tilde{A} = A + I$ (adjacency matrix + self-loops)
- $\tilde{D}$ = degree matrix
- $W^{(l)}$ = learnable weights

### GraphSAGE

Inductive learning — can generalize to unseen nodes.

```python
# Sample and aggregate
h_v = aggregate({h_u for u in neighbors(v)})
```

### GAT (Graph Attention Network)

Learns attention weights between connected nodes.

## Applications for SageMate

1. **Wiki Link Recommendation** — predict missing links
2. **Note Clustering** — discover implicit topics
3. **Search Ranking** — semantic + structural relevance

## Resources

- [[Paper]]: Kipf & Welling, 2016 (GCN)
- [[Paper]]: Hamilton et al., 2017 (GraphSAGE)
- [[Course]]: Stanford CS224W

## Related

- [[node2vec]] — random walk embeddings
- [[Knowledge Graph]] — our wiki structure
- [[TF-IDF]] — current baseline

---
#concept #ml
