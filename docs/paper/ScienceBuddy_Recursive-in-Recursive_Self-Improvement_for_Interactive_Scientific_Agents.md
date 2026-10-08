<p align="center">
  <a href="ScienceBuddy_Recursive-in-Recursive_Self-Improvement_for_Interactive_Scientific_Agents_CN.md" title="查看中文版本"><b>🇨🇳 中文</b></a>
  &nbsp;&nbsp;|&nbsp;&nbsp;
  <span><b>English</b></span>
</p>

---

# ScienceBuddy: Recursive-in-Recursive Self-Improvement for Interactive Scientific Agents

Shuhan Xue1,* Jianyuan Zhong1,* Ziyuan Nan1,* Wenbin Li1 Zhaochen Yu1 Jinchao Ding1 Qiang Gao2,3,4,5 Pengyu Zhan6 Yuntong Zhang6 Tian Cheng6 Zhenfei Yin1,7,† Yingcheng Wu1,8,† Ling Yang1,9,†

###### Abstract

We introduce and release ScienceBuddy, an interactive scientific research workspace that brings continually improving scientific agents into researchers’ everyday workflows. ScienceBuddy supports researchers in carrying out scientific tasks while transforming their requests, feedback, and execution evidence into tasks and evaluation rubrics for continual learning. At its core is recursive-in-recursive self-improvement, a paradigm that couples harness evolution with model reinforcement learning: the inner recursion improves the harness with the model fixed, while the outer recursion trains the model under the improved harness. Harness evolution shapes training experience, and model learning creates new opportunities for harness adaptation. We present case studies of researcher interaction, harness refinement, and model learning, with the benchmark cases spanning four scientific task families. By releasing ScienceBuddy as a research product, we make this paradigm available to the scientific community and take a step toward discovery intelligence: scientific AI that advances through sustained collaboration with researchers and evolves alongside the research it supports.

*Equal contribution.*

*Corresponding authors.*

*“Agents will inhabit streams of experience, rather than short snippets of interaction.”* — Silver and Sutton, *Welcome to the Era of Experience* (2025) (Silver and Sutton, 2025, p. 2)

![](images/sciencebuddy-system-diagram.png)

*Figure 1: ScienceBuddy: a scientific workspace that learns through collaboration. Left: Scientific workspace. A multimodal workspace brings together documents, images, tables, and biological sequences with 224 tools across 22 functional modules, spanning genomics, molecular and cancer biology, pharmacology, bioimaging, literature retrieval, and database queries. Pluggable frontier models and agent harnesses support scientific analysis within this shared environment. Middle: Recursive-in-recursive self-improvement. Nested harness refinement and model learning are linked through scientific tasks and evaluation rubrics. Right: Researcher interaction. Researchers pose questions, inspect results, and refine requirements. These exchanges supply task objectives, evaluation criteria, and evidence for further improvement, connecting scientific collaboration to the next learning cycle.*

###### Contents

1. 1 Introduction
2. 2 ScienceBuddy 2.1 Scientific Workspace & Agent Harness Scientific tools and execution environments. Agent execution and researcher interaction. Modular infrastructure and pluggable harness. 2.2 Interaction Formulation and Learning Signals Interaction formulation. From collaboration to tasks and rubrics. Harbor tasks for post-training. 2.3 Inner Recursion: Feedback-guided Harness Improvement Feedback-guided diagnosis. Harness revision. Evaluation and recursive refinement. 2.4 Outer Recursion: Continual Model Reinforcement Learning Environment augmentation under an evolving harness. Task-adaptive rubric rewards. Model updates and renewed harness adaptation. 2.5 Coordinating Recursive-in-Recursive Improvement Nested update schedule. Cross-cycle experience and re-evaluation.
3. 3 Scientific Workspace and User Experience Scientific scope. Multimodal input and evidence inspection. Long-context agentic reasoning. Researcher interaction. Researcher inspection through interface controls.
4. 4 Case Studies 4.1 ScienceBuddy Interaction Setup. Refining a JAK1 investigation. Connecting evidence in an ARL4C study. From requests to task specifications. 4.2 Two-Cycle Recursive-in-Recursive Dynamics Setup. Learning dynamics across cycles. Scientific task performance. 4.3 Harness Adaptation with a Fixed Model Setup. Adaptation and validation performance. Learned procedures. 4.4 Model Learning with a Fixed Harness Setup. Learning dynamics and problem coverage.
5. 5 Related Work
6. 6 Conclusion
7. References
8. 7 Implementation Details 7.1 Datasets and Environments 7.2 Harness Evolution 7.3 Reinforcement Learning Fresh rollout groups. Group-relative policy objective. 7.4 Concrete Researcher Inputs 7.5 User Interface and Researcher Interaction
9. Organizations

## 1 Introduction

Scientific research proceeds through analysis, inspection, and revision. Language-model agents can assist by retrieving evidence, querying databases, and executing computational workflows (Huang et al., 2025; Wang et al., 2024; Laurent et al., 2024). Researchers then clarify assumptions, question conclusions, and request additional checks. These exchanges reveal how scientific work should be conducted and assessed, but correcting an answer within a conversation does not establish improvement across tasks. This motivates our central question: *How can a scientific agent turn collaboration with researchers into sustained improvements in its working procedures and underlying capabilities?*

Prior work establishes foundations for this problem. Reflection and harness optimization revise reusable instructions and execution procedures (Shinn et al., 2023; Agrawal et al., 2025; Zhang et al., 2025b; Lee et al., 2026); interaction-driven adaptation and rubric-based reinforcement learning provide mechanisms for model improvement (Wang et al., 2026a; Zweiger et al., 2025; Gunjal et al., 2025). Joint adaptation also has precedent: SIA updates both harnesses and model weights, including for single-cell RNA denoising (Hebbar et al., 2026), while HELIX connects harness evolution to model-training data construction (Fan and Huang, 2026). In science, AgentBuild constructs agents from scientist-authored rubrics, curricula, and knowledge bases (Shin et al., 2026). We investigate how *collaboration itself* can supply the tasks and assessment criteria that coordinate repeated procedural and policy learning.

We introduce ScienceBuddy, an interactive scientific research workspace for continual learning from researcher collaboration. Figure 2 provides an overview of the workspace, which combines scientific tools and reference resources (Huang et al., 2025) with data upload, executable analysis, persistent files, and inspectable traces and artifacts. Researchers refine their requests through dialogue, while a pluggable harness organizes model behavior through instructions, reusable skills, and context-management procedures. Separating this editable harness from the scientific infrastructure makes procedural changes explicit and evaluable. Requests, clarifications, execution records, and artifacts jointly establish task objectives, constraints, and success criteria. We consolidate these criteria into task-specific rubrics and package the corresponding instructions, inputs, and environments as executable Harbor tasks (7). Researcher replies inform these criteria without serving as unquestioned correctness labels. The resulting tasks support both procedural diagnosis and evaluation of fresh policy rollouts, using executable checks and fixed judges as appropriate.

On this foundation, we propose recursive-in-recursive self-improvement (Figure 2). The inner recursion holds the task model fixed while a separate, fixed auxiliary model diagnoses failures and proposes bounded edits to instructions, skills, or context settings. Candidates are accepted only when they satisfy edit constraints and improve paired development evaluation (Yang et al., 2026; Ma et al., 2026). Further execution supplies evidence for the next revision. The outer recursion calibrates augmented task environments against the current model and selected harness (Fan et al., 2026), then trains on fresh on-policy rollouts with task-specific rubric rewards and GRPO (Gunjal et al., 2025; Shao et al., 2024). The harness and rubrics remain fixed during training; historical interactions provide task definitions and diagnostic evidence rather than on-policy training samples.

The coupling is bidirectional: harness revisions shape training trajectories and task difficulty, while model updates change the effectiveness of inherited procedures. Background improvement proceeds alongside the online service. After re-evaluation, the updated model–harness pair returns to researchers, whose interactions initiate the next cycle. All harness and environment versions are retained for subsequent evolution. Thus, each outer cycle learns through an inner adaptation process and changes the model that participates in the next.

