---
title: 101 Formulaic Alphas
category: resource
tags: [finance, quant, alphas, worldquant]
created: 2026-04-25
source: 101 Formulaic Alphas (1).pdf
---

# 101 Formulaic Alphas

Paper by [[Zura Kakushadze]] presenting 101 real-life quantitative trading alphas.

## Key Findings

1. Average holding period: **0.6-6.4 days**
2. Average pair-wise correlation: **15.9%**
3. Returns strongly correlated with volatility $\sigma$
4. Returns have **no significant dependence** on turnover

## Scaling Law

$$R \sim \sigma^{\eta}, \quad \eta \approx 0.76$$

Where $R$ is alpha return and $\sigma$ is volatility.

## Sample Alphas

```python
# Alpha#1 — Mean-reversion
rank(Ts_ArgMax(SignedPower(((returns < 0) ? stddev(returns, 20) : close), 2.), 5)) - 0.5

# Alpha#2 — Volume-price correlation
-1 * correlation(rank(delta(log(volume), 2)), rank(((close - open) / open)), 6)

# Alpha#3 — Open-volume correlation
-1 * correlation(rank(open), rank(volume), 10)
```

## Operators Used

| Operator | Description |
|----------|-------------|
| `rank(x)` | Cross-sectional percentile rank |
| `correlation(x, y, d)` | Rolling correlation over d days |
| `ts_rank(x, d)` | Time-series rank |
| `delta(x, d)` | $x_t - x_{t-d}$ |
| `stddev(x, d)` | Rolling standard deviation |
| `SignedPower(x, a)` | $	ext{sign}(x) \cdot |x|^a$ |
| `Ts_ArgMax(x, d)` | $rg\max_i x_i$ over window |

## Related

- [[Investment-Research]] — parent project
- [[Zura Kakushadze]] — author
- [[Kakushadze and Tulchinsky, 2015]] — prior work

---
#finance #quant
