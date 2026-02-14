# **Architectural Efficacy and Economic Sustainability: A Rigorous Blueprint for Benchmarking Incremental Agent Capabilities**

## **1\. Foundational Review of Agentic Design Paradigms**

The effective integration of large language models (LLMs) into autonomous systems necessitates a rigorous, structured evaluation framework that moves beyond simple success metrics. This project outlines an empirical study designed to isolate the performance gains and concomitant economic costs associated with incrementally increasing the agentic complexity of a base LLM. The underlying thesis is that sophisticated agent architectures, while promising increased efficacy, introduce significant operational overhead, requiring an economic metric to evaluate true sustainability.

### **1.1. Defining the Agentic System: Core Principles and Modular Taxonomy**

The evaluation begins by establishing a formal definition of the agentic system based on core principles of autonomy and goal-oriented behavior.1 To facilitate an ablative study, the architecture must be decomposed into functional modules. This modular approach allows for precise quantification of the marginal contribution of each component to overall system performance.2

Modern agent design is best characterized using a functional taxonomy, drawing parallels to cognitive structures.3 Key components that define agentic capacity include:

* **Task Decomposer (Biological Analogue: Anterior Prefrontal Cortex, aPFC):** This module is responsible for abstract, high-level planning, specifically breaking down an overall long-horizon goal into executable subgoals.3
* **Actor (Biological Analogue: Dorsolateral PFC, dlPFC):** The primary execution unit, generating candidate actions based on the current state and task.3
* **Monitor (Biological Analogue: Anterior Cingulate Cortex, ACC):** Crucial for dynamic error detection and constraint checking within the workflow.3
* **Evaluator/Predictor (Biological Analogue: Orbitofrontal Cortex, OFC):** Provides heuristic value estimation of states and forecasts the likely success of next actions, a core mechanism for self-reflection and iterative improvement.3
* **Orchestrator:** A centralized supervisor responsible for managing the progress, sequencing, and eventual termination of complex tasks, particularly essential in multi-agent configurations.3

When moving to higher architectural tiers (T4 and T5), the system transitions from flat, stateless execution toward a nested, functionally distributed organization known as a **Hierarchical Agentic Taxonomy**.4 This taxonomy is fundamental because it imposes vertical stratification, defining clear relations among agent roles (planners, executors) and establishing multi-layer memory structures necessary for scalable reasoning and robust task allocation.4

The complexity introduced in these higher tiers is principally driven by the iterative self-correction loop, primarily governed by the Monitor and Evaluator functions. While essential for achieving high-quality outcomes, the architectural overhead associated with this monitoring and verification process is significant. Specifically, the Critic’s verification step in iterative architectures can effectively **double the inference requirement per iteration** compared to single-shot baselines, resulting in substantially higher latency and token costs.5 This dynamic confirms that improvements in robustness and quality in T5 architectures are obtained at a non-linear increase in operational expenditure. Consequently, the benchmarking blueprint must isolate the cost attributed to this iterative verification and explore optimization strategies, such as utilizing smaller, distilled LLMs specifically fine-tuned for the Monitor/Critic role, to mitigate cost without compromising reliability.5

The nature of this project, defined as an ablative study, necessitates systematic component analysis.2 To ensure methodological rigor and efficiency, the experimental blueprint must integrate a mechanism for automated code analysis, similar to frameworks used for automated code ablation studies.2 This mechanism would systematically generate ablated versions—for example, removing the explicit Evaluator module—and ensure that the modified code remains functional while quantifying the resulting performance degradation and cost savings.

### **1.2. State-of-the-Art Benchmarking: Justifying Fine-Grained Metrics**

Traditional LLM evaluation, focusing on the final success rate, fails to provide sufficient insight into agent capabilities, particularly during complex, multi-round interactions in partially-observable environments.6 To address this limitation, the project mandates the use of analytical evaluation frameworks designed for LLM agents.

The core necessity is a transition to process-oriented metrics that capture intermediate advancements. Frameworks such as AgentBoard have pioneered this approach by offering a comprehensive evaluation toolkit tailored for multi-faceted analysis.6 The central innovation required for this project is the utilization of a **fine-grained progress rate metric**.6 This metric captures incremental advancements throughout the execution trajectory of the agent, rather than focusing solely on the binary outcome.7 For complex, long-horizon tasks handled by hierarchical systems (T5), the fine-grained progress rate is indispensable for diagnosing precisely where sophisticated planning (Task Decomposer function) or iterative execution (Actor function) succeeds or fails. This analytical approach propels the interpretability of agent performance to the forefront of the evaluation.6

## **2\. The Incremental Capability Matrix: Defining Testing Tiers**

