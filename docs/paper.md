# Taming Scylla

## Understanding the multi-headed agentic deamon of the coding seas

Micah Villmow
Individual
research@villmow.us

---

## Abstract

<Abstract text summarizing the motivation, methodology, models evaluated, key results, and conclusions.>

---

## Keywords

<Keywords; e.g., LLM agents, benchmarking, cost-of-pass, multi-agent systems, software engineering>

---

## 1. Summary

<High-level executive summary of the research goals, experimental setup, major findings, and implications.>
With the advancement of large language models has come a massive increase in capabilities for automated computer interactions. What used to require hand-coded algorithms and pipelines can now be done automatically using state of the art coding models to generate instructions that can then be utilized to further improve automated approaches. However, understanding what improves these language models is more of black magic than art, let alone a rigorous science. This paper's goal is to help demistify the magic of prompt engineering by proposing a rigorous evaluation framework across multiple dimensions to help determine how agents interact, the scale that of changes for the agentics, and an attempt to quantify with numbers the benefits of each approach across a broad range of activities.

There are benchmarks for measuring LLM's workflows in various domains, such as agent-bench[1], swe-bench[2], tau-bench[3], etc... There are also prompt evaluation benchmarks such as PromptBench[4], PromptEval[5], Multi-Prompt Eval[6], etc... This paper focuses specifically on coding tools, specifically industry leading tool Claude Code[7], and how prompt modification can change the behavior of the model for better or for worse. This paper also introduces a framework for evaluating other tools in a systematic way, thus allowing extension to domains outside of CLI based coding tools. We show that <insert findings here>. 

This implies that there is still a <summarize implications> and repost here.

---

## 2. Introduction

Anthropic has many good resources for improving Claude Code on their engineering blog, but there is not a simple way to measure easily whether changes to the prompt instructions actually benefit in the way that the user can easily comprehend. Therefor, I am introducing Scylla, a testing framework for evaluating prompts, tools, skills, and agents for solving problems that are common for day to day coding tasks. I wanted to know if sub-agents, skills, tools, or mcp servers were actually contributing to improved code output, without relying on my gut or intuition. This problem came up multiple times when asked by others to explain how to better utilize CLI tools for programming. In my experience, the quality of the prompts has a dramatic improvement on the output of the results. Whether its the prompt to call the tool or MCP server, the prompt to spawn a sub-agent, or the prompt to trigger a skill, these language based triggers are fuzzy in their meaning, unlike a traditional programming language that is very explicit in what it is means and what it does.

First, in section 3, I will introduce the current work that is being done in this area, and explain how they approach the problem. Then, in section 4, I will introduce the testing methodology along with an in-depth analysis of the first test case. This will provide the needed understanding of what is being tested and why on something that should be easily dissectable and understandable. The next three section will introduce three more test cases of varying tasks and complexity that show the variance of results from the various prompts. After that, I will dissect some of the more interesting cases where there was large impacts on the baseline behavior of the model. The final section will showcase the final results across a larger set of test cases, and point to further areas of research and how to extend this to other models.

The questions I am investigating are:
* Is it possible to quantify whether a task is solveable more efficiently by one methodology over others?
* Is the sum of a prompt more than the individual parts? 
* Are there core improvements that can be made purely through extensions to claude code that are generic for all workloads?
* Are there specific prompt techniques that have secondary effects, positive or negative, on other prompt techniques?
* Holding the tool and prompt constant, how much does the underlying model contribute to the quality of the results?

Some hypotheses I have are:
* Certain tasks excel when run as sub-tasks, or tools, or mcp, or skills, that are unrelated to context management.
* Prompt complexity has a negative correlation to higher quality results, i.e. KISS principle, in scenarious that is part of the training set.
* Prompt complexity has a positive correlation to higher quality results, i.e. an inverse KISS principle, in scenerios outside of the training set.

---

## 3. Related Work

<Prior work on LLM benchmarking.>
<Related work on agentic systems and multi-agent architectures.>
<Existing evaluation frameworks and gaps addressed by this work.>

