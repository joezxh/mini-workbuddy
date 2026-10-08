<p align="center">
  <span><b>中文</b></span>
  &nbsp;&nbsp;|&nbsp;&nbsp;
  <a href="ScienceBuddy_Recursive-in-Recursive_Self-Improvement_for_Interactive_Scientific_Agents.md" title="View English version"><b>🇬🇧 English</b></a>
</p>

---

# ScienceBuddy：面向交互式科学智能体的递归中递归自我改进

Shuhan Xue1,* Jianyuan Zhong1,* Ziyuan Nan1,* Wenbin Li1 Zhaochen Yu1 Jinchao Ding1 Qiang Gao2,3,4,5 Pengyu Zhan6 Yuntong Zhang6 Tian Cheng6 Zhenfei Yin1,7,† Yingcheng Wu1,8,† Ling Yang1,9,†

###### 摘要

我们推出并开源 ScienceBuddy——一个交互式科学研究工作空间，将能够持续自我改进的科学智能体引入研究人员的日常科研工作流。ScienceBuddy 协助研究人员开展科学任务，同时将他们的请求、反馈与执行证据转化为用于持续学习的任务与评估准则（rubric）。其核心是**递归中递归的自我改进**（recursive-in-recursive self-improvement）范式，它将"工具链（harness）演进"与"模型强化学习"耦合在一起：内层递归在模型固定不变的情况下改进工具链，而外层递归则在改进后的工具链下训练模型。工具链的演进塑造了训练经验，而模型学习又为工具链的适配创造了新的机会。我们展示了关于研究人员交互、工具链精化与模型学习的案例研究，其基准案例覆盖四类科学任务族。通过将 ScienceBuddy 以科研产品的形式发布，我们让科学界得以使用这一范式，并向"发现智能"（discovery intelligence）迈进一步：即通过与研究人员持续协作而不断进化、并随其所支撑的研究一同演化的科学人工智能。

*同等贡献。*

*通讯作者。*

*"智能体将栖身于经验的洪流之中，而非交互的只言片语。"* —— Silver 与 Sutton，《欢迎来到经验的时代》（2025）（Silver and Sutton, 2025, p. 2）

![ScienceBuddy：一个通过协作不断学习的科学工作空间。左：科学工作空间。多模态工作空间将文档、图像、表格与生物序列汇聚在一起，提供横跨 22 个功能模块的 224 个工具，覆盖基因组学、分子与癌症生物学、药理学、生物成像、文献检索与数据库查询。可插拔的前沿模型与智能体工具链在该共享环境中支撑科学分析。中：递归中递归的自我改进。嵌套的工具链精化与模型学习通过科学任务与评估准则相互联结。右：研究人员交互。研究人员提出问题、检视结果并精化需求。这些交流为后续改进提供任务目标、评估标准与证据，将科学协作连接到下一个学习周期。](images/sciencebuddy-system-diagram.png)

## 1 引言

科学研究通过剖析、检视与修订而推进。语言模型智能体可以通过检索证据、查询数据库与执行计算流程来提供协助（Huang et al., 2025; Wang et al., 2024; Laurent et al., 2024）。研究人员随后澄清假设、质疑结论并请求补充检查。这些交流揭示了科研工作应当如何开展与评估，但在一次对话中纠正某个答案，并不能建立起跨任务的改进。这引出了我们的核心问题：*科学智能体如何将与研究人员的协作转化为其工作规程与底层能力的持续改进？*

先前的工作为这一问题奠定了基础。反思（reflection）与工具链优化会修订可复用的指令与执行规程（Shinn et al., 2023; Agrawal et al., 2025; Zhang et al., 2025b; Lee et al., 2026）；由交互驱动的适配与基于准则的强化学习提供了模型改进的机制（Wang et al., 2026a; Zweiger et al., 2025; Gunjal et al., 2025）。联合适配亦有先例：SIA 同时更新工具链与模型权重，包括用于单细胞 RNA 去噪（Hebbar et al., 2026），而 HELIX 将工具链演进与模型训练数据的构建联系起来（Fan and Huang, 2026）。在科学领域，AgentBuild 依据科学家编写的准则、课程与知识库来构建智能体（Shin et al., 2026）。我们研究*协作本身*如何能够提供协调反复进行的规程学习与策略学习所需的任务与评估标准。

我们推出 ScienceBuddy，一个用于从研究人员协作中持续学习的交互式科学研究工作空间。图 2 给出了该工作空间的概览，它将科学工具与参考资源（Huang et al., 2025）与数据上传、可执行分析、持久化文件以及可检视的轨迹与产物结合在一起。研究人员通过对话精化其请求，而一个可插拔的工具链则通过指令、可复用技能与上下文管理规程来组织模型行为。将这一可编辑的工具链与科学基础设施相分离，使得规程层面的变更变得明确且可评估。请求、澄清、执行记录与产物共同确立了任务目标、约束与成功标准。我们将这些标准整合为任务专属的准则，并将相应的指令、输入与环境打包为可执行的 Harbor 任务（7）。研究人员的回复为这些标准提供信息，但并不会被当作不容置疑的正确性标签。所得到的任务既支持规程诊断，也支持对全新策略采样的评估，并酌情使用可执行检查与固定评审者（judge）。

在此基础之上，我们提出递归中递归的自我改进（图 2）。内层递归保持任务模型固定，同时由一个独立的、固定的辅助模型来诊断失败并提出对指令、技能或上下文设置的受限编辑。只有当候选改动满足编辑约束并改善配对的开发集评估时，才会被接受（Yang et al., 2026; Ma et al., 2026）。进一步的执行则为下一次修订提供证据。外层递归针对当前的模型与选定的工具链来校准增强后的任务环境（Fan et al., 2026），随后在全新的同策略（on-policy）采样轨迹上，以任务专属的准则奖励与 GRPO 进行训练（Gunjal et al., 2025; Shao et al., 2024）。在训练过程中工具链与准则保持固定；历史交互提供的是任务定义与诊断证据，而非同策略的训练样本。

这种耦合是双向的：工具链的修订塑造了训练轨迹与任务难度，而模型更新则改变了所继承规程的有效性。后台改进与在线服务并行推进。在重新评估之后，更新后的"模型—工具链"组合返回给研究人员，由其交互开启下一个周期。所有工具链与环境版本都被保留以供后续演进。因此，每一个外层周期都通过内层适配过程进行学习，并改变参与下一周期学习的模型。

## 2 ScienceBuddy

ScienceBuddy 是一个交互式科学研究工作空间，将证据获取、计算分析与方法学指导整合进单一的对话式工作流。研究人员可以连同自己的数据一并提出问题，检视所得的分析结果，并通过后续交流对研究工作进行精化。在此基础之上，ScienceBuddy 支持*递归中递归的自我改进*：一个内层过程在任务模型保持固定的情况下修订并评估智能体的工具链（第 2.3 节），而一个外层过程则对在不断演进的工具链下生成的轨迹施加持续的强化学习（第 2.4 节）。更新后的模型随后回到进一步的工具链适配之中，将工作规程的改进与执行这些规程的模型的改进耦合在一起（第 2.5 节）。图 2 概括了这种工具链与模型的耦合改进过程。