The experimental methodology is structured around a controlled, sequential introduction of agentic capabilities. By benchmarking performance and cost at each incremental step ($T(n)$ versus $T(n-1)$), the study aims to quantify the marginal utility and economic viability of specific architectural components.

### **2.1. Tier 0 & 1: Cost Floor and Context Optimization**

#### **T0 – Vanilla LLM (Zero-Shot Baseline)**

The foundational stage involves running the base LLM in a zero-shot, single-inference setting. This establishes the absolute minimum operational cost and performance floor for the task domain.5 Given the objective of economic sustainability, a cost-effective model (e.g., GPT-3.5-turbo) should be selected for the baseline to ensure that any subsequent architectural complexity must prove its value against a highly competitive cost-effective model.9

#### **T1 – Prompt Optimization**

Tier 1 introduces sophisticated **Prompt Engineering** 10 and **Context Engineering** 11 to optimize model behavior within the single-LLM architecture. Context engineering is the continuous process of curating high-signal information to be passed to the model within its finite attention budget.11 Given that models may exhibit reduced precision in long-range reasoning in extremely long contexts, thoughtful context engineering ensures that the smallest possible set of high-signal tokens are utilized to maximize the desired outcome.11 The performance ceiling of this optimized, non-agentic architecture serves as a crucial benchmark for determining if added architectural complexity (T2-T6) yields sufficient improvement to justify its overhead.

### **2.2. Tier 2 & 3: Resource Augmentation Trade-offs (Skills vs. Tooling)**

This phase directly contrasts two methods of providing domain knowledge and execution capacity: internal skills (prompt-based expertise) versus external tooling (API schemas).

#### **T2 – Prompt \+ Skills**

This tier incorporates domain expertise and judgmental heuristics encoded directly within the agent’s system prompt or specialized instructions. The primary advantage of this approach lies in its **token economics**.12 Skills, being prompt-based instructions, encode domain knowledge and approach without requiring the massive token consumption associated with tool schema descriptions. When dealing with complex systems that might expose numerous capabilities (e.g., 90+ tools), the act of loading JSON schemas can consume over 50,000 tokens before any reasoning even begins.12 T2 is hypothesized to deliver high efficacy at an excellent Cost-of-Pass (CoP) efficiency, particularly in scenarios requiring judgment rather than complex external execution.

#### **T3 – Prompt \+ Tooling**

Tier 3 equips the agent with access to external functions and APIs via structured schema definitions (e.g., JSON). This capability enables the agent to take real-world actions.13 However, this is the point at which the **Token Efficiency Chasm** manifests.14 The operational flaw is that agents often treat comprehensive tool libraries like knowledge, loading all definitions upfront "just in case".14 This results in massive context bloat and exorbitant input token bills, potentially consuming over 150,000 tokens in a single multi-tool workflow run.14 Consequently, while T3 provides necessary functional capability, the analysis is expected to reveal a sharp decline in CoP efficiency compared to T2, despite providing a more standardized interface for multi-model flexibility.12

### **2.3. Tier 4 & 5: Architectural Agentification (Delegation and Hierarchy)**

These tiers evaluate distributed cognitive architectures, assessing the efficiency and robustness of task delegation.

#### **T4 – Flat Delegation (Sub-Agents)**

T4 implements a multi-agent system where a centralized Orchestrator assigns tasks to specialist agents.15 This approach prioritizes **Atomic Task Design**, which involves breaking complex workflows into smaller, simpler, and narrowly scoped tasks.17 Production data indicates that this distribution reliably improves latency, cost, and reliability by avoiding the generalized prompts that lead to computational overhead and opacity in debugging.17 The use of specialized, narrow, and stateless agents results in cost reduction (in one observed case, a 54% decrease in cost per lead) and significant latency drops (up to 72% reduction) compared to relying on single, generalist agents.17

#### **T5 – Nested Hierarchy**

Tier 5 represents the highest architectural complexity, employing a pyramid-like Multi-Agent System 19 that features nested orchestration and deep planning capabilities.4 The architecture relies heavily on iterative feedback loops, where the Monitor/Evaluator component is active.5 The focus of the benchmarking here is to precisely measure the increased Cost-of-Pass (CoP) resulting from recursive planning, verification, and re-execution, and to contrast this cost against the expected gains in robustness and the ability to solve long-horizon, complex problems with higher accuracy.

### **2.4. Tier 6: Command and Hybrid Combinations**

This final phase optimizes the architecture by integrating structural constraints and testing synergistic combinations of components found to be independently effective and efficient.