Our case studies examine real researcher interactions, harness revision with a fixed task model, and model learning with a fixed harness. The benchmark cases cover four task families from LAB-Bench and Biomni-Eval1: literature reading, database judgments, protocol troubleshooting, and gene and variant assessment (Laurent et al., 2024; Huang et al., 2025). Holding one component fixed provides a focused view of changes in the other: the harness case measures first-response accuracy on feedback-accessible evaluation tasks, while the model case measures problem coverage on a common panel under H0. These studies connect the proposed framework to observable improvements in scientific task execution.

We release ScienceBuddy as an interactive research product, bringing scientific assistance and continual capability improvement into a shared workspace for researchers. This release makes our proposed paradigm available to the scientific community and takes a step toward discovery intelligence, where scientific agents evolve through sustained collaboration with the researchers they support.

Contributions. Our contributions are fourfold: • A released scientific research workspace. We develop and release ScienceBuddy, an interactive product that helps researchers carry out scientific tasks by connecting researcher dialogue, executable analysis, inspectable artifacts, and a pluggable harness within a persistent workspace. • Interaction-grounded tasks and supervision. We formulate a workflow for deriving executable tasks and evaluation rubrics from collaboration, with validated environment augmentation calibrated to current capabilities. • Recursive-in-recursive self-improvement. We introduce a paradigm for model–harness co-design that couples evaluated harness evolution with rubric-supervised model reinforcement learning, returning the updated system to researchers for renewed interaction and adaptation. • Case-study evidence for procedural and model learning. We examine real researcher interactions, fixed-model harness evolution, and model learning under a fixed harness, relating the proposed framework to improved scientific task execution and broader problem coverage.

## 2 ScienceBuddy

ScienceBuddy is an interactive scientific research workspace that brings evidence access, computational analysis, and methodological guidance into a single conversational workflow. Researchers can introduce questions together with their data, inspect the resulting analyses, and refine the work through subsequent exchanges. Built on this foundation, ScienceBuddy supports *recursive-in-recursive self-improvement*: an inner process revises and evaluates the agent’s harness while keeping the task model fixed (Section 2.3), and an outer process applies continual reinforcement learning to trajectories generated under the evolving harness (Section 2.4). The updated model then returns to further harness adaptation, coupling improvements in working procedures with improvements in the model that executes them (Section 2.5). Figure 2 summarizes the coupled harness and model improvement process.

### 2.1 Scientific Workspace & Agent Harness

We first describe three system components: scientific tools and execution environments, agent execution and researcher interaction, and modular infrastructure with a pluggable harness. Figure 2 summarizes the scientific workspace and researcher interaction.

#### Scientific tools and execution environments.

ScienceBuddy provides access to a catalog of 224 tools across 22 functional modules, spanning genomics, molecular and cancer biology, pharmacology, bioimaging, literature retrieval, and database queries. The runtime supports Python, R, and Bash execution, combining scientific libraries with data processing, statistical analysis, and visualization. Online database interfaces and a local data lake provide complementary access to biomedical evidence. Researcher-provided documents, tables, sequences, and images enter a persistent workspace that retains inputs, intermediate files, and generated outputs. Interface and environment details appear in Section 7.1. The scientific tool catalog and execution utilities are derived from Huang et al. (2025).

#### Agent execution and researcher interaction.

We follow a ReAct-style reasoning–action–observation loop (Yao et al., 2023), alternating reasoning, code or tool execution, and observation. Researchers submit questions, upload supporting data, and provide follow-up instructions through the Chat view. The Trajectory view presents the chronological execution record, an event timeline, and details of selected events. Compute and Results panels provide access to execution activity and generated artifacts. Conversation history and workspace files preserve task context across exchanges, allowing researchers to inspect the agent’s work and request revisions. Section 7.5 illustrates both interface views.

#### Modular infrastructure and pluggable harness.

ScienceBuddy separates the agent harness from the infrastructure that manages researcher interactions, task execution, and persistent workspaces. A common execution interface specifies the task context supplied to the harness and the responses and execution records returned to the platform. Alternative agentic harnesses can be integrated by implementing this interface, while sharing the same task-management and storage services. Within this architecture, instructions, skills, and selected context-management procedures constitute the editable components of the harness. Recursive improvement revises these components while keeping the surrounding infrastructure fixed, allowing changes in scientific problem-solving procedures to be evaluated under consistent execution conditions (Section 2.3).

### 2.2 Interaction Formulation and Learning Signals

#### Interaction formulation.

Let $x$ denote a research request and its inputs, $\pi_{\theta}$ the task model, $H$ the harness, and $h_{t}=(x,a_{0},o_{1},\ldots,a_{t-1},o_{t})$ the history, with $h_{0}=(x)$. An action $a_{t}$ is executable code, a tool call, or a researcher-facing response. The observation $o_{t+1}=(e_{t+1},u_{t+1})$ records environment output or execution status $e_{t+1}$ and an optional researcher reply $u_{t+1}$, with ut+1=⊥u_{t+1}=\bot when absent. The harness constructs model context $C_{H}(h_{t})$ from history, memory, skills, and tool descriptions. Allowing for a scheduled deterministic action $d_{H}(h_{t})$, such as input inspection, the joint policy and trajectory are $\displaystyle\mu_{\theta,H}(a\mid h_{t})$ $\displaystyle=\begin{cases}\delta_{d_{H}(h_{t})}(a),&\text{if a harness action is scheduled},\\ \pi_{\theta}(a\mid C_{H}(h_{t})),&\text{otherwise},\end{cases}$ (1) $\displaystyle a_{t}$ $\displaystyle\sim\mu_{\theta,H}(\cdot\mid h_{t}),\qquad\tau=(x,a_{0},o_{1},\ldots,a_{T-1},o_{T}).$ Here $\delta$ denotes a point mass and $T$ counts execution steps. A researcher-facing response may follow several tool steps; a tool observation alone does not constitute a researcher turn or user feedback.

#### From collaboration to tasks and rubrics.

The collaboration record supplies two complementary artifacts: a self-contained task and its evaluation rubric (Figure 3). Related turns are consolidated around a scientific objective, with independently solvable objectives separated. The task instruction preserves the final requirements and inputs without importing the historical answer. Unlike earlier task-only packaging followed by expert annotation, the current workflow also derives the rubric from the full collaboration trajectory: $$ \mathcal{C}(x)=\operatorname{ConstructRubric}\bigl(\tau_{x}^{\mathrm{collab}};I_{x},A_{x}\bigr), $$ (2) where $\tau_{x}^{\mathrm{collab}}$ is the source collaboration, $I_{x}$ the reconstructed instruction, and $A_{x}$ the required assets. Criteria cover task scope, methodological requirements, evidence, and expected artifacts. Conflicting requirements are resolved before scoring; historical answers and researcher approval are not automatically treated as scientific ground truth.

#### Harbor tasks for post-training.

The task package combines the instruction, input assets, execution environment $\mathcal{E}_{x}$, and rubric: $$ \mathcal{P}_{x}=\bigl(I_{x},A_{x},\mathcal{E}_{x},\mathcal{C}(x)\bigr). $$ (3) Instructions, configuration, assets, and rubric-based tests are organized as Harbor tasks (7). The same tasks support two post-training routes: SFT retains rubric-qualified generated trajectories through rejection sampling, while RL collects fresh on-policy rollouts and uses rubric scores as rewards. Input and runtime checks establish executability; rubric-based checks and a fixed judge assess scientific requirements. The rubric remains fixed within each post-training stage.

### 2.3 Inner Recursion: Feedback-guided Harness Improvement

At inner step $j$ of outer cycle $k$, the active harness $H_{k,j}$ is the *parent*, and its proposed revision $\widetilde{H}_{k,j+1}$ is a *candidate*. An accepted candidate becomes the *child* $H_{k,j+1}$. Otherwise, the parent remains active.

#### Feedback-guided diagnosis.

Within outer cycle $k$, the task-model parameters $\theta_{k}$ remain fixed. We use GPT-6 Astra as a separate, fixed auxiliary model for trajectory diagnosis and harness editing. It reviews recent trajectories and rubric evaluations, identifies unmet criteria, and cites the relevant actions and observations. Following evidence-based trajectory diagnosis (Barke et al., 2026), it maps these findings to a candidate procedural edit. Task-specific answers and newly supplied facts remain local to the task.