### 2.1 科学工作空间与智能体工具链

我们首先描述三个系统组件：科学工具与执行环境、智能体执行与研究人员交互，以及带有可插拔工具链的模块化基础设施。图 2 概括了科学工作空间与研究人员交互。

**科学工具与执行环境。** ScienceBuddy 提供对包含 22 个功能模块、共 224 个工具的目录的访问，覆盖基因组学、分子与癌症生物学、药理学、生物成像、文献检索与数据库查询。运行时支持 Python、R 与 Bash 执行，将科学库与数据处理、统计分析与可视化结合在一起。在线数据库接口与本地数据湖为生物医学证据提供了互补的获取途径。研究人员提供的文档、表格、序列与图像进入一个持久化的工作空间，该空间保留输入、中间文件与生成输出。接口与环境细节见第 7.1 节。科学工具目录与执行工具源自 Huang 等人（2025）。

**智能体执行与研究人员交互。** 我们遵循 ReAct 风格的"推理—动作—观察"循环（Yao et al., 2023），交替进行推理、代码或工具执行以及观察。研究人员通过 Chat 视图提交问题、上传支撑数据并提供后续指令。Trajectory（轨迹）视图呈现按时间顺序排列的执行记录、事件时间线以及所选事件的详细信息。Compute（计算）与 Results（结果）面板提供对执行活动与生成产物的访问。对话历史与工作空间文件跨多次交流保留任务上下文，使研究人员能够检视智能体的工作并提出修订。第 7.5 节展示了这两种界面视图。

**模块化基础设施与可插拔工具链。** ScienceBuddy 将智能体工具链与管理研究人员交互、任务执行与持久化工作空间的基础设施相分离。一个通用的执行接口规定了提供给工具链的任务上下文，以及返回给平台的响应与执行记录。其他智能体式工具链只需实现该接口即可集成进来，同时共享相同的任务管理与存储服务。在这一架构中，指令、技能以及被选定的上下文管理规程构成了工具链中可编辑的组件。递归改进在保持周边基础设施不变的前提下修订这些组件，从而使科学问题求解规程的变更能够在一致的执行条件下被评估（第 2.3 节）。

### 2.2 交互形式化与学习信号

**交互形式化。** 令 $x$ 表示一个研究请求及其输入，$\pi_{\theta}$ 表示任务模型，$H$ 表示工具链，$h_{t}=(x,a_{0},o_{1},\ldots,a_{t-1},o_{t})$ 表示历史，且 $h_{0}=(x)$。动作 $a_{t}$ 是可执行代码、工具调用或面向研究人员的响应。观察 $o_{t+1}=(e_{t+1},u_{t+1})$ 记录环境输出或执行状态 $e_{t+1}$ 以及一条可选的研究人员回复 $u_{t+1}$，当该回复缺失时 $u_{t+1}=\bot$。工具链根据历史、记忆、技能与工具描述构造模型上下文 $C_{H}(h_{t})$。在允许存在预定确定性动作 $d_{H}(h_{t})$（例如输入检查）的前提下，联合策略与轨迹为

$$\mu_{\theta,H}(a\mid h_{t})=\begin{cases}\delta_{d_{H}(h_{t})}(a),&\text{if a harness action is scheduled},\\ \pi_{\theta}(a\mid C_{H}(h_{t})),&\text{otherwise},\end{cases}$$

其中 $a_{t}\sim\mu_{\theta,H}(\cdot\mid h_{t}),\qquad\tau=(x,a_{0},o_{1},\ldots,a_{T-1},o_{T})$。这里 $\delta$ 表示点质量（point mass），$T$ 统计执行步数。一条面向研究人员的响应可能跟在若干工具步骤之后；单独的工具观察并不构成研究人员轮次或用户反馈。

**从协作到任务与准则。** 协作记录提供两类互补的产物：一个自包含的任务及其评估准则（图 3）。相关的轮次围绕一个科学目标被整合起来，彼此可独立求解的目标则被分开。任务指令保留最终的需求与输入，而不引入历史答案。与早期"先打包任务、再交由专家标注"的做法不同，当前工作流还从完整的协作轨迹中推导出准则：

$$\mathcal{C}(x)=\operatorname{ConstructRubric}\bigl(\tau_{x}^{\mathrm{collab}};I_{x},A_{x}\bigr),$$

其中 $\tau_{x}^{\mathrm{collab}}$ 是源协作过程，$I_{x}$ 是重构后的指令，$A_{x}$ 是所需资产。准则涵盖任务范围、方法学要求、证据与预期产物。相互冲突的需求在评分之前被解决；历史答案与研究人员的认可不会被自动当作科学上的真值。

**用于训练后（post-training）的 Harbor 任务。** 任务包将指令、输入资产、执行环境 $\mathcal{E}_{x}$ 与准则组合在一起：

$$\mathcal{P}_{x}=\bigl(I_{x},A_{x},\mathcal{E}_{x},\mathcal{C}(x)\bigr).$$

指令、配置、资产与基于准则的测试被组织为 Harbor 任务（7）。相同的任务支撑两条训练后路径：SFT 通过拒绝采样保留满足准则要求的生成轨迹，而 RL 则收集全新的同策略采样轨迹，并以准则得分作为奖励。输入与运行时检查确立可执行性；基于准则的检查与一个固定的评审者（judge）评估科学要求。在每个训练后阶段内，准则保持固定。

*图 3：源自协作的、用于训练后的 Harbor 任务。协作同时提供任务定义与准则。在示意图的文件树中，instruction.md 定义任务，task.toml 配置执行，environment/ 存放任务资产，而 tests/test.sh 调用基于准则的评估。所得任务通过拒绝采样支撑 SFT，并通过同策略采样支撑 RL。*

### 2.3 内层递归：反馈引导的工具链改进

在外层周期 $k$ 的第 $j$ 个内层步骤中，活跃的工具链 $H_{k,j}$ 是*父本*（parent），其被提议的修订 $\widetilde{H}_{k,j+1}$ 是*候选*（candidate）。被接受的候选成为*子本*（child）$H_{k,j+1}$；否则父本保持活跃。

**反馈引导的诊断。** 在外层周期 $k$ 内，任务模型参数 $\theta_{k}$ 保持固定。我们使用 GPT-6 Astra 作为一个独立的、固定的辅助模型来进行轨迹诊断与工具链编辑。它审视近期的轨迹与准则评估结果，识别未被满足的标准，并引用相关的动作与观察。遵循基于证据的轨迹诊断（Barke et al., 2026），它将所得发现映射为一个候选的规程编辑。任务专属的答案与新提供的 fact 仍局限于该任务本身。

**工具链修订。** 令 $E_{k,j}$ 包含工具链 $H_{k,j}$ 的所选轨迹、准则反馈与编辑历史。辅助模型提出一个受限的更新：