* **Commands:** Strict structural requirements, such as forcing output to conform to a specific JSON or YAML format, are introduced to enhance consistency and determinism.20
* **Hybrid Optimization:** The core of T6 involves testing optimal combinations, such as integrating T2's token-efficient Skills with T4's Atomic Delegation, or incorporating **Agentic RAG**. Agentic RAG is a key hybrid pattern where the LLM dynamically directs tool usage and decision-making based on retrieved context.22 This approach moves beyond simple RAG (which only improves response generation accuracy) to enable intelligent automation that adapts and refines its performance over time. Empirical findings show Agentic RAG can deliver substantial reductions in error rates—up to 78% compared with traditional RAG baselines—making it a crucial test case for maximizing the efficacy-to-cost ratio.22

The following table summarizes the incremental matrix and the hypothesized economic implications for each architectural decision.

Table 2.1: Incremental Agent Capability Testing Matrix (Ablation Study Framework)

| Tier | Name | Sub-tests | Primary Function | Dominant Cost Driver | Hypothesized Viability |
| :---- | :---- | :---- | :---- | :---- | :---- |
| T0 | Prompts | 24 | System prompt ablation (empty → full CLAUDE.md) | Input Token Cost (Context) | Baseline measurement |
| T1 | Skills | 10 | Domain expertise via installed skills by category | Context Bloat (Mitigated) | Excellent CoP, High Efficacy |
| T2 | Tooling | 15 | External tools and MCP servers | Schema Token Overhead | High Efficacy, Poor CoP |
| T3 | Delegation | 41 | Flat multi-agent with specialist agents (L2-L5) | Orchestration Latency | High Efficacy, Moderate CoP |
| T4 | Hierarchy | 7 | Nested orchestration with orchestrator agents (L0-L1) | Iterative Verification Cost | Very High Efficacy, High CoP |
| T5 | Hybrid | 15 | Best combinations and permutations from all tiers | Synergistic Overhead | Maximized CoP/Efficacy Ratio |
| T6 | Super | 1 | Everything enabled at maximum capability | Maximum Overhead | Theoretical Upper Bound |

## **3\. Detailed Experimental Protocol and Task Selection**

The experimental rigor hinges on selecting tasks that genuinely challenge the agentic capabilities being tested and on implementing strict protocols for measuring quality throughout the process.

### **3.1. Task Domain Selection and Difficulty Structuring**

The benchmark suite must comprise non-trivial, multi-step tasks requiring complex interactions, such as end-to-end software development or complex data manipulation, to fully differentiate the performance of advanced T4 and T5 architectures from simpler ones.8

To ensure a meaningful evaluation, tasks must be structured to incrementally increase difficulty.24 Difficulty should be reliably proxied by complexity metrics, such as the number of required tool calls, the depth of context required, the sequential steps needed, or the number of constraints imposed.24 Testing should confirm the observation of a monotonic drop in performance as complexity increases, validating that the benchmark suite presents a meaningful challenge even to highly advanced models (e.g., GPT-4o).24

Crucially, the tasks must be of the **long-horizon** variety, where goal attainment necessitates many steps and state updates, effectively requiring planning and autonomy (T4/T5) rather than allowing for successful resolution via pure deductive reasoning (T0/T1).1

Finally, the integrity of the benchmark requires the establishment of a **human expert baseline**. This baseline serves two purposes: first, it confirms that the tasks are solvable, providing a target success rate (e.g., human solvers achieving 85% to 97.5% on complexity-controlled tasks) 24; and second, it establishes the economic frontier against which the agent’s performance and cost-efficiency are measured.25

### **3.2. The Ablation Study Blueprint**

The study follows a controlled comparison methodology. For every tier $T(n)$, the key performance and economic metrics, such as the fine-grained progress rate ($\\mathbf{R\_{Prog}}$) and Cost-of-Pass (CoP), must be compared directly against $T(n-1)$. This approach precisely quantifies the marginal utility—the performance gained per unit of architectural complexity—of the newly introduced feature. For example, comparing the performance and cost of T3 (Tooling) against T2 (Skills) isolates the economic impact of heavy JSON schema loading versus internalized prompt expertise.12

The systematic analysis requires executing runs where specific architectural components are deliberately removed.2 For instance, testing the T5 architecture with and without the Monitor function (the self-verification step) allows for the isolation and quantification of the precise cost-benefit of integrating an iterative self-correction loop into the planning process.5

### **3.3. Mitigating Strategic Drift and Ensuring Process Quality**

For multi-step, long-horizon agents, maintaining coherence over an extended operation is paramount. A key challenge is "strategic drift," where an agent's intermediate actions veer off-track from the intended goal over many steps.20 The experimental protocol must quantify this drift by checking the intermediate outputs against the ultimate objective. If, after numerous steps, an agent's actions correlate poorly with improving the desired metric, a planning failure has occurred, requiring further diagnosis facilitated by the $\\mathbf{R\_{Prog}}$ metric.20