---

## 4. Test Methodology

### 4.1 Experimental Design

<Overall experimental design and rationale.>
<Ablation strategy and tiered evaluation approach (T0–T6).>

### 4.2 Dimensional Search Space

<Definition of dimensional axes explored in this study.>

* **Agent Complexity:** <Tier 0–6 definition and criteria>
* **Prompt Complexity:** <Prompt scale 0–10 definition>
* **Skill Complexity:** <Definition and categorization>
* **Agent Hierarchy:** <Flat vs hierarchical vs hybrid>

---

## 5. Test Metrics

### 5.1 Performance Metrics

<Completion metrics, success rates, and accuracy definitions.> <Fine-grained progress metrics.>

### 5.2 Quality Metrics

<Implementation rate, semantic correctness, and validation strategy.> <Code quality and maintainability metrics.>

### 5.3 Efficiency and Cost Metrics

<Latency measurements.>
<Token usage and cost accounting.>
<Cost-of-Pass (CoP) definition and calculation.>

---

## 6. Test Configuration

### 6.1 Hardware and Infrastructure

<Compute environment, hardware specifications, and execution environment.>

### 6.2 Software Stack

<Frameworks, libraries, orchestration tools, and evaluation harness.>

### 6.3 Model Configuration

<Model versions, context limits, decoding parameters, and safety settings.>

---

## 7. Test Cases

### 7.1 Pull Request (PR) Selection Criteria

<Selection methodology and constraints.>

* **PR Size Categories:**

  * <Small: < 100 LOC>
  * <Medium: 300–500 LOC>
  * <Large: 500–2000 LOC>

### 7.2 Workflow Categories

<Description of each workflow category and evaluation intent.>

* **Build System:** <Description>
* **CI/CD:** <Description>
* **Bug Fixing:** <Description>
* **New Features:** <Description>
* **Refactoring:** <Description>
* **Optimization:** <Description>
* **Review:** <Description>
* **Documentation:** <Description>
* **Issue Filing:** <Description>

### 7.3 Test Case Matrix

<Table mapping PRs × workflow categories × complexity tiers.>

---

## 8. Model Summary

### 8.1 Claude Code Models

* **Claude Opus:** <Model description and role>
* **Claude Sonnet:** <Model description and role>
* **Claude Haiku:** <Model description and role>

### 8.2 OpenAI Models

* **Codex / GPT‑5.2:** <Model description and role>

### 8.3 Large Model CLI-Based Systems

<Unified description of CLI-based or tool-driven agent systems.>

* **Claude Opus:** <Details>
* **OpenAI GPT‑5.2:** <Details>
* **Gemini 3.0 Pro:** <Details>
* **DeepSeek:** <Details>
* **Qwen 3:** <Details>
* **MBZ‑K2:** <Details>
* **Kimi‑K2 + Kimi‑3:** <Details>

---

## 9. Results

### 9.1 Quantitative Results

<Tables and figures summarizing performance, quality, and cost metrics.>

### 9.2 Comparative Analysis

<Comparison across models, tiers, and workflow categories.>

### 9.3 Cost–Performance Trade-offs

<Analysis of CoP, scaling behavior, and diminishing returns.>

---

## 10. Discussion

<Interpretation of results.>
<Implications for agent design and deployment.>
<Observed failure modes and limitations.>

---

## 11. Conclusions

<Summary of findings.>
<Answers to research questions.>
<Key takeaways for practitioners and researchers.>

---

## 12. Further Work

<Proposed extensions, additional benchmarks, and future research directions.>

---

## Acknowledgements

<Acknowledgements and funding sources.>

---

## References

<Bibliography entries in the required citation format.>

---

## Appendices

### Appendix A: Detailed Metric Definitions

<Expanded definitions and formulas.>

### Appendix B: Additional Tables and Figures

<Supplementary results.>

### Appendix C: Reproducibility Checklist

<Steps, configurations, and artifacts required to reproduce the study.>