$$\widetilde{H}_{k,j+1}=U(H_{k,j},E_{k,j};\theta_{k}).$$

每个提议会新增、移除或修订一个限定范围的技能，编辑一条指令，或更改一个对外暴露的上下文设置，而保持其他组件不变（Liu et al., 2026; Yang et al., 2026）。一个模式（schema）检查强制实施允许的编辑范围与规模预算。工具、执行基础设施、准则与评估者保持固定。这是一次规程层面的更新；任务模型与辅助模型都不接收梯度更新。

**评估与递归精化。** 父本与候选在相同的开发任务、随机种子与执行预算上，使用冻结的任务准则进行评估。令 $\bar{S}_{k}(H)$ 表示平均归一化准则得分，$\mathrm{Valid}(H)$ 表示是否符合编辑约束。记 $\Delta_{k,j}=\bar{S}_{k}(\widetilde{H}_{k,j+1})-\bar{S}_{k}(H_{k,j})$。所提出的接受规则为

$$H_{k,j+1}=\begin{cases}\widetilde{H}_{k,j+1},&\mathrm{Valid}(\widetilde{H}_{k,j+1})\ \land\ \Delta_{k,j}>0,\\ H_{k,j},&\text{otherwise}.\end{cases}$$

评估包含此前成功的任务，以考量回归（Ma et al., 2026），平局时保留父本。被拒绝的编辑与得分变化保留在优化器的历史中。被选中的工具链随后执行新的训练任务，其轨迹为下一次修订提供证据。迭代持续进行，直到达到提议预算或外层收集边界。开发任务与策略训练任务以及最终留出测试集相互独立，后者绝不参与编辑或选择。

### 2.4 外层递归：持续的模型强化学习

**演进中工具链下的环境增强。** 随着工具链的演进，此前具有挑战性的任务可能变得常规，从而降低其对进一步模型训练的价值。因此，我们借助当前任务模型与所选工具链进行试点执行，以此校准环境难度。遵循环境演进（Fan et al., 2026），我们通过改变科学输入与分析条件，或扩展计算步骤之间的依赖关系，来增强由研究人员派生的任务。经过验证的环境随后提供全新的 RL 采样轨迹。

**任务自适应的准则奖励。** 对于每个任务 $x$，一个固定的准则构建器从源协作轨迹及其重构的目标、输入与所需输出中推导出任务专属的标准（第 2.2 节），遵循任务自适应准则构建（Ding, 2026）。所得准则 $\mathcal{C}(x)$ 将任务专属的正确性检查与相关的证据及产物要求结合在一起。每条标准都有一个非负的重要性权重 $w_{c}(x)$（在采样轨迹评估之前分配）以及一个满足度得分 $v_{c}(x,\tau)\in[0,1]$。在可用时我们使用可执行检查，而对于需要科学解释的标准则使用一个固定的评审者（Yu et al., 2026）。遵循基于准则的奖励聚合（Gunjal et al., 2025），轨迹奖励为

$$R_{x}(\tau)=\frac{\sum_{c\in\mathcal{C}(x)}w_{c}(x)\,v_{c}(x,\tau)}{\sum_{c\in\mathcal{C}(x)}w_{c}(x)},\qquad\sum_{c\in\mathcal{C}(x)}w_{c}(x)>0.$$

准则在不同任务间有所差异，但在优化过程与配对的工具链评估中保持固定。终端奖励提供一个在生成的所有 token 之间共享的轨迹级优势。我们使用 GRPO（Shao et al., 2024）；其目标与实现细节见第 7.3 节。

**模型更新与 renewed 工具链适配。** 在外层周期 $k$，我们在所选工具链下最大化期望轨迹奖励：

$$\max_{\theta}J_{k}(\theta),\qquad J_{k}(\theta)=\mathbb{E}_{x\sim q_{k}}\mathbb{E}_{\tau\sim\pi_{\theta,H_{k}^{\star}}(\cdot\mid x)}\bigl[R_{x}(\tau)\bigr].$$

这里 $q_{k}$ 是在外层周期 $k$ 上、针对经过验证的种子环境与增强变体的训练任务分布，$\pi_{\theta,H_{k}^{\star}}$ 是任务模型在固定工具链 $H_{k}^{\star}$ 下所诱导出的轨迹分布。GRPO 更新产生 $\theta_{k+1}$。由于工具链的有效性取决于其与任务模型的交互（Lee et al., 2026），我们在部署 $(\theta_{k+1},H_{k+1})$（其中 $H_{k+1}=H_{k}^{\star}$）之前，会在更新后的模型下重新评估所选工具链。研究人员与该组合的互动为下一个内层适配阶段与外层更新周期提供证据（第 2.5 节）。

### 2.5 协调递归中递归的改进

**嵌套的更新调度。** ScienceBuddy 在一个固定的收集间隔内，以模型 $\theta_{k}$ 与工具链 $H_{k}$ 为研究人员提供服务。由此产生的交互与反馈启动一个与在线服务异步进行的后台更新周期：在 $\theta_{k}$ 固定的情况下进行工具链改进，随后在所选工具链下进行模型 RL。重新评估之后，更新后的"模型—工具链"组合被部署，以支撑要求越来越高的研究任务。后续的研究人员交互为下一个周期提供证据（算法 1）。

**跨周期经验与重新评估。** 所有工具链版本与任务环境都被保留，以供后续演进使用。所继承的工具链在部署或复用之前，会在更新后的任务模型下被重新评估。

**算法 1**　带异步在线服务的递归中递归改进

1. 初始化 $(\theta_{0},H_{0})$、收集间隔 $\Delta$、训练环境 $\mathcal{T}$、开发任务、内层预算 $J_{k}$、RL 预算与外层计数 $K$。
2. 初始化证据缓冲区 $\mathcal{B}$ 与编辑历史 $\mathcal{L}$；部署 $(\theta_{0},H_{0})$。
3. 对 $k=0,\ldots,K-1$ 循环：
   - $E_{k}\leftarrow\operatorname{Collect}_{\Delta}(\theta_{k},H_{k})$；$\mathcal{B}\leftarrow\mathcal{B}\cup E_{k}$。
   - *后台更新；在线服务以 $(\theta_{k},H_{k})$ 继续运行。*
   - $H_{k,0}\leftarrow H_{k}$；评估 $\bar{S}_{k}(H_{k,0})$；$j\leftarrow 0$。
   - 当 $j<J_{k}$ 且内层执行预算仍有剩余时：
     - 在 $(\theta_{k},H_{k,j})$ 下向 $\mathcal{B}$ 追加新鲜任务证据。
     - $E_{k,j}\leftarrow\operatorname{Read}(\mathcal{B},\mathcal{L};H_{k,j})$。
     - $\widetilde{H}_{k,j+1}\leftarrow U(H_{k,j},E_{k,j};\theta_{k})$（第 2.3 节）。
     - 验证并在验证通过后，在配对的开发条件下评估 $\widetilde{H}_{k,j+1}$。
     - 依据公式 (5) 选择 $H_{k,j+1}$，并将该决策记录于 $\mathcal{L}$。
     - $j\leftarrow j+1$。
   - $H_{k}^{\star}\leftarrow H_{k,j}$；$\mathcal{T}_{k}\leftarrow\operatorname{Augment}(\mathcal{T};\theta_{k},H_{k}^{\star})$。
   - $\theta_{k+1}\leftarrow\operatorname{RLUpdate}(\theta_{k};H_{k}^{\star},\mathcal{T}_{k},R)$（第 2.4 节），使用新鲜批次 $\mathcal{D}_{k,t}$、公式 (6) 与 (10)；优化后退役批次。
   - $H_{k+1}\leftarrow H_{k}^{\star}$；重新评估 $(\theta_{k+1},H_{k+1})$。
   - 保留所有工具链与环境版本；$\mathcal{T}\leftarrow\mathcal{T}\cup\mathcal{T}_{k}$。
   - 部署 $(\theta_{k+1},H_{k+1})$。
