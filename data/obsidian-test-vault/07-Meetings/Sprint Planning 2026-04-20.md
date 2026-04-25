---
title: Sprint Planning 2026-04-20
category: meeting
date: 2026-04-20
attendees: [me, Alex Chen, Sarah Liu, David Kim]
tags: [meeting, sprint, planning, q2]
---

# Sprint Planning 2026-04-20

**Date**: 2026-04-20  
**Attendees**: [[Alex Chen]], [[Sarah Liu]], [[David Kim]], me

## Agenda

1. Q2 OKRs review
2. Streaming feature retrospective
3. Next sprint priorities
4. Technical debt discussion

## Decisions

| # | Decision | Owner | Deadline |
|---|----------|-------|----------|
| 1 | Ship streaming by end of Q2 | me | Jun 30 |
| 2 | Migrate to [[Rust]] for parser | [[David Kim]] | Aug 15 |
| 3 | Add [[Graph Neural Networks]] for recommendations | [[Sarah Liu]] | Jul 31 |
| 4 | Reduce CI time from 12min to 5min | [[Alex Chen]] | May 15 |

## Action Items

- [ ] Write [[Q2 OKRs]] document
- [ ] Schedule mid-sprint check-in (May 5)
- [ ] Review [[Technical Debt Register]]

## Notes

[[Alex Chen]] raised concerns about API costs for [[GLM-OCR]] at scale. Need to do cost analysis before full rollout.

[[David Kim]] proposed using [[Rust]] for the PDF parser to get 10x speedup. Worth exploring but risk is integration complexity.

---
#meeting #sprint