#### Harness revision.

Let $E_{k,j}$ contain the selected trajectories, rubric feedback, and edit history for harness $H_{k,j}$. The auxiliary model proposes a bounded update, $$ \widetilde{H}_{k,j+1}=U(H_{k,j},E_{k,j};\theta_{k}). $$ (4) Each proposal adds, removes, or revises one scoped skill, edits an instruction, or changes one exposed context setting, leaving other components unchanged (Liu et al., 2026; Yang et al., 2026). A schema check enforces the permitted edit scope and size budget. Tools, execution infrastructure, rubrics, and evaluators remain fixed. This is a procedural update; neither the task model nor the auxiliary model receives gradient updates.

#### Evaluation and recursive refinement.

Parent and candidate are evaluated on identical development tasks, seeds, and execution budgets using frozen task rubrics. Let $\bar{S}_{k}(H)$ be the mean normalized rubric score and $\mathrm{Valid}(H)$ indicate compliance with the edit constraints. Write $\Delta_{k,j}=\bar{S}_{k}(\widetilde{H}_{k,j+1})-\bar{S}_{k}(H_{k,j})$. The proposed acceptance rule is $$ H_{k,j+1}=\begin{cases}\widetilde{H}_{k,j+1},&\mathrm{Valid}(\widetilde{H}_{k,j+1})\ \land\ \Delta_{k,j}>0,\\ H_{k,j},&\text{otherwise}.\end{cases} $$ (5) Evaluation includes previously successful tasks to account for regressions (Ma et al., 2026), and ties retain the parent. Rejected edits and score changes remain in the optimizer’s history. The selected harness then executes new training tasks, whose trajectories supply evidence for the next revision. Iteration continues until the proposal budget or outer collection boundary is reached. Development tasks are separate from policy-training tasks and the final held-out test set, which never informs editing or selection.

### 2.4 Outer Recursion: Continual Model Reinforcement Learning

#### Environment augmentation under an evolving harness.

As the harness evolves, previously challenging tasks may become routine, reducing their value for further model training. We therefore calibrate environment difficulty through pilot execution with the current task model and selected harness. Following environment evolution (Fan et al., 2026), we augment researcher-derived tasks by varying scientific inputs and analysis conditions or extending dependencies between computational steps. The validated environments then supply fresh RL rollouts.

#### Task-adaptive rubric rewards.

For each task $x$, a fixed rubric composer derives task-specific criteria from the source collaboration trajectory and its reconstructed objective, inputs, and required outputs (Section 2.2), following task-adaptive rubric construction (Ding, 2026). The resulting rubric $\mathcal{C}(x)$ combines task-specific correctness checks with relevant evidence and artifact requirements. Each criterion has a nonnegative importance weight $w_{c}(x)$, assigned before rollout evaluation, and a satisfaction score $v_{c}(x,\tau)\in[0,1]$. We use executable checks where available and a fixed judge for criteria requiring scientific interpretation (Yu et al., 2026). Following rubric-based reward aggregation (Gunjal et al., 2025), the trajectory reward is $$ R_{x}(\tau)=\frac{\sum_{c\in\mathcal{C}(x)}w_{c}(x)\,v_{c}(x,\tau)}{\sum_{c\in\mathcal{C}(x)}w_{c}(x)},\qquad\sum_{c\in\mathcal{C}(x)}w_{c}(x)>0. $$ (6) Rubrics vary across tasks but remain fixed during optimization and paired harness evaluation. The terminal reward supplies a trajectory-level advantage shared across generated tokens. We use GRPO (Shao et al., 2024); its objective and implementation details are given in Section 7.3.

#### Model updates and renewed harness adaptation.

At outer cycle $k$, we maximize the expected trajectory reward under the selected harness: maxθJk(θ),Jk(θ)=𝔼x∼qk𝔼τ∼πθ,Hk⋆(⋅∣x)[Rx(τ)].\max_{\theta}J_{k}(\theta),\qquad J_{k}(\theta)=\mathbb{E}_{x\sim q_{k}}\mathbb{E}_{\tau\sim\pi_{\theta,H_{k}^{\star}}(\cdot\mid x)}\bigl[R_{x}(\tau)\bigr]. (7) Here $q_{k}$ is the training-task distribution over the validated seed environments and augmented variants at outer cycle $k$, and $\pi_{\theta,H_{k}^{\star}}$ is the trajectory distribution induced by the task model under the fixed harness $H_{k}^{\star}$. The GRPO update yields $\theta_{k+1}$. Because harness effectiveness depends on its interaction with the task model (Lee et al., 2026), we re-evaluate the selected harness under the updated model before deploying $(\theta_{k+1},H_{k+1})$, with $H_{k+1}=H_{k}^{\star}$. Researcher interactions with this pair provide evidence for the next inner-adaptation phase and outer update cycle (Section 2.5).

### 2.5 Coordinating Recursive-in-Recursive Improvement

#### Nested update schedule.

ScienceBuddy serves researchers with model $\theta_{k}$ and harness $H_{k}$ over a fixed collection interval. The resulting interactions and feedback initiate a background update cycle, asynchronous with the online service: harness improvement proceeds with $\theta_{k}$ fixed, followed by model RL under the selected harness. After re-evaluation, the updated model–harness pair is deployed to support increasingly demanding research tasks. Subsequent researcher interactions provide the evidence for the next cycle (Algorithm 1).

#### Cross-cycle experience and re-evaluation.

All harness versions and task environments are retained for subsequent evolution. Inherited harnesses are re-evaluated under the updated task model before deployment or reuse.

Algorithm 1 Recursive-in-recursive improvement with asynchronous online service 1: Initial $(\theta_{0},H_{0})$, collection interval $\Delta$, training environments $\mathcal{T}$, 2: development tasks, inner budgets $J_{k}$, RL budgets, and outer count $K$ 3: Initialize evidence buffer $\mathcal{B}$ and edit history $\mathcal{L}$; deploy $(\theta_{0},H_{0})$ 4: for $k=0,\ldots,K-1$ do 5: $E_{k}\leftarrow\operatorname{Collect}_{\Delta}(\theta_{k},H_{k})$; $\mathcal{B}\leftarrow\mathcal{B}\cup E_{k}$ 6: *Background updates; the online service continues with $(\theta_{k},H_{k})$.* 7: $H_{k,0}\leftarrow H_{k}$; evaluate $\bar{S}_{k}(H_{k,0})$; $j\leftarrow 0$ 8: while $j<J_{k}$ and the inner execution budget remains do 9: Append fresh task evidence under $(\theta_{k},H_{k,j})$ to $\mathcal{B}$ 10: $E_{k,j}\leftarrow\operatorname{Read}(\mathcal{B},\mathcal{L};H_{k,j})$ 11: $\widetilde{H}_{k,j+1}\leftarrow U(H_{k,j},E_{k,j};\theta_{k})$ $\triangleright$ Section 2.3 12: Validate and, if valid, evaluate $\widetilde{H}_{k,j+1}$ under paired development conditions 13: Select $H_{k,j+1}$ by Equation 5; record the decision in $\mathcal{L}$ 14: $j\leftarrow j+1$ 15: end while 16: $H_{k}^{\star}\leftarrow H_{k,j}$; $\mathcal{T}_{k}\leftarrow\operatorname{Augment}(\mathcal{T};\theta_{k},H_{k}^{\star})$ 17: $\theta_{k+1}\leftarrow\operatorname{RLUpdate}(\theta_{k};H_{k}^{\star},\mathcal{T}_{k},R)$ $\triangleright$ Section 2.4 18: Use fresh batches $\mathcal{D}_{k,t}$, Equations 6 and 10; retire batches after optimization. 19: $H_{k+1}\leftarrow H_{k}^{\star}$; re-evaluate $(\theta_{k+1},H_{k+1})$ 20: Retain all harness and environment versions; $\mathcal{T}\leftarrow\mathcal{T}\cup\mathcal{T}_{k}$ 21: Deploy $(\theta_{k+1},H_{k+1})$ 22: end for 23: return $(\theta_{K},H_{K})$