4. 返回 $(\theta_{K},H_{K})$。

## 3 科学工作空间与用户体验

**科学范围。** ScienceBuddy 在一个共享的科学工作空间内，将多模态输入、长上下文智能体式推理与研究人员交互结合在一起。其文档处理与执行接口支持多个科学领域，而当前的工具与数据则专攻生物医学。下面这段被记录的会话展示了研究人员如何将可视化的科学素材与目标分析、证据检索以及进一步的问题联系起来。

**多模态输入与证据检视。** 研究人员可以在自然语言请求的同时，提供文档、表格、生物序列与图像。在图 4 中，一张上传的免疫信号通路示意图引导了对分子靶标的识别，以及对相关药物与通路知识的组织。响应将可视化实体与一个证据表格联系起来，区分出被检索到的 PDE4/rolipram 片段，以及返回了无匹配结果的 CD40 与 AHR 检索。对话、输入编辑器与 Compute 面板将科学素材、响应与执行历史汇集到一个可检视的视图中。原始的界面截图见第 7.5 节。

![图 4：用于多模态科学分析的工作空间。一名研究人员提供一张科学示意图并请求相关知识。Chat 视图将视觉解释与一个结构化的"靶标—证据"表格联系起来，而 Compute 面板则暴露执行记录。被检索到的证据与可用数据中的缺口对研究人员保持可见。界面文本与对话系根据录制内容以英文重建；上传的图示保留其原始外观与语言。账户与模型标识被遮蔽。](images/sciencebuddy-workspace-chat.png)

*图 4：用于多模态科学分析的工作空间。一名研究人员提供一张科学示意图并请求相关知识。Chat 视图将视觉解释与一个结构化的"靶标—证据"表格联系起来，而 Compute 面板则暴露执行记录。被检索到的证据与可用数据中的缺口对研究人员保持可见。界面文本与对话系根据录制内容以英文重建；上传的图示保留其原始外观与语言。账户与模型标识被遮蔽。*

**长上下文智能体式推理。** 图 5 追踪了一个连续会话中的三条基于图像的请求：一张 HMGCR 孟德尔随机化示意图、一个与阿尔茨海默病相关的微胶质网络，以及一张免疫信号示意图。智能体通过推理、检索与综合来解释每张图像；后段的执行显式地恢复了同一会话，并保留此前的交流。轨迹记录了反复的数据湖检索以及文献/蛋白质查询；中间的响应则没有发起新的数据库查询，而是使用了模型自身的知识。

![图 5：多模态输入、长上下文智能体式推理与研究人员交互。三条连续的、基于图像的请求在一个连续的科学会话中引导靶标分析。上传的示意图、智能体的解释与证据表格与录制的执行历史配对呈现，展示了研究人员的主导方向与保留的上下文如何将一轮轮的工作连接起来。所提议的分析并非实际执行的实验。英文对话与界面系根据录制片段重建；上传的图示保留其原始语言，省略的事件被标注，标识被遮蔽。](images/sciencebuddy-workspace-long-trajectory.png)

*图 5：多模态输入、长上下文智能体式推理与研究人员交互。三条连续的、基于图像的请求在一个连续的科学会话中引导靶标分析。上传的示意图、智能体的解释与证据表格与录制的执行历史配对呈现，展示了研究人员的主导方向与保留的上下文如何将一轮轮的工作连接起来。所提议的分析并非实际执行的实验。英文对话与界面系根据录制片段重建；上传的图示保留其原始语言，省略的事件被标注，标识被遮蔽。*

**研究人员交互。** 研究人员通过引入新的示意图、改变科学关注点以及显式请求数据库证据来主导工作。连续的响应组织靶标、区分通路与细胞状态标记，并识别出进一步分析所需的数据。被保留的对话与证据支撑着后续请求，以及任务目标与评估标准的推导（第 2.2 节）。

**通过界面控件进行的研究人员检视。** 研究人员交互还包括超出对话输入的导航与检视操作（图 6）。在演示中，研究人员以更大尺度打开一张上传的示意图，从 Chat 切换到 Trajectory，并选择某个工具事件以检视其元数据、输入与输出。所选的 UniProt 事件暴露了一次较早的 HMGCR 查询，而后面的请求仍处在同一会话中。这些控件使研究人员能够检查源素材、跟踪执行历史，并在不开启新对话的情况下重新追溯某个响应的依据。

![图 6：超越对话的研究人员检视。打开一张上传的图像揭示其科学细节；切换到 Trajectory 暴露执行历史；选择一个工具事件则打开其输入、输出与元数据。该示例在同一连续会话中重新追溯了一次较早的 HMGCR 蛋白查询。英文界面重建突出了录制中所使用的控件；上传的示意图与时间线保留源像素。光标标记指示被检视的控件。](images/sciencebuddy-researcher-inspection.png)

*图 6：超越对话的研究人员检视。打开一张上传的图像揭示其科学细节；切换到 Trajectory 暴露执行历史；选择一个工具事件则打开其输入、输出与元数据。该示例在同一连续会话中重新追溯了一次较早的 HMGCR 蛋白查询。英文界面重建突出了录制中所使用的控件；上传的示意图与时间线保留源像素。光标标记指示被检视的控件。*

## 4 案例研究

我们展示了 ScienceBuddy 在科学协助与自我改进方面的四个不同案例研究，每一个都对应一个独立的研究问题：

- **RQ1：研究人员交互。** 研究人员反馈如何引导科学协助，并揭示任务目标与评估标准？（第 4.1 节）
- **RQ2：耦合的递归中递归改进。** 交替进行的工具链精化与模型学习，能否在多个周期中维持改进，并拓宽科学任务表现？（第 4.2 节）
- **RQ3：工具链适配。** 在不改变模型权重的情况下，工具链适配能否改进科学任务表现？（第 4.3 节）
- **RQ4：模型学习。** 在固定工具链下，强化学习能否扩展科学问题求解能力？（第 4.4 节）

### 4.1 ScienceBuddy 交互