For architectures involving complex delegation (T4/T5), quality must be enforced throughout the workflow. Robust multi-agent systems often incorporate a **dual-audit mechanism** to ensure the stability and quality of sub-task completion before integration.19 Implementing such a mechanism for the T5 architecture will directly confirm the efficacy of the embedded Monitor/Evaluator loop and validate whether the high cost of iterative verification translates into genuinely higher quality output stability.

## **4\. Efficacy Metrics and Quality Assessment**

Efficacy evaluation must be multi-faceted, encompassing not only the final result but also the quality of the generative process and the maintainability of the artifacts produced.

### **4.1. Core Completion and Process Metrics**

The following metrics are foundational for technical assessment:

* **Full Completion Score ($\\mathbf{S\_{Full}}$):** The binary or scalar measure defining the eventual goal completion ability of the agent.8
* **Fine-Grained Progress Rate ($\\mathbf{R\_{Prog}}$):** Captures incremental advancements, providing analytical evaluation and interpretability into the agent's step-by-step capabilities and limitations.6
* **Latency:** The average time from the initial query submission to the resolution of the task.20 This metric is critical for quantifying the operational penalty incurred by iterative architectures (T5), where the verification loop significantly adds to the response time.5
* **Consistency and Determinism:** Measures the stability of the agent’s output quality or format when faced with identical or highly similar inputs.20 This is particularly relevant for T6, where structured output commands are introduced to improve reliability.21

### **4.2. Fine-Grained Quality Validation (Hybrid Framework)**

To assess the quality of agent-generated artifacts (e.g., code or detailed documents), a hybrid evaluation framework is required, combining automated functional testing with semantic verification.23

* **Pass-Rate:** Functional quality is determined by automated test-case-based assessment (e.g., running a Pytest suite on agent-generated code).23
* **Implementation Rate (Impl-Rate):** This is the primary success metric for assessing semantic alignment with requirements. An LLM (acting as an "autorater" or Judge, e.g., Gemini-2.5-Pro) is used to verify the generated artifact against the original requirements document, performing a binary classification for each requirement.23 This method captures qualitative and subjective requirement satisfaction that functional tests may miss.
* **Deterministic Validation:** For structured outputs such as code, JSON, or SQL, programmatic checks are vital to verify format and structure (e.g., confirming non-null values, valid JSON structure, or correct API call signatures).21

### **4.3. DevOps Quality Proxies (Measuring Stability and Maintainability)**

An agent's success is not just defined by its ability to complete a task, but by the long-term stability and maintainability of its output. For generative tasks like code development, industry-standard DevOps metrics must be applied:

* **Change Fail Percentage (CFP):** This metric measures the percentage of production changes (resulting from agent output) that cause a failure in service, requiring immediate remediation such as a rollback or hotfix.29 If highly complex architectures (T5), which incur high cost for iterative refinement, achieve a high Impl-Rate but also exhibit a high CFP, this suggests the generated artifacts are brittle and high-maintenance, providing a critical counter-evidence against raw efficacy claims.
* **PR Revert Rate:** A quantitative metric captured in real-time, tracking the frequency with which agent-generated changes are discarded or reverted by human reviewers due to quality or architectural concerns.29

Table 4.1: Quality and Process Efficacy Metrics

| Metric | Category | Definition and Rationale | Ablation Focus |
| :---- | :---- | :---- | :---- |
| Implementation Rate (Impl-Rate) | Quality (Semantic) | Requirements met, verified by LLM-as-Judge.23 | Measures true requirement satisfaction for T2/T5 architectures. |
| Fine-Grained Progress Rate ($\\mathbf{R\_{Prog}}$) | Process | Captures incremental steps and trajectory coherence.8 | Discerning strategic drift and planning success in T4/T5.20 |
| Change Fail Percentage (CFP) | Stability | Percentage of successful outputs requiring immediate remediation.30 | Quantifying the long-term reliability and stability penalty of complex architectures. |
| Latency | Efficiency | Average time from query initiation to resolution.20 | Quantifies the penalty of iterative verification in T5.5 |

## **5\. Economic Sustainability and Cost Modeling**

For AI systems to achieve widespread adoption, they must demonstrate the ability to generate economic value that substantially outweighs their inference costs.25 This project adopts a robust framework grounded in production theory to evaluate this crucial trade-off.

### **5.1. Operational Cost Floor and Granular Tracking**

Accurate economic analysis requires granular cost monitoring. Since commercial LLM providers charge different rates for input and output tokens, dynamic cost management is essential.31