## 3 Scientific Workspace and User Experience

#### Scientific scope.

ScienceBuddy combines multimodal input, long-context agentic reasoning, and researcher interaction within a shared scientific workspace. Its document handling and execution interfaces support multiple scientific domains, while the current tools and data specialize in biomedicine. The following recorded session illustrates how researchers connect visual scientific material to target analysis, evidence retrieval, and further questions.

#### Multimodal input and evidence inspection.

Researchers can supply documents, tables, biological sequences, and images alongside natural-language requests. In Figure 4, an uploaded immune-signaling diagram guides the identification of molecular targets and the organization of related drug and pathway knowledge. The response connects visual entities to an evidence table, distinguishing a retrieved PDE4/rolipram fragment from CD40 and AHR searches that returned no matches. The conversation, input composer, and Compute panel bring the scientific material, response, and execution history into one inspectable view. Original interface captures appear in Section 7.5.

![Figure 4: A workspace for multimodal scientific analysis. A ](images/sciencebuddy-workspace-chat.png)

*Figure 4: A workspace for multimodal scientific analysis. A researcher supplies a scientific diagram and requests related knowledge. The Chat view connects visual interpretation to a structured target–evidence table, while the Compute panel exposes execution records. Retrieved evidence and gaps in the available data remain visible for researcher inspection. UI text and dialogue are reconstructed in English from the recording; uploaded figures retain their original appearance and language. Account and model identifiers are masked.*

#### Long-context agentic reasoning.

Figure 5 follows three image-based requests in a continuing session: an HMGCR Mendelian-randomization diagram, an Alzheimer’s-related microglial network, and an immune-signaling diagram. The agent interprets each image through reasoning, retrieval, and synthesis; the later execution explicitly resumes the same session with prior exchanges available. The trace records repeated data-lake searches and literature/protein queries; the middle response instead uses model knowledge without a new database query.

#### Researcher interaction.

The researcher directs the work by introducing new diagrams, changing the scientific focus, and explicitly requesting database evidence. Successive responses organize targets, distinguish pathways from cell-state markers, and identify data needed for further analysis. Retained dialogue and evidence support subsequent requests and the derivation of task objectives and evaluation criteria (Section 2.2).

![Figure 5: Multimodal input, long-context agentic reasoning, ](images/sciencebuddy-workspace-long-trajectory.png)

*Figure 5: Multimodal input, long-context agentic reasoning, and researcher interaction. Three successive image-based requests direct target analysis across a continuing scientific session. Uploaded diagrams, assistant interpretations, and evidence tables are paired with the recorded execution history, showing how researcher direction and retained context connect successive rounds of work. Proposed analyses are not executed experiments. English dialogue and UI are reconstructed from recorded moments; uploaded figures retain their original language, omitted events are marked, and identifiers are masked.*

#### Researcher inspection through interface controls.

Researcher interaction also includes navigation and inspection actions beyond conversational input (Figure 6). In the demonstration, the researcher opens an uploaded diagram at a larger scale, switches from Chat to Trajectory, and selects a tool event to inspect its metadata, input, and output. The selected UniProt event exposes an earlier HMGCR lookup while later requests remain in the same session. These controls let the researcher examine source material, follow the execution history, and revisit the basis of a response without starting a new conversation.

![Figure 6: Researcher inspection beyond the conversation. Ope](images/sciencebuddy-researcher-inspection.png)

*Figure 6: Researcher inspection beyond the conversation. Opening an uploaded image reveals its scientific details; switching to Trajectory exposes the execution history; selecting a tool event opens its input, output, and metadata. The example revisits an earlier HMGCR protein lookup within the continuing session. English interface reconstructions highlight controls used in the recording; the uploaded diagram and timeline retain source pixels. Cursor markers indicate the inspected controls.*

## 4 Case Studies

We present four distinct case studies of ScienceBuddy’s scientific assistance and self-improvement. Each addresses a separate research question:

RQ1: Researcher interaction. How does researcher feedback guide scientific assistance and reveal task objectives and evaluation criteria? (Section 4.1) RQ2: Coupled Recursive-in-Recursive improvement. Can alternating harness refinement and model learning sustain improvement across cycles and broaden scientific task performance? (Section 4.2) RQ3: Harness adaptation. Can harness adaptation improve scientific task performance without changing model weights? (Section 4.3) RQ4: Model learning. Can reinforcement learning expand scientific problem-solving capability under a fixed harness? (Section 4.4)

### 4.1 ScienceBuddy Interaction

#### Setup.

We examine two real researcher interactions with deployed ScienceBuddy. Requests, supplied materials, agent responses, and subsequent researcher input support a qualitative assessment of scientific assistance and opportunities for reinforcement learning (RL) task construction. Readers interested in the concrete researcher wording can consult Figure 11 in the appendix.

#### Refining a JAK1 investigation.

A researcher asked ScienceBuddy to design a study of JAK1, immunotherapy outcomes, and the immune microenvironment in small-cell lung cancer using public single-cell transcriptomes and IMpower133 bulk RNA data. In response to the scope refinement (Figure 11a), ScienceBuddy organized a gene-specific plan with treatment-by-JAK1 interaction tests, patient-level expression summaries within cell types, and immune-state signatures. The plan assigned Seurat/Scanpy to single-cell analysis, UCell/AUCell to signature scoring, and CellChat/NicheNet to subsequent cell-communication analyses. This plan distinguished treatment-effect modification from prognosis and prioritized mechanistic follow-up.

#### Connecting evidence in an ARL4C study.

A researcher requested a presentation connecting the background and results of an ARL4C study, then specified panel selection, conclusions, mechanism schematics, and speaker notes (Figure 11b). Using text and figure captions organized through Python/PyPDF2, ScienceBuddy linked candidate screening to cellular and molecular evidence. It highlighted depletion and conditional knockout comparisons for cellular attribution, blockade for functional dependence, and kinetic and rescue assays for molecular interpretation. Panel-selection rationales and notes linked each scientific claim to its supporting comparison.

#### From requests to task specifications.

These cases illustrate how researcher requirements translate into task objectives, evaluation criteria, and required artifacts (Figure 7). The JAK1 refinement yields a study-planning objective whose criteria preserve gene-specific scope and place association analyses before mechanistic follow-up. The ARL4C request yields a presentation objective whose criteria link claims to supporting panels and comparisons, with conclusions and speaker notes accompanying the slide outline. Such task specifications provide the basis for the trajectory-derived rubrics and post-training tasks described in Section 2.2.

### 4.2 Two-Cycle Recursive-in-Recursive Dynamics

#### Setup.

Starting from Qwen3.5-4B and an initial scientific-agent harness, we run three successive co-evolution cycles, indexed by $k=0,1,2$. In cycle $k$, harness refinement starts from $(\theta_{k},H_{k})$, keeps the model fixed, and performs 10 search steps to select $H_{k}^{\star}$ by validation accuracy. Model learning then performs 20 RL updates under the selected harness. The final checkpoint $\theta_{k+1}$ and selected harness $H_{k+1}=H_{k}^{\star}$ are carried into the next cycle, where inherited harnesses are reassessed under the updated model. This repeated exchange allows improvements in the model and harness to carry forward, supporting continued system improvement across successive cycles. Dataset and environment details are provided in Appendix 7.1; detailed experimental settings are deferred to the appendix.

#### Learning dynamics across cycles.

Figure 8(a) shows consistent improvements within each of the three cycles. Harness refinement increases validation accuracy from 38.9% to 44.4%, 34.4% to 46.7%, and 61.1% to 70.0% in the first, second, and third cycles, respectively. Over the same cycles, mean training reward rises from 33.3% to 38.8%, 44.1% to 60.5%, and 57.8% to 69.8% between the first and second halves of each RL phase. These gains show that both harness refinement and model training continue to improve their respective metrics over repeated cycles.

#### Scientific task performance.