**设置。** 我们考察了两个与已部署 ScienceBuddy 进行的真实研究人员交互。请求、所提供的素材、智能体响应以及后续的研究人员输入，支撑了对科学协助以及强化学习（RL）任务构建机会的定性评估。对具体研究人员措辞感兴趣的读者可参阅附录中的图 11。

**精化一项 JAK1 研究。** 一名研究人员要求 ScienceBuddy 利用公共单细胞转录组与 IMpower133 批量 RNA 数据，设计一项关于 JAK1、免疫治疗效果以及小细胞肺癌免疫微环境的研究。针对范围精化（图 11a），ScienceBuddy 组织了一个以基因为中心的研究计划，包含按 JAK1 分层的治疗效果检验、细胞类型内患者层面的表达汇总，以及免疫状态特征。该计划将 Seurat/Scanpy 分配给单细胞分析、UCell/AUCell 分配给特征评分、CellChat/NicheNet 分配给后续的细胞通讯分析。该计划将治疗效应修饰与预后区分开来，并优先安排了机制层面的后续工作。

**在一项 ARL4C 研究中连接证据。** 一名研究人员要求制作一份演示，将一项 ARL4C 研究的背景与结果联系起来，随后明确了面板选择、结论、机制示意图与演讲备注（图 11b）。借助通过 Python/PyPDF2 组织的文本与图注，ScienceBuddy 将候选筛选与细胞及分子证据联系起来。它突出了用于细胞归因的缺失（depletion）与条件性敲除（conditional knockout）比较、用于功能依赖的阻断（blockade），以及用于分子解释的动力学与救援（rescue）实验。面板选择的理由与备注将每一项科学主张与其支撑性比较联系起来。

**从请求到任务规格。** 这些案例展示了研究人员的需求如何转化为任务目标、评估标准与所需产物（图 7）。JAK1 精化产生了一个研究计划式的目标，其标准保留了以基因为中心的范围，并将关联分析置于机制后续工作之前。ARL4C 请求产生了一个演示式目标，其标准将主张与支撑性面板及比较联系起来，并附带结论与演讲备注以及幻灯片大纲。此类任务规格为第 2.2 节所述的、由轨迹派生的准则与训练后任务提供了基础。

*图 7：从研究人员请求到任务规格。（a）一次 JAK1 范围精化定义了一个有序的、以基因为中心的研究计划。（b）ARL4C 演示需求定义了一份证据关联的演示以及"面板—主张"映射。请求经过翻译与删节，源自真实交互；任务目标、评估标准与所需产物是示意性的推导，而非已归档的准则包或已评分的输出。*

### 4.2 双周期递归中递归动态

**设置。** 从 Qwen3.5-4B 与一个初始的科学智能体工具链出发，我们运行三个连续的协同演进周期，以 $k=0,1,2$ 索引。在周期 $k$ 中，工具链精化从 $(\theta_{k},H_{k})$ 开始，保持模型固定，并进行 10 步搜索以通过验证准确率选出 $H_{k}^{\star}$。随后模型学习在所选工具链下进行 20 次 RL 更新。最终的检查点 $\theta_{k+1}$ 与所选工具链 $H_{k+1}=H_{k}^{\star}$ 被带入下一周期，其中所继承的工具链会在更新后的模型下被重新评估。这种反复交换使得模型与工具链的改进能够向前传递，支撑系统在 successive 周期中的持续改进。数据集与环境细节见附录 7.1；详细的实验设置推迟到附录。

*图 8：三个 RinR 周期中的学习动态与评估。每个周期包含十步工具链演进，随后是二十次 RL 更新；颜色标识不同周期。（a）圆圈显示了测得的工具链验证得分，包含被拒绝的候选。（b）结果迁移将初始系统与最终系统在同一测试集上配对。（c）按科学任务族的测试准确率。工具链选择使用一个独立的、固定的验证集。*

**跨周期的学习动态。** 图 8(a) 显示了三个周期各自内部的一致改进。工具链精化将验证准确率从第一、第二、第三周期的 38.9% 提升至 44.4%、34.4% 提升至 46.7%、61.1% 提升至 70.0%。在相同的周期内，平均训练奖励在各自 RL 阶段的前半与后半之间，分别从 33.3% 升至 38.8%、44.1% 升至 60.5%、57.8% 升至 69.8%。这些增益表明，工具链精化与模型训练都持续地改进着它们各自的指标。

**科学任务表现。** 图 8(b,c) 概括了留出（held-out）科学任务表现的改进。单次尝试（single-attempt）的总体测试准确率从 42.2% 提升至 73.3%。在所有测试问题中，33.3% 从错误转为正确，而 2.2% 从正确转为错误。子集比较显示四个任务族均有所增益。这些结果表明，改进延伸到了此前未解决的问题，拓宽了系统的科学问题求解能力。接下来的两个案例研究分别在模型权重或工具链固定的前提下，独立地评估工具链适配与模型学习（第 4.3 与 4.4 节）。

### 4.3 固定模型下的工具链适配

**设置。** 我们在一个*适配集*（adaptation set）上精化并选择工具链，随后在一个独立的*验证集*上比较所选工具链与初始工具链。来自 LAB-Bench 与 Biomni-Eval1（Laurent et al., 2024; Huang et al., 2025）的任务覆盖文献阅读、数据库判断、实验方案排错，以及基因与变异评估。实现细节见第 7.2 节。

**适配与验证表现。** 图 9a 追踪了工具链适配期间的首次响应准确率：即在首次提交时即被正确回答的任务比例。在 24 个适配批次中，观测到的最佳批次准确率达到 75.0%。随后，所选工具链与初始工具链一起在验证任务上接受评估（图 9b）。验证准确率从 31.1% 提升至 51.1%，在模型权重固定的情况下取得了 20 个百分点的增益。这一改进证明了： revising 智能体的工作规程，能够超越用于适配与选择的任务本身而发挥作用。

**学到的规程。** 我们检视所选工具链，以刻画那些从交互中保留下来的规程。它的四条指令条目与九个限定范围的技能，涉及 Python 执行、资源与模式（schema）检查、有界记录查询，以及显式的答案提交。任务专属的规程包括基因集成员关系检查、细胞带（cytoband）查询，以及数据库专属的证据抽取。这些规程引导智能体定位并检查科学记录，将交互证据转化为可用于任务执行的可复用指导。第 7.2 节描述了这些修订，以及将增益归因于单个编辑或反馈来源的局限性。

*图 9：固定模型权重下的工具链适配与验证表现。（a）适配批次期间的首次响应准确率；阶跃曲线追踪迄今观测到的最佳批次准确率。各批次包含不同的任务。（b）初始工具链与在适配集上所选工具链的验证准确率：31.1% 对 51.1%，即 20 个百分点的增益。验证集用于此比较，而非用于工具链选择。*

### 4.4 固定工具链下的模型学习

**设置。** 我们在整个训练过程中保持初始工具链固定，并在相同的评估预算下比较 RL 前后的模型。学习算法与评估协议见第 7.3 节。