* **Dynamic Cost Calculation:** The system must calculate the cost of a single unit of work by determining the number of tokens consumed for a typical user action and applying the upstream provider’s differential pricing model for input and output tokens.31
* **Component-Level Cost Breakdown:** To analyze the architectural overhead, costs must be tracked at the component level.33 This is vital for isolating the contribution of specific modules, such as the massive schema overhead introduced by T3's Tooling 14 or the token consumption of the Critic’s verification loop in T5.5 Detailed breakdowns, including Total Cost, Total Tokens, and Average Cost/Token, must be collected and visualized over time.33

### **5.2. The Cost-of-Pass (CoP) Framework**

The core economic metric for this study is the **Cost-of-Pass (CoP)**, defined as the expected monetary cost required to generate a correct solution.25 CoP integrates both the cost of inference and the accuracy ($R\_m(p)$) of the model, establishing a comprehensive measure of cost-efficiency.

Mathematically, CoP incorporates the inherent stochasticity of LLMs, mirroring principles from classical economic production theory where the cost of achieving a specific target output is assessed.34 If an agent architecture consistently fails on a problem, meaning its accuracy ($R\_m(p)$) is zero, the Cost-of-Pass mathematically becomes infinite, signaling the economic infeasibility of that solution for the given task.26

The Cost-of-Pass analysis serves as the principled tool for measuring progress and guiding deployment decisions. A major economic assessment derived from CoP analysis involves comparing architectural complexity against foundational model capability. Specifically, the study must determine if the marginal accuracy gains provided by complex, iterative inference-time techniques (such as the self-refinement in T5) actually justify their accrued costs, or if cost-efficiency is better driven by leveraging a more capable, though possibly more expensive, underlying LLM base model with a simpler prompt (T1).34 The CoP framework provides the objective measurement required to determine whether architectural sophistication or intrinsic model innovation is the primary driver of value.

Finally, the sustainability of the agent architecture is only validated when its cost-efficiency is compared against the human expert alternative. The project must calculate the **LM Frontier Cost-of-Pass**, defined as the minimum CoP achievable across all tested architectural tiers ($T0-T6$).26 This frontier cost is then compared to the approximate cost of hiring a human expert.25 True economic success mandates that the agent’s economic benefit outweighs the labor costs it replaces or optimizes.35 For an AI agent to justify its existence as an economic asset, its resolution rate must exceed the proportional human performance threshold.35

Table 5.1: Economic Sustainability and Cost Metrics

| Metric | Calculation Focus | Purpose and Economic Insight | Relevant Tier Analysis |
| :---- | :---- | :---- | :---- |
| Cost-of-Pass (CoP) | $\\frac{\\text{Cost}}{\\text{Accuracy}}$ 34 | Determines the expected cost of one correct solution, linking cost to efficacy. | Primary comparative metric for T0-T6 viability. |
| Frontier CoP | $\\min(CoP)$ across all models/tiers 26 | Measures the state-of-the-art minimum cost to solve a problem compared to human labor. | Establishes the economic threshold for project success. |
| Avg. Cost per Output Token | Total Cost / Total Output Tokens 31 | Operational efficiency, crucial for dynamic cost management.32 | Highlights the inefficiency caused by T3 schema loading.12 |
| Token Distribution Cost | Component-specific cost breakdown 33 | Isolates cost drivers (e.g., Critic, Tool Schema, Orchestrator). | Guides targeted optimization (e.g., model distillation for Monitor role).5 |

## **6\. Implementation Status and Future Work**

### **6.1. Currently Implemented Metrics**

The following metrics are **fully implemented** in both the metrics calculation layer (`scylla/metrics/`) and analysis pipeline (`scylla/analysis/`):

**Quality Metrics:**

* **Pass-Rate**: Functional test coverage (automated test-based assessment)
* **Implementation Rate (Impl-Rate)**: Semantic requirement satisfaction (LLM-as-Judge verification)
* **Score**: Overall performance score based on grading rubric
* **Consistency**: Output stability measured as 1 - Coefficient of Variation (1-CV)

**Economic Metrics:**

* **Cost-of-Pass (CoP)**: Expected cost per correct solution
* **Frontier CoP**: Minimum CoP across all tiers
* **Token Distribution**: Component-level cost breakdown (input/output/total tokens)
* **Cost per Token**: Average cost per input/output token

**Process Metrics:**

* **Latency**: Time from query initiation to resolution
* **Judge Agreement**: Inter-rater reliability using Krippendorff's alpha

### **6.2. Metrics Defined but Not Yet Integrated**

The following metrics are **implemented** in `scylla/metrics/process.py` but **not yet integrated** into the analysis pipeline (`scylla/analysis/`):

**Process Metrics (Future Integration):**