Figures 8(b,c) summarize the improvement in held-out scientific task performance. Overall single-attempt test accuracy increases from 42.2% to 73.3%. Among all test problems, 33.3% transition from incorrect to correct, whereas 2.2% transition from correct to incorrect. The subset comparison shows gains across all four task families. These results indicate that improvement extends to previously unsolved problems, broadening the system’s scientific problem-solving capability.

The next two case studies evaluate harness adaptation and model learning independently, holding model weights or the harness fixed, respectively (Sections 4.3 and 4.4).

### 4.3 Harness Adaptation with a Fixed Model

#### Setup.

We refine and select the harness on an *adaptation set*, then compare the selected and initial harnesses on a separate *validation set*. Tasks from LAB-Bench and Biomni-Eval1 (Laurent et al., 2024; Huang et al., 2025) cover literature reading, database judgments, protocol troubleshooting, and gene and variant assessment. Implementation details appear in Section 7.2.

#### Adaptation and validation performance.

Figure 9a tracks first-response accuracy during harness adaptation: the fraction of tasks answered correctly on the first submission. Across 24 adaptation batches, the best observed batch accuracy reaches 75.0%. The selected harness is then evaluated on validation tasks, alongside the initial harness (Figure 9b). Validation accuracy increases from 31.1% to 51.1%, a gain of 20 percentage points with model weights fixed. This improvement demonstrates the effectiveness of revising the agent’s working procedures beyond the tasks used for adaptation and selection.

#### Learned procedures.

We inspect the selected harness to characterize the procedures retained from interaction. Its four instruction entries and nine scoped skills address Python execution, resource and schema inspection, bounded record lookup, and explicit answer submission. Task-specific procedures include gene-set membership checks, cytoband lookup, and database-specific evidence extraction. These procedures guide the agent in locating and checking scientific records, turning interaction evidence into reusable guidance for task execution. Section 7.2 describes the revisions and the limits of attributing gains to individual edits or feedback sources.

### 4.4 Model Learning with a Fixed Harness

#### Setup.

We keep the initial harness fixed throughout training and compare the model before and after RL under the same evaluation budget. The learning algorithm and evaluation protocol appear in Section 7.3.

#### Learning dynamics and problem coverage.

Training accuracy trends upward over approximately two hours of RL (Figure 10a). To assess whether learning also expands the range of solvable problems, we measure *problem coverage*: the fraction of test problems solved at least once within four attempts. Coverage increases from 48.3% before RL to 67.8% afterward (Figure 10b), a gain of 19.5 percentage points. With both the harness and attempt budget unchanged, the model solves a broader set of scientific problems, demonstrating the effectiveness of model learning as a distinct improvement mechanism.

## 5 Related Work

Persistent experience in agents. Reflexion retains verbal lessons in episodic memory, GEPA searches over prompts using trajectory reflection, and ACE incrementally maintains contextual playbooks (Shinn et al., 2023; Agrawal et al., 2025; Zhang et al., 2025b). Meta-Harness extends search to harness code using prior candidates and execution records, while PILOT learns reusable procedures during live execution (Lee et al., 2026; Xiao et al., 2026). These methods provide mechanisms for persistent procedural adaptation. ScienceBuddy studies how this adaptation generates experience for a second, model-level recursion.

Recursive self-improvement. The Darwin Godel Machine evolves an archive of agents, and Hyperagents makes the meta-level modification procedure part of the editable program (Zhang et al., 2025a; Zhang et al., 2026). SEAL generates data and update directives for parameter adaptation (Zweiger et al., 2025). ScienceBuddy instead studies a nested dependency between repeated harness adaptation and repeated task-model learning. Its reflector remains fixed, so improved task performance does not imply that the improvement mechanism itself has become stronger.

Learning from interaction. OpenClaw-RL extracts evaluative and directive signals from the states following agent actions, including user replies (Wang et al., 2026a). RLAnything jointly adapts environments, policies, and reward models (Wang et al., 2026b). ScienceBuddy studies how these learning processes interact with an evolving harness. User feedback guides procedural revision, while task verification supervises policy trajectories generated under the active harness. The learned model then returns to the next inner process, changing the conditions for further procedural adaptation.

## 6 Conclusion

ScienceBuddy provides an interactive scientific workspace in which researcher collaboration can inform both working procedures and model learning. Its recursive-in-recursive framework connects evaluated harness refinement with rubric-supervised model updates, returning the updated system to further scientific interaction. The case studies illustrate the complementary contributions of these components: researcher requests and follow-up requirements define scientific tasks and assessment criteria; harness revision improves first-response accuracy with the task model fixed; and model learning expands problem coverage under the initial harness. These findings support the framework’s procedural and model-learning mechanisms and provide a basis for studying their coordination across continued researcher collaboration.

## 7 Implementation Details

This appendix connects the case studies to the scientific workspace and recursive-in-recursive framework described in the main text. We distinguish the fixed-model harness-evolution run from the model-learning case under a fixed harness. The role specifications describe the information boundaries and procedural responsibilities of these components; the policy objective shows how model learning fits within the full recursive procedure.

### 7.1 Datasets and Environments

Task composition. The 895-task collection contains 96 LitQA2, 511 DbQA, 108 ProtocolQA, and 180 GWAS tasks. LitQA2 and ProtocolQA each have one subtopic, DbQA has ten, and GWAS has four, for 16 subtopics in total. Table 1 reports the number of tasks in each subtopic and the totals for each task family.

| Family | Subtopic | Count |
| --- | --- | --- |
| LitQA2 | Scientific literature reading | 96 |
| DbQA | Disease–gene associations | 39 |
|  | Gene location | 40 |
|  | miRNA targets | 40 |
|  | Mouse tumor gene sets | 80 |
|  | Oncogenic signatures | 40 |
|  | Transcription-factor binding (GTRD) | 40 |
|  | Variant annotation: single sequence | 80 |
|  | Variant annotation: multiple sequences | 72 |
|  | Vaccine-response gene sets | 40 |
|  | Viral protein interactions | 40 |
|  | Subtotal | 511 |
| ProtocolQA | Experimental protocol troubleshooting | 108 |
| GWAS | Causal genes: GWAS Catalog | 42 |
|  | Causal genes: Open Targets | 45 |
|  | Causal genes: PharmaProjects | 50 |
|  | Variant prioritization | 43 |
|  | Subtotal | 180 |
| Total | 16 subtopics | 895 |

Roles of the task sets. In the standalone harness case study, adaptation conversations guide procedural revisions and harness selection. The initial harness and the harness selected on this adaptation set are subsequently compared on a separate validation set. The model-learning case compares two model checkpoints on the same panel under the initial harness, with four attempts per problem. Dataset counts describe the task inventory; the 288 conversations reported for harness adaptation describe the executed adaptation stream. The real researcher interactions in Section 4.1 separately illustrate how scientific requests and follow-up requirements can define task contexts and rubrics.

### 7.2 Harness Evolution

Models and schedule. The reported harness run uses a fixed Qwen3.5-4B task model. A fixed Qwen3.8-27B helper supports bounded user simulation and feedback interpretation, while GPT-6 Astra proposes harness edits. After each batch of 12 task conversations, user feedback and execution evidence guide an update, giving 24 updates over 288 adaptation conversations. These conversations provide the feedback used for harness refinement; validation tasks are reserved for comparing the initial and adaptation-selected harnesses.

Editable procedures. The general harness interface permits instruction, skill, and selected context-management updates (Section 2.1). The reported case study restricts adaptation to instruction and scoped-skill text in a single-file harness. The execution loop, Python tool interface, context handling, input-inspection settings, submission checks, and budgets remain fixed. H0 starts without added instruction or skill entries; H24 contains four instruction entries and nine scoped skills. Each rollout executes a fixed source snapshot, with its harness version retained in the trajectory. The role specification below preserves the same instruction/skill-only edit boundary.

Revision and checkpoint selection. Proposed instruction or skill revisions pass component validation and a fixed execution preflight. The best-performing harness on the adaptation set is selected for the validation comparison; validation scores do not guide revision or checkpoint selection. On the validation set, the selected harness achieves 51.1% correct, compared with 31.1% for the initial harness. This standalone experiment’s selection protocol is distinct from validation-based harness selection in the coupled-cycle experiment.