**学习动态与问题覆盖。** 在大约两小时的 RL 过程中，训练准确率呈上升趋势（图 10a）。为了评估学习是否也扩展了可解问题的范围，我们测量*问题覆盖率*（problem coverage）：即在四次尝试内至少被成功求解一次测试问题的比例。覆盖率从 RL 前的 48.3% 提升到 RL 后的 67.8%（图 10b），即 19.5 个百分点的增益。在工具链与尝试预算均不变的情况下，模型求解了更广泛的科学问题，证明了模型学习作为一种独立改进机制的有效性。

*图 10：固定工具链下的模型学习与问题覆盖。（a）模型学习期间的训练准确率随耗时变化。（b）RL 前后的问题覆盖率，以固定工具链与相同尝试预算下的 pass@4 衡量。覆盖率从 48.3% 提升至 67.8%，表明在相同尝试预算内成功求解了更多不同的问题。*

## 5 相关工作

**智能体中的持久经验。** Reflexion 将语言经验保留在情景记忆中，GEPA 利用轨迹反思在提示（prompt）上进行搜索，而 ACE 则增量地维护情境化的"剧本"（playbook）（Shinn et al., 2023; Agrawal et al., 2025; Zhang et al., 2025b）。Meta-Harness 借助先前的候选与执行记录将搜索扩展到工具链代码，而 PILOT 在实时执行期间学习可复用规程（Lee et al., 2026; Xiao et al., 2026）。这些方法为持久性的规程适配提供了机制。ScienceBuddy 研究的是：这种适配如何为第二个、模型层面的递归生成经验。

**递归式自我改进。** Darwin Godel Machine 演进出一个智能体档案库，而 Hyperagents 将元层面的修改过程变为可编辑程序的一部分（Zhang et al., 2025a; Zhang et al., 2026）。SEAL 为参数适配生成数据与更新指令（Zweiger et al., 2025）。ScienceBuddy 则研究反复进行的工具链适配与反复进行的任务模型学习之间一种嵌套的依赖关系。其反射器（reflector）保持固定，因此任务表现的改进并不意味着改进机制本身变得更强。

**从交互中学习。** OpenClaw-RL 从智能体动作之后的状态（包括用户回复）中提取评估性与指令性信号（Wang et al., 2026a）。RLAnything 联合适配环境、策略与奖励模型（Wang et al., 2026b）。ScienceBuddy 研究这些学习过程如何与一个演进中的工具链相互作用。用户反馈引导规程修订，而任务验证则监督在活跃工具链下生成的策略轨迹。学习到的模型随后回到下一个内层过程，改变进一步规程适配的条件。

## 6 结论

ScienceBuddy 提供了一个交互式科学工作空间，在其中研究人员的协作能够同时影响工作规程与模型学习。其递归中递归的框架将经过评估的工具链精化与受准则监督的模型更新连接起来，并将更新后的系统交回以进行进一步科学交互。这些案例研究阐明了这些组件的互补贡献：研究人员的请求与后续需求定义了科学任务与评估标准；工具链修订在任务模型固定的情况下改进了首次响应准确率；而模型学习则在初始工具链下扩展了问题覆盖率。这些发现支撑了该框架的规程学习与模型学习机制，并为研究它们在持续的研究人员协作中的协调提供了基础。

## 7 实现细节

本附录将案例研究与正文所描述的科学工作空间及递归中递归框架联系起来。我们将固定模型的工具链演进运行，与固定工具链下的模型学习案例区分开来。角色规格描述了这些组件的信息边界与规程职责；策略目标则展示了模型学习如何契合完整的递归过程。

### 7.1 数据集与环境

**任务构成。** 这 895 个任务的集合包含 96 个 LitQA2、511 个 DbQA、108 个 ProtocolQA 与 180 个 GWAS 任务。LitQA2 与 ProtocolQA 各有 1 个子主题，DbQA 有 10 个，GWAS 有 4 个，共计 16 个子主题。表 1 报告了每个子主题的任务数量以及每个任务族的总数。

| 任务族 | 子主题 | 数量 |
| --- | --- | --- |
| LitQA2 | 科学文献阅读 | 96 |
| DbQA | 疾病—基因关联 | 39 |
|  | 基因定位 | 40 |
|  | miRNA 靶标 | 40 |
|  | 小鼠肿瘤基因集 | 80 |
|  | 致癌特征 | 40 |
|  | 转录因子结合（GTRD） | 40 |
|  | 变异注释：单序列 | 80 |
|  | 变异注释：多序列 | 72 |
|  | 疫苗响应基因集 | 40 |
|  | 病毒蛋白相互作用 | 40 |
|  | 小计 | 511 |
| ProtocolQA | 实验方案排错 | 108 |
| GWAS | 因果基因：GWAS Catalog | 42 |
|  | 因果基因：Open Targets | 45 |
|  | 因果基因：PharmaProjects | 50 |
|  | 变异优先级排序 | 43 |
|  | 小计 | 180 |
| 合计 | 16 个子主题 | 895 |

**任务集的角色。** 在独立的工具链案例研究中，适配对话引导规程修订与工具链选择。初始工具链与在该适配集上所选的工具链，随后在一个独立的验证集上进行比较。模型学习案例在相同面板、初始工具链下比较两个模型检查点，每个问题尝试四次。数据集计数描述的是任务清单；为工具链适配报告的 288 段对话描述的是已执行的适配流。第 4.1 节中真实的研究人员交互，则独立地展示了科学请求与后续需求如何定义任务上下文与准则。

### 7.2 工具链演进

**模型与调度。** 所报告的工具链运行使用一个固定的 Qwen3.5-4B 任务模型。一个固定的 Qwen3.8-27B 辅助模型支撑有界的用户模拟与反馈解释，而 GPT-6 Astra 提出工具链编辑。在每批 12 个任务对话之后，用户反馈与执行证据引导一次更新，从而在 288 段适配对话上产生 24 次更新。这些对话提供了用于工具链精化的反馈。验证任务被保留用于比较初始工具链与适配所选工具链。

**可编辑的规程。** 通用工具链接口允许对指令、技能以及选定的上下文管理进行更新（第 2.1 节）。所报告的案例研究将适配限制为单文件工具链中的指令与限定范围技能文本。执行循环、Python 工具接口、上下文处理、输入检查设置、提交检查与预算保持固定。H0 起始时不带新增的指令或技能条目；H24 包含四条指令条目与九个限定范围技能。每次采样执行一个固定的源快照，其工具链版本保留在轨迹中。下面的角色规格保持了相同的"仅指令/技能"编辑边界。

**修订与检查点选择。** 所提议的指令或技能修订通过组件校验与一次固定的执行预检（preflight）。在适配集上表现最好的工具链被选用于验证比较；验证得分并不引导修订或检查点选择。在验证集上，所选工具链达到 51.1% 的正确率，而初始工具链为 31.1%。这一独立实验的选择协议，不同于耦合周期实验中的、基于验证的工具链选择。