* **Fine-Grained Progress Rate (R_Prog)**: Incremental advancement tracking through expected steps
  * Implementation: `scylla/metrics/process.py:calculate_r_prog()`
  * Status: Data structures defined (ProgressTracker, ProgressStep), calculation functions complete
  * Integration needed: Add to dataframes.py, loader.py, and create analysis figures/tables

* **Change Fail Percentage (CFP)**: Stability metric for production changes requiring remediation
  * Implementation: `scylla/metrics/process.py:calculate_cfp()`
  * Status: Data structures defined (ChangeResult), calculation functions complete
  * Integration needed: Add to dataframes.py, loader.py, and create comparison tables

* **PR Revert Rate**: Frequency of agent-generated changes reverted by human reviewers
  * Implementation: `scylla/metrics/process.py:calculate_pr_revert_rate()`
  * Status: Uses ChangeResult dataclass, calculation functions complete
  * Integration needed: Add to dataframes.py, loader.py, and create quality analysis tables

**Strategic Drift:**

* Defined in research methodology (Section 4.1) as goal coherence over multi-step tasks
* Implementation: Partially covered by ProgressStep.goal_alignment field
* Status: Needs dedicated calculation function and integration

**S_Full (Full Completion Score):**

* Mentioned in assessment but not fully defined in research.md or implemented
* Status: Requires specification before implementation

### **6.3. Future Work Recommendations**

1. **Integrate Process Metrics** (R_Prog, CFP, PR Revert Rate):
   * Extend `run_result.json` schema to include process tracking data
   * Update `loader.py` to extract process metrics from experiment results
   * Add columns to `runs_df` in `dataframes.py`
   * Create dedicated figures (e.g., Fig_RProg: Progress Rate by Tier)
   * Add to comparison tables (e.g., Table_CFP: Change Fail Percentage Analysis)

2. **Advanced Statistical Modeling**:
   * Implement Hierarchical Bayesian Generalised Linear Models (HiBayES) for multi-level data structure
   * Account for asymmetric and nested evaluation data (domains, subdomains, repetitions)
   * Ensure statistically sound conclusions about complexity and difficulty effects

3. **Power Analysis**:
   * Add statistical power reporting to comparison tables
   * Ensure sufficient sample sizes for detecting meaningful effect sizes

4. **Multi-Experiment Support**:
   * Enhance rubric conflict handling when loading multiple experiments
   * Add multi-experiment comparison tables

## **7\. Conclusion and Strategic Research Recommendations**

The rigorous implementation of the Incremental Capability Matrix and the Cost-of-Pass framework will yield definitive data on the architectural efficacy and economic sustainability of LLM agents.

The core outcome of the analysis will be the identification of the **Point of Diminishing Returns**. This is the specific complexity tier (likely T4 or T5) where the marginal increase in architectural complexity leads to an exponentially rising Cost-of-Pass that is not proportionally justified by the incremental gain in the Implementation Rate (Impl-Rate) or a decrease in the Change Fail Percentage (CFP). The study will quantify the trade-off between the high cost of iterative processes (T5 Monitor loop) and the quality stability provided by those processes.

The analysis must specifically validate the utility of distributed cognition, confirming whether the specialization inherent in **Atomic Task Design** (T4) successfully offsets the communication and orchestration overhead associated with multi-agent systems, providing a significant reduction in latency and cost compared to single, generalist approaches.17

The strategic recommendation for future deployment will be based on the **T6 hybrid blueprint** that achieves the lowest Frontier Cost-of-Pass. This blueprint will likely favor token-efficient approaches, such as incorporating prompt-encoded Skills (T2) and utilizing Agentic RAG in combination with specialized, delegated agents (T4), providing a quantitative basis that this configuration provides economic value surpassing the estimated human expert baseline.

Finally, the complexity of evaluating hierarchically nested agentic data—where performance metrics are gathered across multiple domains, subdomains, and repetitions—requires advanced statistical treatment.36 For future research, it is recommended to adopt statistical frameworks such as Hierarchical Bayesian Generalised Linear Models (HiBayES) to provide a robust statistical analysis that properly accounts for the asymmetric and multi-level structure of the generated evaluation data.36 This advanced modeling will ensure that conclusions regarding the effects of complexity and difficulty are statistically sound.

### **Works cited**