Simulated feedback. The simulator receives correctness and submission-status verdicts and selects a permitted reply for the task family. Correct answers receive confirmation, missing submissions receive a format request, and incorrect answers receive a procedural check or revision request. The reply set excludes the correct option, identifier, and numerical answer. The feedback interpreter sees the reply and its public conversation context, but not the private verdict or answer. It classifies the reply as acceptance, correction, new information, new requirement, or ambiguity and records a supporting quote and a diagnostic score $q_{t}\in\{-1,0,+1\}$. These bounded replies provide controlled procedural feedback; the real researcher interactions in Section 4.1 illustrate the broader collaboration setting.

Diagnostic feedback and optimization reward. The score $q_{t}$ records how a follow-up relates to the preceding response and supports harness diagnosis. The field named reward in the interpreter specification denotes this diagnostic score. Policy optimization instead uses the separately evaluated trajectory reward $R_{x}(\tau)$ in Equation 6. Researcher feedback can inform a task’s objectives and rubric before evaluation; it does not replace assessment of the resulting rollout against those criteria. The GRPO advantage below is defined from $R_{x}(\tau)$, not by substituting the interpreter’s ternary score. Table 2 summarizes these information boundaries.

| Role | Public context | User next reply | Private answer | Verifier verdict |
| --- | --- | --- | --- | --- |
| Task policy | Visible prefix | After response | Hidden | Through bounded user feedback |
| User simulator | Review context | Produces reply | Hidden | Correctness and submission status |
| Feedback judge | Prior context | Observed reply | Hidden | Hidden |
| Harness reflector | Parent’s public trace | Observed reply | Hidden | Evaluation summaries |
| Scientific verifier | Required output | Not required | Private access | Produces verdict |
| Policy learner | Recorded policy input | Not backfilled | Not in prompt | Trajectory reward Rx​(τ)R_{x}(\tau) |

Reflection record and interpretation. GPT-6 Astra receives recent task trajectories, active procedures, rubric feedback, and relevant edit history, excluding private answers and evaluator internals. Each diagnosis links an unmet criterion to supporting actions or observations and a proposed procedural edit. The optimizer records the parent, candidate, model and environment versions, evaluation conditions, and acceptance decision. Rejected edits remain available for later diagnosis; stored versions are a history of decisions, not a frontier for parent sampling. The learning curves describe the combined effect of successive procedural revisions at fixed model weights. Effects of individual skills and feedback sources are not separately isolated.

Role prompt specifications. The following concise specifications explain the task interface, information boundaries, and edit scope of the harness-evolution case study. They are expository descriptions of the roles rather than byte-for-byte archived request payloads. Concrete requests also supply task inputs, conversation records, permitted replies, the parent harness, and the runtime’s edit schema. Private reference answers remain outside the policy and proposer inputs.

Task policy. You are a scientific assistant running in Science Buddy. You can reason and use Python in a persistent REPL. Public inputs are in /workspace/assets. The original task, including sequences, is in /workspace/assets/task_prompt.txt. Read long sequences from that file instead of copying them into generated code. Use the exact public filenames listed below. Python code must print results; bare expressions are not displayed. Scientific tool/data descriptions are in /opt/scitrace/TOOLS.md and /opt/scitrace/DATA.md. The available frozen data lake is mounted read-only at /opt/data/biomni_data/data_lake. Check which files and records exist before claiming database evidence. For a tool call, output one <execute>Python code</execute> block and wait for its result. Otherwise, reply to the researcher with a brief explanation and one <answer>value</answer> tag. Do not claim to have inspected evidence or executed code unless you actually did so. Respond to the researcher’s next reply, revising your work when warranted.

User simulator. Role-play a researcher reviewing the assistant’s ACTUAL response. This is a BOUNDED, REFERENCE-ASSISTED user simulator, not unrestricted expert feedback or a human trace. Choose the most useful and applicable reply from allowed_replies based on the conversation. The options request checks or confirm completion; none identifies the correct task answer. Do not add scientific claims, candidate names, numerical results or facts outside the allowed replies. The private correctness verdict concerns the selected answer, not every sentence of the explanation. Return JSON with reply equal to one allowed reply and done equal to answer_correct.

Feedback interpreter. You interpret feedback for trajectory diagnosis in an interactive scientific assistant. Use the user’s NEXT REPLY as evidence about the assistant’s PRECEDING response. You do not receive a reference answer or terminal verifier score. Do not guess one. Score +1 for explicit acceptance/confirmation; -1 for a correction or request to redo caused by an error, omission or unmet prior requirement; 0 for new requirements, newly supplied facts, unrelated follow-ups or insufficient evidence. A successful tool call is not user approval. A request to recheck or revise the same answer, or to supply an answer format already requested, is a correction (-1), not positive progression or a new requirement. Judge what the feedback says, not whether the user is scientifically correct. Return ONLY JSON with reward (-1,0,1), feedback_type (acceptance,correction,new_information, new_requirement,ambiguous), evidence (an EXACT substring of the user’s reply), and hint (a brief reusable improvement direction, empty when not supported). The reward field is the diagnostic feedback score, not the trajectory reward used for policy optimization.

Harness proposer: instruction/skill-only edits. Improve the scientific assistant’s instructions or scoped skills using the supplied parent harness and interaction evidence. Identify an unmet criterion, cite the relevant actions or observations, and propose one bounded procedural change: revise an instruction, or add, remove, or revise one scoped skill. Preserve all non-target entries and runtime settings. Return the revised harness using the supplied runtime schema and edit constraints; retain existing skills unless one is the target of the proposed change. Do not change context-history settings, input-inspection settings, tools, execution infrastructure, submission checks, budgets, rubrics, or evaluators. A complete serialized harness represents the local edit, not permission to rewrite every component. Avoid repeating rejected edits without new supporting evidence. Do not encode task-specific answers, numerical results, or sample IDs. A successful tool call does not prove scientific correctness; newly supplied information is not necessarily an error.

### 7.3 Reinforcement Learning

Case-study configuration. The task backbone is Qwen3.5-4B. In Section 4.4, the initial harness H0 remains fixed throughout model training and evaluation. Both model checkpoints are evaluated on the same problems with four attempts per problem, so the before/after comparison examines model learning under a common procedural interface. GPT-6 Astra is the diagnosis/editor model for harness adaptation (Section 7.2); this fixed-H0 case does not invoke a new harness-adaptation phase. It illustrates the model-learning component that can be coordinated with harness refinement in the full framework.

Evaluation measure. Training accuracy counts correctly solved attempts. Evaluation coverage, measured by pass@4, counts a problem once if at least one of its four attempts succeeds. The latter compares the breadth of solved problems under an equal attempt budget and is distinct from the first-response accuracy used in the harness case. The reported coverage rises from 48.3% to 67.8% under H0. The objective below formulates this model-learning step within the recursive framework.

#### Fresh rollout groups.

We express the model-learning component using the notation of the general recursive framework. During outer stage $k$, the selected harness $H_{k}^{\star}$ remains fixed while the task model is optimized. The model-only case in Section 4.4 holds this harness at H0 throughout its comparison. The case study instantiates a fixed-harness model-learning step, while Section 2.4 describes how selected harnesses and validated task environments can be incorporated across cycles. For each rollout batch, a frozen copy $\pi_{\mathrm{old}}$ of the current task policy generates $G$ trajectories per task. Records associate the model inputs, generated tokens, behavior log probabilities, task and rubric versions, and harness identifier with each trajectory. Fresh rollout groups supply the objective below; historical researcher interactions instead support task definition and procedural diagnosis. When a batch is reused for several optimizer passes, probability ratios remain relative to its original collection policy.

#### Group-relative policy objective.