**模拟反馈。** 模拟器接收正确性与提交状态的判定，并为该任务族选择一个被允许的回复。正确答案会收到确认，缺失的提交会收到格式请求，错误答案会收到规程检查或修订请求。回复集合排除了正确选项、标识符与数值答案。反馈解释器看到回复及其公开对话上下文，但看不到私有判定或答案。它将回复分类为接受、纠正、新信息、新需求或歧义，并记录一段支撑性引用与一个诊断得分 $q_{t}\in\{-1,0,+1\}$。这些有界的回复提供了受控的规程反馈；第 4.1 节中的真实研究人员交互展示了更广阔的协作场景。

**诊断反馈与优化奖励。** 得分 $q_{t}$ 记录了一次后续输入与前述响应之间的关系，并支撑工具链诊断。解释器规格中名为 `reward` 的字段表示这一诊断得分。策略优化则改用公式 (6) 中独立评估得到的轨迹奖励 $R_{x}(\tau)$。研究人员反馈可以在评估之前为一个任务的目标与准则提供信息；它并不替代针对这些标准对所得采样轨迹的评估。下面的 GRPO 优势由 $R_{x}(\tau)$ 定义，而不是通过替换解释器的三元得分得到。表 2 概括了这些信息边界。

| 角色 | 公开上下文 | 用户下一步回复 | 私有答案 | 验证者判定 |
| --- | --- | --- | --- | --- |
| 任务策略 | 可见前缀 | 响应之后 | 隐藏 | 经由有界用户反馈 |
| 用户模拟器 | 审阅上下文 | 产生回复 | 隐藏 | 正确性与提交状态 |
| 反馈评审者 | 先前上下文 | 观测到的回复 | 隐藏 | 隐藏 |
| 工具链反射器 | 父本的公开轨迹 | 观测到的回复 | 隐藏 | 评估摘要 |
| 科学验证者 | 所需输出 | 非必需 | 私有访问 | 产生判定 |
| 策略学习者 | 被记录的策略输入 | 不回填 | 不在提示中 | 轨迹奖励 $R_{x}(\tau)$ |

**反思记录与解释。** GPT-6 Astra 接收近期的任务轨迹、活跃规程、准则反馈以及相关编辑历史，排除私有答案与评估者内部信息。每次诊断将一个未被满足的标准关联到支撑性的动作或观察，以及一个被提议的规程编辑。优化器记录父本、候选、模型与环境版本、评估条件与接受决策。被拒绝的编辑仍可用于后续诊断；被存储的版本是决策的历史，而非用于父本采样的"前沿"。学习曲线描述的是在固定模型权重下、连续规程修订的综合效应。单个技能与反馈来源各自的效应并未被单独隔离。

**角色提示规格。** 以下简洁的规格解释了工具链演进案例研究的任务接口、信息边界与编辑范围。它们是对这些角色的解释性描述，而非逐字节归档的请求负载。具体的请求还会提供任务输入、对话记录、被允许的回复、父本工具链以及运行时的编辑模式（schema）。私有的参考答案始终位于策略与提议者的输入之外。

**任务策略。** 你是一个运行于 Science Buddy 中的科学助手。你可以推理，并在一个持久的 REPL 中使用 Python。公开输入位于 `/workspace/assets`。包括序列在内的原始任务位于 `/workspace/assets/task_prompt.txt`。请从该文件读取长序列，而不是将其复制进生成的代码中。请使用下面列出的确切公开文件名。Python 代码必须打印结果；裸表达式不会被显示。科学工具/数据描述位于 `/opt/scitrace/TOOLS.md` 与 `/opt/scitrace/DATA.md`。可用的冻结数据湖以只读方式挂载于 `/opt/data/biomni_data/data_lake`。在声称拥有数据库证据之前，请检查哪些文件与记录确实存在。对于工具调用，请输出一个 `<execute>Python 代码</execute>` 块并等待其结果。否则，请用简要解释与一个 `<answer>值</answer>` 标签回复研究人员。除非你确实这样做过，否则不要声称自己检视了证据或执行了代码。请回应研究人员的下一条回复，并在有理由时修订你的工作。

**用户模拟器。** 角色扮演一名审阅助手*实际*响应的研究人员。这是一个有界的、借助参考辅助的用户模拟器，而非不受限的专家反馈或人类轨迹。请根据对话，从 `allowed_replies` 中选择最有用的、适用的回复。这些选项请求检查或确认完成；没有任何一个会指出正确的任务答案。不要添加科学主张、候选名称、数值结果或超出被允许回复的事实。私有的正确性判定针对所选答案，而非解释中的每一句话。请返回 JSON，其中 `reply` 等于某个被允许的回复，`done` 等于 `answer_correct`。

**反馈解释器。** 你为一个交互式科学助手解释反馈，用于轨迹诊断。请以用户的*下一条回复*作为关于助手*前一条响应*的证据。你不会收到参考答案或终端验证者得分。不要去猜。对于显式接受/确认记为 +1；对于由错误、遗漏或未满足的先前需求所引起的纠正或重做请求记为 -1；对于新需求、新提供的信息、不相关的后续或证据不足记为 0。一次成功的工具调用并非用户认可。要求重新检查或修订同一答案，或提供已被请求过的答案格式，属于纠正（-1），而非正向进展或新需求。请判断反馈*说了什么*，而不是判断用户在科学上是否正确。仅返回 JSON，包含 `reward`（-1, 0, 1）、`feedback_type`（acceptance, correction, new_information, new_requirement, ambiguous）、`evidence`（用户回复的一段*精确*子串），以及 `hint`（一条简要的可复用改进方向，在不支撑时为空）。`reward` 字段是诊断性反馈得分，而非用于策略优化的轨迹奖励。

**工具链提议者：仅指令/技能的编辑。** 利用所提供的父本工具链与交互证据，改进科学助手的指令或限定范围技能。识别一个未被满足的标准，引用相关的动作或观察，并提出一项有界的规程变更：修订一条指令，或新增、移除、修订一个限定范围技能。保留所有非目标条目与运行时设置。请使用所提供的运行时模式（schema）与编辑约束返回修订后的工具链；除非某条目是所提议变更的目标，否则保留现有技能。不要更改上下文历史设置、输入检查设置、工具、执行基础设施、提交检查、预算、准则或评估者。一个完整的序列化工具链代表的是局部编辑，而非重写每个组件的许可。不要在没有新的支撑证据的情况下重复被拒绝的编辑。不要编码任务专属答案、数值结果或样本 ID。一次成功的工具调用并不能证明科学正确性；新提供的信息未必是一个错误。

### 7.3 强化学习

**案例研究配置。** 任务主干为 Qwen3.5-4B。在第 4.4 节中，初始工具链 H0 在整个模型训练与评估过程中保持固定。两个模型检查点在相同的问题上、每个问题尝试四次进行评估，因此前后比较考察的是在通用规程接口下的模型学习。GPT-6 Astra 是工具链适配（第 7.2 节）的诊断/编辑模型；这一固定 H0 的案例不会启动新的工具链适配阶段。它阐明了可以与完整框架中的工具链精化相协调的、模型学习这一组件。