1. What are AI Agents? \- Artificial Intelligence \- AWS, accessed December 12, 2025, [https://aws.amazon.com/what-is/ai-agents/](https://aws.amazon.com/what-is/ai-agents/)
2. AmirLayegh/agentic-ablation: Automated neural network ablation studies using LLM agents and LangGraph. Systematically remove components, test performance, and gain insights into architecture importance through an intelligent multi-agent workflow. \- GitHub, accessed December 12, 2025, [https://github.com/AmirLayegh/agentic-ablation](https://github.com/AmirLayegh/agentic-ablation)
3. Modular LLM-Agent Architecture \- Emergent Mind, accessed December 12, 2025, [https://www.emergentmind.com/topics/modular-llm-agent-architecture](https://www.emergentmind.com/topics/modular-llm-agent-architecture)
4. Hierarchical Agentic Taxonomy \- Emergent Mind, accessed December 12, 2025, [https://www.emergentmind.com/topics/hierarchical-agentic-taxonomy](https://www.emergentmind.com/topics/hierarchical-agentic-taxonomy)
5. Zero-shot 3D Map Generation with LLM Agents: A Dual-Agent Architecture for Procedural Content Generation \- arXiv, accessed December 12, 2025, [https://arxiv.org/html/2512.10501v1](https://arxiv.org/html/2512.10501v1)
6. AgentBoard: An Analytical Evaluation Board of Multi-turn LLM ..., accessed December 12, 2025, [https://openreview.net/forum?id=4S8agvKjle](https://openreview.net/forum?id=4S8agvKjle)
7. \[2401.13178\] AgentBoard: An Analytical Evaluation Board of Multi-turn LLM Agents \- arXiv, accessed December 12, 2025, [https://arxiv.org/abs/2401.13178](https://arxiv.org/abs/2401.13178)
8. TheAgentCompany: Benchmarking LLM Agents on Consequential Real World Tasks \- arXiv, accessed December 12, 2025, [https://arxiv.org/html/2412.14161v2](https://arxiv.org/html/2412.14161v2)
9. The unreasonable effectiveness of large language models in zero-shot semantic annotation of legal texts \- Frontiers, accessed December 12, 2025, [https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2023.1279794/full](https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2023.1279794/full)
10. Agentic AI Frameworks: A Quick Comparison Guide \- Arkon Data, accessed December 12, 2025, [https://www.arkondata.com/en/post/agentic-ai-frameworks-a-quick-comparison-guide](https://www.arkondata.com/en/post/agentic-ai-frameworks-a-quick-comparison-guide)
11. Effective context engineering for AI agents \- Anthropic, accessed December 12, 2025, [https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
12. Skills vs Tools for AI Agents: Production Guide \- Arcade Blog, accessed December 12, 2025, [https://blog.arcade.dev/what-are-agent-skills-and-tools](https://blog.arcade.dev/what-are-agent-skills-and-tools)
13. Review of Tools for Zero-Code LLM Based Application Development \- arXiv, accessed December 12, 2025, [https://arxiv.org/html/2510.19747v1](https://arxiv.org/html/2510.19747v1)
14. Token-Efficient Agent Architecture | by Bijit Ghosh | Nov, 2025 \- Medium, accessed December 12, 2025, [https://medium.com/@bijit211987/token-efficient-agent-architecture-6736bae692a8](https://medium.com/@bijit211987/token-efficient-agent-architecture-6736bae692a8)
15. Self-Resource Allocation in Multi-Agent LLM Systems \- arXiv, accessed December 12, 2025, [https://arxiv.org/html/2504.02051v1](https://arxiv.org/html/2504.02051v1)
16. LLM Multi-Agent Systems: Challenges and Open Problems \- arXiv, accessed December 12, 2025, [https://arxiv.org/html/2402.03578v2](https://arxiv.org/html/2402.03578v2)
17. Optimizing Latency and Cost in Multi-Agent Systems \- HockeyStack, accessed December 12, 2025, [https://www.hockeystack.com/applied-ai/optimizing-latency-and-cost-in-multi-agent-systems](https://www.hockeystack.com/applied-ai/optimizing-latency-and-cost-in-multi-agent-systems)
18. InfiAgent: Self-Evolving Pyramid Agent Framework for Infinite Scenarios \- ResearchGate, accessed December 12, 2025, [https://www.researchgate.net/publication/395943748\_InfiAgent\_Self-Evolving\_Pyramid\_Agent\_Framework\_for\_Infinite\_Scenarios](https://www.researchgate.net/publication/395943748_InfiAgent_Self-Evolving_Pyramid_Agent_Framework_for_Infinite_Scenarios)
19. paperscope/AIConf · Datasets at Hugging Face, accessed December 12, 2025, [https://huggingface.co/datasets/paperscope/AIConf](https://huggingface.co/datasets/paperscope/AIConf)
20. AI Agent Evaluation: Frameworks, Strategies, and Best Practices \- Medium, accessed December 12, 2025, [https://medium.com/online-inference/ai-agent-evaluation-frameworks-strategies-and-best-practices-9dc3cfdf9890](https://medium.com/online-inference/ai-agent-evaluation-frameworks-strategies-and-best-practices-9dc3cfdf9890)
21. LLM evaluation metrics and methods, explained simply \- Evidently AI, accessed December 12, 2025, [https://www.evidentlyai.com/llm-guide/llm-evaluation-metrics](https://www.evidentlyai.com/llm-guide/llm-evaluation-metrics)
22. Agentic RAG: Architecture, Use Cases, and Limitations \- Vellum AI, accessed December 12, 2025, [https://www.vellum.ai/blog/agentic-rag](https://www.vellum.ai/blog/agentic-rag)
23. \[Literature Review\] Benchmarking and Studying the LLM-based Agent System in End-to-End Software Development \- Moonlight, accessed December 12, 2025, [https://www.themoonlight.io/review/benchmarking-and-studying-the-llm-based-agent-system-in-end-to-end-software-development](https://www.themoonlight.io/review/benchmarking-and-studying-the-llm-based-agent-system-in-end-to-end-software-development)
24. BenchAgents: Multi-Agent Systems for Structured Benchmark Creation \- arXiv, accessed December 12, 2025, [https://arxiv.org/html/2410.22584v2](https://arxiv.org/html/2410.22584v2)
25. mhamzaerol/Cost-of-Pass: Cost-of-Pass: An Economic ... \- GitHub, accessed December 12, 2025, [https://github.com/mhamzaerol/Cost-of-Pass](https://github.com/mhamzaerol/Cost-of-Pass)
26. COST-OF-PASS: AN ECONOMIC FRAMEWORK FOR EVALUATING LANGUAGE MODELS \- OpenReview, accessed December 12, 2025, [https://openreview.net/pdf?id=vC9S20zsgN](https://openreview.net/pdf?id=vC9S20zsgN)
27. Benchmarking and Studying the LLM-based Agent System in End-to-End Software Development \- arXiv, accessed December 12, 2025, [https://arxiv.org/html/2511.04064](https://arxiv.org/html/2511.04064)
28. A Practical Guide for Evaluating LLMs and LLM-Reliant Systems \- arXiv, accessed December 12, 2025, [https://arxiv.org/html/2506.13023v1](https://arxiv.org/html/2506.13023v1)
29. Three metrics for measuring the impact of AI on code quality \- DX, accessed December 12, 2025, [https://getdx.com/blog/3-metrics-for-measuring-the-impact-of-ai-on-code-quality/](https://getdx.com/blog/3-metrics-for-measuring-the-impact-of-ai-on-code-quality/)
30. How to measure Change failure rate? \- Codacy | Blog, accessed December 12, 2025, [https://blog.codacy.com/how-to-measure-change-failure-rate](https://blog.codacy.com/how-to-measure-change-failure-rate)
31. LLM Inference Benchmarking: How Much Does Your LLM Inference Cost? | NVIDIA Technical Blog, accessed December 12, 2025, [https://developer.nvidia.com/blog/llm-inference-benchmarking-how-much-does-your-llm-inference-cost/](https://developer.nvidia.com/blog/llm-inference-benchmarking-how-much-does-your-llm-inference-cost/)
32. Kinde AI Token Pricing Optimization: Dynamic Cost Management for LLM-Powered SaaS, accessed December 12, 2025, [https://kinde.com/learn/billing/billing-for-ai/ai-token-pricing-optimization-dynamic-cost-management-for-llm-powered-saas/](https://kinde.com/learn/billing/billing-for-ai/ai-token-pricing-optimization-dynamic-cost-management-for-llm-powered-saas/)
33. LLM Cost Metrics | VoltAgent, accessed December 12, 2025, [https://voltagent.dev/voltops-llm-observability-docs/dashboard/llm-cost-overview/](https://voltagent.dev/voltops-llm-observability-docs/dashboard/llm-cost-overview/)
34. Cost-of-Pass: An Economic Framework for Evaluating Language Models \- arXiv, accessed December 12, 2025, [https://arxiv.org/html/2504.13359v1](https://arxiv.org/html/2504.13359v1)
35. Measuring the Real Economic Impact of AI Agents | by Daniel Rodríguez \- Medium, accessed December 12, 2025, [https://medium.com/sadasant/measuring-the-real-economic-impact-of-ai-agents-3f2b4296577c](https://medium.com/sadasant/measuring-the-real-economic-impact-of-ai-agents-3f2b4296577c)
36. HiBayES: Improving LLM evaluation with hierarchical Bayesian modelling | AISI Work, accessed December 12, 2025, [https://www.aisi.gov.uk/blog/hibayes-improving-llm-evaluation-with-hierarchical-bayesian-modelling](https://www.aisi.gov.uk/blog/hibayes-improving-llm-evaluation-with-hierarchical-bayesian-modelling)
