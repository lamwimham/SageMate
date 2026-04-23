---
title: 'Hermes Agent与Evolver引擎抄袭争议'
slug: hermes-agent-evolver-controversy
category: analysis
tags: ["AI代理", "开源争议", "Hermes Agent", "EvoMap"]
sources: ["deepseek迎来首轮外部融资_宇树h1半马被担架抬离赛道_钉钉创始人_全员禁止写文档_hermes_agent三度否认抄袭_ai周报-md"]
source_pages: [1]
---

2026年4月，国内AI团队EvoMap公开指控硅谷明星开源项目Hermes Agent的核心自进化能力系统性复刻了其开源的Evolver引擎。争议聚焦于架构同构性、术语映射替换及极短的研发时间窗口，Hermes所属实验室Nous Research先后三次予以否认。

## EvoMap指控核心
- **架构高度同构**：Evolver的10步进化主循环与Hermes自进化模块执行流程一一对应，均实现任务经验提取闭环、周期性自我评估与技能按需加载。
- **术语系统性替换**：存在12组核心术语的刻意替换（如Gene对应SKILL.md，Capsule对应技能执行记录，solidify对应skill_manage等）。
- **时间线高度重合**：Evolver于2月1日开源核心设计，Hermes于3月中旬推出对应自进化功能，时间差仅24至39天。
- **零引用**：Hermes公开材料中对先行开源的Evolver与GEP协议未做引用或致谢。

## Hermes方反驳与后续
- **仓库创建时间**：Hermes官方指出其代码仓库创建早于Evolver，主张技术先发。
- **独立收敛论**：联合创始人Teknium称从未听说EvoMap，否认抄袭，称架构系依赖学术开源独立收敛。
- **中国首秀回应**：业务负责人Tommy Eastman重申未抄袭，强调Nous Research是理念驱动的开源团队。
- **社区部署**：争议未阻碍商业化进程，MiniMax基于其推出云端沙箱MaxHermes，腾讯与阿里云相继上线一键部署模板。

## 行业启示
争议凸显了Agent自进化架构成为开源社区核心资产的背景下，知识产权界定、开源协议遵守与“独立发明”边界面临的严峻挑战。

## Related
- [[guo-daya]]
- [[dingtalk-no-document-policy]]