**评估度量。** 训练准确率统计被正确求解的尝试。评估覆盖率以 pass@4 衡量，即若一个问题的四次尝试中至少有一次成功，则计为该问题被解决。后者在相同尝试预算下比较已解问题的广度，不同于工具链案例中所用的首次响应准确率。所报告的覆盖率在 H0 下从 48.3% 升至 67.8%。下面的目标在此递归框架内形式化了这一模型学习步骤。

**新鲜采样组。** 我们使用通用递归框架的记号来表达模型学习组件。在外层阶段 $k$，所选工具链 $H_{k}^{\star}$ 保持固定，而任务模型被优化。第 4.4 节中的纯模型案例在整个比较过程中将该工具链保持在 H0。该案例研究实例化了一个固定工具链的模型学习步骤，而第 2.4 节描述了如何在各周期中纳入所选工具链与经过验证的任务环境。对于每个采样批次，当前任务策略的一个冻结副本 $\pi_{\mathrm{old}}$ 为每个任务生成 $G$ 条轨迹。记录将模型输入、生成的 token、行为对数概率、任务与准则版本，以及工具链标识符与每条轨迹关联起来。新鲜采样组为下面的目标提供数据；而历史研究人员交互则支撑任务定义与规程诊断。当一个批次被复用于若干优化轮次时，概率比值仍相对于其原始收集策略。

**组相对策略目标。** GRPO 公式（Shao et al., 2024）使用 token 级平均。对于轨迹 $i$，令 $r_{i}=R_{x_{i}}(\tau_{i})$ 表示其被评估的轨迹奖励（不同于诊断反馈得分 $q_{t}$），并令 $\mathcal{G}(i)$ 包含在同一工具链与准则下、为同一任务生成的轨迹。组相对优势为

$$\widehat{A}_{i}=\frac{r_{i}-\operatorname{mean}_{j\in\mathcal{G}(i)}r_{j}}{\operatorname{std}_{j\in\mathcal{G}(i)}r_{j}+\delta},\qquad\delta>0.$$

一条轨迹中的所有生成 token 共享这一优势。奖励相同的组具有零策略梯度优势。研究人员消息、工具输出、任务指令与确定性工具链动作被排除在优化 token 之外。对于生成的 token $b_{i,\ell}$ 及其实际上下文 $c_{i,\ell}$，定义

$$\rho_{i,\ell}(\theta)=\frac{\pi_{\theta}(b_{i,\ell}\mid c_{i,\ell})}{\pi_{\mathrm{old}}(b_{i,\ell}\mid c_{i,\ell})}.$$

对于一个由完整组构成的 minibatch $\mathcal{M}$，轨迹 $i$ 含有 $L_{i}$ 个生成 token，其目标为

$$\mathcal{J}_{k}^{\mathrm{GRPO}}(\theta)=\frac{1}{\sum_{i\in\mathcal{M}}L_{i}}\sum_{i\in\mathcal{M}}\sum_{\ell=1}^{L_{i}}\Big[\min\{\rho_{i,\ell}(\theta)\widehat{A}_{i},\operatorname{clip}(\rho_{i,\ell}(\theta),1-\epsilon,1+\epsilon)\widehat{A}_{i}\}-\beta\widehat{d}_{i,\ell}(\theta)\Big].$$

这里 $\epsilon>0$ 控制裁剪，$\beta\geq 0$ 加权采样的 KL 代理。参考策略 $\pi_{\mathrm{ref}}$ 是外层 RL 阶段开始时任务模型的一个冻结副本。记 $z_{i,\ell}=\pi_{\mathrm{ref}}(b_{i,\ell}\mid c_{i,\ell})/\pi_{\theta}(b_{i,\ell}\mid c_{i,\ell})$，则该代理为 $\widehat{d}_{i,\ell}=z_{i,\ell}-\log z_{i,\ell}-1$。这一采样量在被行为策略 token 上评估；它并不被断言为更新策略下的精确 KL 散度。轨迹奖励在采样之后，根据其输出与任务相关的执行证据计算，且准则与评估者参数在优化过程中保持固定。它不会将后续的评估信息回填到生成较早 token 的上下文中。在模型学习案例研究中，两个检查点都在 H0 下使用通用的 pass@4 协议进行评估。在完整的递归框架中，所得检查点 $\theta_{k+1}$ 回到工具链重新评估与部署，后续的研究人员交互启动下一个周期（第 2.5 节）。因此，同一策略学习公式既服务于固定工具链的比较，也提供了完整递归过程中的模型更新步骤。

### 7.4 具体的研究人员输入

以下节选复现了第 4.1 节中所讨论的范围精化与演示需求。它们提供了图 7 中示意性任务转换背后具体的研究人员措辞。

### 7.5 用户界面与研究人员交互

**Chat 与任务管理。** Chat 视图将任务侧边栏、对话工作空间，以及用于执行活动与生成结果的面板结合在一起（图 12）。研究人员可以创建或重访一个任务、选择一个起始提示，或直接输入一个问题。输入编辑器接受粘贴或上传的文件，并支持在同一对话内进行后续指令。Compute 与 Results 选项卡提供对分析活动与所得产物的访问。

![图 12：ScienceBuddy 中的 Chat 视图。任务侧边栏显示在左侧，起始提示与对话区在中间，Compute 与 Results 选项卡在右侧。输入编辑器支持提问、文件附件与模型选择。此截图展示的是执行前的初始任务视图。](images/research-interface-chat.png)

*图 12：ScienceBuddy 中的 Chat 视图。任务侧边栏显示在左侧，起始提示与对话区在中间，Compute 与 Results 选项卡在右侧。输入编辑器支持提问、文件附件与模型选择。此截图展示的是执行前的初始任务视图。*

**轨迹检视。** Trajectory 视图暴露一个任务的有序记录，包括用户消息、系统事件、上下文摘要、工具调用与助手响应（图 13）。一条时间线将输入、模型与工具活动分隔开。选择一个事件会打开一个详情面板，其中包含 Summary、Payload 与 Result 选项卡，用于检视其被记录的内容。搜索与导出控件支撑对记录的审阅，而对话编辑器仍可用于后续输入。

![图 13：ScienceBuddy 中的 Trajectory 视图。时间线与事件记录暴露了一次分析的推进过程，右侧面板显示所选事件的详细信息。截图展示了一段被记录的化合物性质查询、其工具活动、后续对话，以及一个被选中的上下文条目。](images/research-interface-trajectory.png)

*图 13：ScienceBuddy 中的 Trajectory 视图。时间线与事件记录暴露了一次分析的推进过程，右侧面板显示所选事件的详细信息。截图展示了一段被记录的化合物性质查询、其工具活动、后续对话，以及一个被选中的上下文条目。*

## 组织机构

1. PhAI Labs
2. 复旦大学附属中山医院 肝胆外科及肝移植科，肝癌研究所
3. 复杂表型遗传与发育国家重点实验室
4. 复旦大学
5. 上海自然科学院
6. 顺为资本
7. 牛津大学
8. 斯坦福大学
9. 普林斯顿大学

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