The GRPO formulation (Shao et al., 2024) uses token-level averaging. For trajectory $i$, let $r_{i}=R_{x_{i}}(\tau_{i})$ denote its evaluated trajectory reward, distinct from the diagnostic feedback score $q_{t}$, and let $\mathcal{G}(i)$ contain trajectories generated for the same task under the same harness and rubric. The group-relative advantage is $$ \widehat{A}_{i}=\frac{r_{i}-\operatorname{mean}_{j\in\mathcal{G}(i)}r_{j}}{\operatorname{std}_{j\in\mathcal{G}(i)}r_{j}+\delta},\qquad\delta>0. $$ (8) All generated tokens in a trajectory share this advantage. Groups with identical rewards have zero policy-gradient advantage. Researcher messages, tool outputs, task instructions, and deterministic harness actions are excluded from the optimized tokens.

For generated token $b_{i,\ell}$ and its actual context $c_{i,\ell}$, define $$ \rho_{i,\ell}(\theta)=\frac{\pi_{\theta}(b_{i,\ell}\mid c_{i,\ell})}{\pi_{\mathrm{old}}(b_{i,\ell}\mid c_{i,\ell})}. $$ (9) For a minibatch $\mathcal{M}$ of complete groups, with $L_{i}$ generated tokens in trajectory $i$, the objective is $\displaystyle\mathcal{J}_{k}^{\mathrm{GRPO}}(\theta)=\frac{1}{\sum_{i\in\mathcal{M}}L_{i}}\sum_{i\in\mathcal{M}}\sum_{\ell=1}^{L_{i}}\Big[$ $\displaystyle\min\{\rho_{i,\ell}(\theta)\widehat{A}_{i},$ (10) $\displaystyle\operatorname{clip}(\rho_{i,\ell}(\theta),1-\epsilon,1+\epsilon)\widehat{A}_{i}\}-\beta\widehat{d}_{i,\ell}(\theta)\Big].$ Here $\epsilon>0$ controls clipping and $\beta\geq 0$ weights the sampled KL surrogate. The reference policy $\pi_{\mathrm{ref}}$ is a frozen copy of the task model at the start of the outer RL stage. Writing $z_{i,\ell}=\pi_{\mathrm{ref}}(b_{i,\ell}\mid c_{i,\ell})/\pi_{\theta}(b_{i,\ell}\mid c_{i,\ell})$, the surrogate is $\widehat{d}_{i,\ell}=z_{i,\ell}-\log z_{i,\ell}-1$. This sampled quantity is evaluated on behavior-policy tokens; it is not asserted to be an exact KL divergence under an updated policy.

The trajectory reward is computed after the rollout from its outputs and task-relevant execution evidence, with rubric and evaluator parameters fixed during optimization. It does not backfill later evaluation information into the contexts that generated earlier tokens. In the model-learning case study, both checkpoints are evaluated under H0 using the common pass@4 protocol. In the full recursive framework, the resulting checkpoint $\theta_{k+1}$ returns to harness re-evaluation and deployment, and subsequent researcher interactions initiate the next cycle (Section 2.5). The same policy-learning formulation thus serves the fixed-harness comparison and provides the model-update step of the full recursive procedure.

### 7.4 Concrete Researcher Inputs

The following excerpts reproduce the scope refinement and presentation requirements discussed in Section 4.1. They provide the concrete researcher wording underlying the illustrative task transformations in Figure 7.

### 7.5 User Interface and Researcher Interaction

Chat and task management. The Chat view combines a task sidebar, a conversational workspace, and panels for execution activity and generated results (Figure 12). Researchers can create or revisit a task, choose a starter prompt, or enter a question directly. The input composer accepts pasted or uploaded files and supports follow-up instructions within the same conversation. The Compute and Results tabs provide access to analysis activity and resulting artifacts.

![Figure 12: Chat view in ScienceBuddy. The task sidebar appea](images/research-interface-chat.png)

*Figure 12: Chat view in ScienceBuddy. The task sidebar appears on the left, starter prompts and the conversation area in the center, and Compute and Results tabs on the right. The input composer supports questions, file attachments, and model selection. This screenshot shows the initial task view before execution.*

Trajectory inspection. The Trajectory view exposes the ordered record of a task, including user messages, system events, context summaries, tool calls, and assistant responses (Figure 13). A timeline separates input, model, and tool activity. Selecting an event opens a detail pane with Summary, Payload, and Result tabs for inspecting its recorded content. Search and export controls support reviewing the record, while the conversation composer remains available for subsequent input.

![Figure 13: Trajectory view in ScienceBuddy. The timeline and](images/research-interface-trajectory.png)

*Figure 13: Trajectory view in ScienceBuddy. The timeline and event record expose the progression of an analysis, and the right-hand pane displays details of a selected event. The screenshot shows a recorded compound-property query, its tool activity, subsequent dialogue, and a selected context entry.*

## Organizations

1PhAI Labs

2Department of Hepatobiliary Surgery and Transplantation, Liver Cancer Institute, Zhongshan Hospital, Fudan University

3State Key Laboratory of Genetics and Development of Complex Phenotypes

4Fudan University

5Shanghai Academy of Natural Sciences

6Shunwei Capital

7University of Oxford

8Stanford University

9Princeton University

## References

- Agrawal et al. (2025) L. A. Agrawal, S. Tan, D. Soylu, N. Ziems, R. Khare, K. Opsahl-Ong, A. Singhvi, H. Shandilya, M. J. Ryan, M. Jiang, C. Potts, K. Sen, A. G. Dimakis, I. Stoica, D. Klein, M. Zaharia, and O. Khattab GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning. arXiv preprint arXiv:2507.19457. External Links: [Document](https://dx.doi.org/10.48550/arXiv.2507.19457), [Link](https://arxiv.org/abs/2507.19457) Cited by: §1, §5.
- Barke et al. (2026) S. Barke, A. Goyal, A. Khare, A. Singh, S. Nath, and C. Bansal AgentRx: Diagnosing AI Agent Failures from Execution Trajectories. arXiv preprint arXiv:2602.02475. External Links: [Link](https://arxiv.org/abs/2602.02475) Cited by: §2.3.
- Ding (2026) L. Ding AdaRubric: Task-Adaptive Rubrics for Reliable LLM Agent Evaluation and Reward Learning. arXiv preprint arXiv:2603.21362. External Links: [Link](https://arxiv.org/abs/2603.21362) Cited by: §2.4.
- Fan and Huang (2026) T. Fan and C. Huang HELIX: Model-Harness Co-evolution for Recursive Self-Improvement. arXiv preprint arXiv:2608.13951. External Links: [Link](https://arxiv.org/abs/2608.13951) Cited by: §1.
- Fan et al. (2026) Z. Fan, T. Yu, Y. Cai, J. Zhou, J. Guan, J. Liu, Y. Yang, D. Hu, Z. Han, X. Wu, F. Zhang, and L. Wang Environment Evolution for Terminal Agents. arXiv preprint arXiv:2609.04128. External Links: [Link](https://arxiv.org/abs/2609.04128) Cited by: §1, §2.4.
- Gunjal et al. (2025) A. Gunjal, A. Wang, E. Lau, V. Nath, Y. He, B. Liu, and S. Hendryx Rubrics as Rewards: Reinforcement Learning Beyond Verifiable Domains. arXiv preprint arXiv:2507.17746. External Links: [Link](https://arxiv.org/abs/2507.17746) Cited by: §1, §1, §2.4.
- [7] Harbor: Task Structure. Note: [https://www.harborframework.com/docs/tasks](https://www.harborframework.com/docs/tasks)Accessed September 9, 2026 Cited by: §1, §2.2.
- Hebbar et al. (2026) P. Hebbar, Y. Manawat, S. Verboomen, A. Ivanova, S. Palanimalai, K. Bhatia, and V. Baskaran SIA: Self Improving AI with Harness & Weight Updates. arXiv preprint arXiv:2605.27276. External Links: [Link](https://arxiv.org/abs/2605.27276) Cited by: §1.
- Huang et al. (2025) K. Huang, S. Zhang, H. Wang, Y. Qu, Y. Lu, Y. Roohani, R. Li, L. Qiu, J. Zhang, Y. Di, et al. Biomni: A General-Purpose Biomedical AI Agent. bioRxiv. External Links: [Document](https://dx.doi.org/10.1101/2025.05.30.656746), [Link](https://www.biorxiv.org/content/10.1101/2025.05.30.656746v1) Cited by: §1, §1, §1, §2.1, §4.3.
- Laurent et al. (2024) J. M. Laurent, J. D. Janizek, M. Ruzo, M. M. Hinks, M. J. Hammerling, S. Narayanan, M. Ponnapati, A. D. White, and S. G. Rodriques LAB-Bench: Measuring Capabilities of Language Models for Biology Research. arXiv preprint arXiv:2407.10362. External Links: [Document](https://dx.doi.org/10.48550/arXiv.2407.10362), [Link](https://arxiv.org/abs/2407.10362) Cited by: §1, §1, §4.3.
- Lee et al. (2026) Y. Lee, R. Nair, Q. Zhang, K. Lee, O. Khattab, and C. Finn Meta-Harness: End-to-End Optimization of Model Harnesses. arXiv preprint arXiv:2603.28052. External Links: [Document](https://dx.doi.org/10.48550/arXiv.2603.28052), [Link](https://arxiv.org/abs/2603.28052) Cited by: §1, §2.4, §5.
- Liu et al. (2026) H. Liu, Z. Wang, Y. Guo, H. Shou, and X. Tang Adaptive Prompt Structure Factorization: A Framework for Self-Discovering and Optimizing Compositional Prompt Programs. arXiv preprint arXiv:2604.06699. External Links: [Link](https://arxiv.org/abs/2604.06699) Cited by: §2.3.
- Ma et al. (2026) Y. Ma, Y. Huang, H. Bao, H. Zhuang, S. Shukla, M. Galley, X. Zhang, and S. Feuerriegel SkillGen: Verified Inference-Time Agent Skill Synthesis. arXiv preprint arXiv:2605.10999. External Links: [Link](https://arxiv.org/abs/2605.10999) Cited by: §1, §2.3.
- Shao et al. (2024) Z. Shao, P. Wang, Q. Zhu, R. Xu, J. Song, X. Bi, H. Zhang, M. Zhang, Y. K. Li, Y. Wu, and D. Guo DeepSeekMath: Pushing the Limits of Mathematical Reasoning in Open Language Models. arXiv preprint arXiv:2402.03300. External Links: [Link](https://arxiv.org/abs/2402.03300) Cited by: §1, §2.4, §7.3.
- Shin et al. (2026) W. Shin, C. A. Bridges, M. T. McDonnell, and R. Ferreira da Silva Fantastic Scientific Agents and How to Build Them: AgentBuild for Rietveld Refinement. arXiv preprint arXiv:2606.12834. External Links: [Link](https://arxiv.org/abs/2606.12834) Cited by: §1.
- Shinn et al. (2023) N. Shinn, F. Cassano, E. Berman, A. Gopinath, K. Narasimhan, and S. Yao Reflexion: Language Agents with Verbal Reinforcement Learning. arXiv preprint arXiv:2303.11366. External Links: [Document](https://dx.doi.org/10.48550/arXiv.2303.11366), [Link](https://arxiv.org/abs/2303.11366) Cited by: §1, §5.
- Silver and Sutton (2025) D. Silver and R. S. Sutton Welcome to the Era of Experience. Note: Preprint of a chapter for *Designing an Intelligence*, MIT Press External Links: [Link](https://storage.googleapis.com/deepmind-media/Era-of-Experience%20/The%20Era%20of%20Experience%20Paper.pdf) Cited by: ScienceBuddy: Recursive-in-Recursive Self-Improvement for Interactive Scientific Agents.
- Wang et al. (2024) X. Wang, Y. Chen, L. Yuan, Y. Zhang, Y. Li, H. Peng, and H. Ji Executable Code Actions Elicit Better LLM Agents. arXiv preprint arXiv:2402.01030. External Links: [Document](https://dx.doi.org/10.48550/arXiv.2402.01030), [Link](https://arxiv.org/abs/2402.01030) Cited by: §1.
- Wang et al. (2026a) Y. Wang, X. Chen, X. Jin, M. Wang, and L. Yang OpenClaw-RL: Train Any Agent Simply by Talking. arXiv preprint arXiv:2603.10165. External Links: [Document](https://dx.doi.org/10.48550/arXiv.2603.10165), [Link](https://arxiv.org/abs/2603.10165) Cited by: §1, §5.
- Wang et al. (2026b) Y. Wang, T. Xie, K. Shen, M. Wang, and L. Yang RLAnything: Forge Environment, Policy, and Reward Model in Completely Dynamic RL System. arXiv preprint arXiv:2602.02488. External Links: [Document](https://dx.doi.org/10.48550/arXiv.2602.02488), [Link](https://arxiv.org/abs/2602.02488) Cited by: §5.
- Xiao et al. (2026) Y. Xiao, Y. Sun, H. Wu, W. Hui, W. Da, Z. Luo, M. Chuan, Y. Hu, W. Li, and C. Jiang PILOT in the Loop: Live Self-Improvement for Long-Horizon Agents. arXiv preprint arXiv:2608.26530. External Links: [Document](https://dx.doi.org/10.48550/arXiv.2608.26530), [Link](https://arxiv.org/abs/2608.26530) Cited by: §5.
- Yang et al. (2026) Y. Yang, Z. Gong, W. Huang, Q. Yang, Z. Zhou, Z. Huang, Y. Li, X. Gao, Q. Dai, B. Liu, K. Qiu, Y. Yang, D. Chen, X. Yang, and C. Luo SkillOpt: Executive Strategy for Self-Evolving Agent Skills. arXiv preprint arXiv:2605.23904. External Links: [Link](https://arxiv.org/abs/2605.23904) Cited by: §1, §2.3.
- Yao et al. (2023) S. Yao, J. Zhao, D. Yu, N. Du, I. Shafran, K. Narasimhan, and Y. Cao ReAct: Synergizing Reasoning and Acting in Language Models. In International Conference on Learning Representations, External Links: [Link](https://arxiv.org/abs/2210.03629) Cited by: §2.1.
- Yu et al. (2026) Y. Yu, H. Wang, F. Hong, X. Qu, G. Wu, Q. Luo, N. Xu, H. Wang, W. Xu, Y. Liao, Z. Chen, H. Li, Z. Li, D. Peng, M. Liao, J. Wu, H. Ren, and D. Tu Reinforcement Learning with Robust Rubric Rewards. arXiv preprint arXiv:2605.30244. External Links: [Link](https://arxiv.org/abs/2605.30244) Cited by: §2.4.
- Zhang et al. (2025a) J. Zhang, S. Hu, C. Lu, R. Lange, and J. Clune Darwin Godel Machine: Open-Ended Evolution of Self-Improving Agents. arXiv preprint arXiv:2505.22954. External Links: [Document](https://dx.doi.org/10.48550/arXiv.2505.22954), [Link](https://arxiv.org/abs/2505.22954) Cited by: §5.
- Zhang et al. (2026) J. Zhang, B. Zhao, W. Yang, J. Foerster, J. Clune, M. Jiang, S. Devlin, and T. Shavrina Hyperagents. arXiv preprint arXiv:2603.19461. External Links: [Document](https://dx.doi.org/10.48550/arXiv.2603.19461), [Link](https://arxiv.org/abs/2603.19461) Cited by: §5.
- Zhang et al. (2025b) Q. Zhang, C. Hu, S. Upasani, B. Ma, F. Hong, V. Kamanuru, J. Rainton, C. Wu, M. Ji, H. Li, U. Thakker, J. Zou, and K. Olukotun Agentic Context Engineering: Evolving Contexts for Self-Improving Language Models. arXiv preprint arXiv:2510.04618. External Links: [Document](https://dx.doi.org/10.48550/arXiv.2510.04618), [Link](https://arxiv.org/abs/2510.04618) Cited by: §1, §5.
- Zweiger et al. (2025) A. Zweiger, J. Pari, H. Guo, E. Akyürek, Y. Kim, and P. Agrawal Self-Adapting Language Models. arXiv preprint arXiv:2506.10943. External Links: [Document](https://dx.doi.org/10.48550/arXiv.2506.10943), [Link](https://arxiv.org/abs/2506.10943) Cited by: §1, §5.

\supplementary
