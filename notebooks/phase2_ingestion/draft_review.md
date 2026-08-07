# Draft review — 27 questions

Reviewer verdicts shown per question. To accept: delete the `"status": "draft_unverified"` field
in data/golden_dataset.jsonl. To reject: delete the line. Or just tell me the ids.

**Order suggested:** the 4 REWRITTEN/CORRECTED first (I changed these), then the 6 NEEDS A LOOK,
then the 16 routine ones.

## Changed by me — please check my fix

### g048  ·  computable  ·  2607.26952

**REWRITTEN — quote was verbatim but answer misleading; rebuilt on the regression results**

**Q.** On credit-card agreements, which reasoning feature most reduces the odds of a correct answer, and how does the number of required computational steps affect correctness?

> The number of required computational steps is positively associated with correctness ( β = 0.33, p = 0.012), corresponding to approximately a 39% increase in the odds of a correct answer per additional step.
>
> — 2607.26952, sec 6.2 Regression Results, p8-9

> In contrast, comparison-based reasoning substantially hurts performance ( β = -1.33, p < 0.001) the largest among all features, reducing the odds of a correct answer by approximately 74%.
>
> — 2607.26952, sec 6.2 Regression Results, p8-9

**Expected answer.** Comparison-based reasoning is the largest negative effect of any feature (beta -1.33, p < 0.001), cutting the odds of a correct answer by about 74%. Required computational steps work the other way: each additional step is associated with roughly 39% higher odds of correctness (beta 0.33, p = 0.012).

- [✓] accept

### g051  ·  factual_single  ·  2607.27146

**CORRECTED — reference answer misstated what the metric measures**

**Q.** What two transition rates does MindForge use to characterise agent behaviour beyond raw operational counts?

> (i) the fraction of reasoning actions that are immediately followed by an implementation edit; and (ii) the fraction of failure-recovery actions that are immediately followed by an implementation edit.
>
> — 2607.27146, sec 4.3 Behavior Analysis, p6

**Expected answer.** The fraction of reasoning actions immediately followed by an implementation edit, and the fraction of failure-recovery actions immediately followed by an implementation edit. Both measure how reliably an agent converts deliberation, or recovery from a failed command, into an actual change to its code — reported alongside turns, tool-calls, token counts and failure rates.

- [✓] accept

### g055  ·  factual_single  ·  2607.27155

**RETYPED — was multi_paper with one paper listed**

**Q.** How does OmegaUse-OfficeVal say its evaluation target differs from that of OSWorld 2.0?

> OSWorld 2.0 remains a computer-use benchmark centered on GUI operation, asking whether the agent reaches the expected environment state. OmegaUse-OfficeVal instead evaluates the final office deliverable itself.
>
> — 2607.27155, sec 2.3 Computer-Use and GUI-Agent, p5

**Expected answer.** OSWorld 2.0 asks whether the agent reaches an expected environment state — a GUI-operation target. OmegaUse-OfficeVal instead judges the final office deliverable itself. OSWorld 2.0 comprises 108 tasks with a median of roughly 1.6 hours of skilled human operation.

- [✓] accept

### g063  ·  definitional  ·  2607.27191

**CORRECTED — overstated a claim the paper disclaims; disclaimer added as evidence**

**Q.** What gap do the authors identify between an AI system producing research and judging it?

> Our results suggest there is a generator-verifier gap in conducting AI research.
>
> — 2607.27191, sec 4.4, p11-12

> At the same time, we cannot establish the verifier's accuracy. Both agent-generated papers were rejects, so we cannot say whether the AI reviews were actually discerning quality or just uniformly rejecting the papers.
>
> — 2607.27191, sec 4.4, p11-12

**Expected answer.** A generator-verifier gap: the agents could not produce publishable research, while AI reviews reliably rejected their drafts, which the authors suggest could be used to discern quality and drive progress via reinforcement learning. They immediately qualify this — they cannot establish the verifier's accuracy, since both agent papers were rejects, so the reviews may have been uniformly rejecting rather than discriminating.

- [✓ ] accept

## Reviewer flagged — judgement call

### g047  ·  entity_anchored  ·  2607.27183

**lexical give-away: question and evidence share distinctive terms almost verbatim**

**Q.** Which model was used to filter prompts when building Pangram 4's synthetic benchmark, and from which source dataset?

> we use Mistral-Small-24B-Instruct-2501 (Mistral AI, 2025) to filter prompts from the Chatbot Arena Conversations Dataset
>
> — 2607.27183, sec 5.2 Synthetic benchmark construction, p14-15

**Expected answer.** Mistral-Small-24B-Instruct-2501, filtering prompts from the Chatbot Arena Conversations Dataset — chosen so prompts reflect the real-world distribution of user prompts to LLMs.

- [✓ ] accept

### g056  ·  definitional  ·  2607.26593

**type may be wrong: mechanism question, not definitional**

**Q.** In the QQ-search training procedure, how is the negative half of each preference pair obtained?

> The negative sequence ( 𝑟 -𝑖 , 𝑙 -𝑖 ) is taken as the model's original prediction
>
> — 2607.26593, sec 4.2 Training Process, p4-5

**Expected answer.** It is the model's own original prediction. The positive half is generated by beam search, selecting the highest-probability candidate consistent with the verified label.

- [✓ ] accept

### g062  ·  entity_anchored  ·  2607.27065

**scope ambiguity: paper studies three detectors over two objects; quote covers one object**

**Q.** Which two detector architectures does the synthetic-data study compare, and why were both chosen?

> LW-DETR-Tiny [13], a compact transformer-based detector that achieves real-time performance while offering a fundamentally different architecture, allowing findings to be assessed across both model families
>
> — 2607.27065, sec 4 Comparison using edge-deployable, p6

**Expected answer.** A detector from the latest YOLO generation and LW-DETR-Tiny, a compact transformer-based detector — deliberately different architectures so findings hold across both model families.

- [✓ ] accept

### g064  ·  factual_single  ·  2607.26967

**worst lexical give-away: question nearly reproduces the section header**

**Q.** Why does JUD work, according to the paper analysing it?

> these results show that JUD is effective because it removes the set-level prediction bottleneck and more directly elicits the LLM's pair-recognition capability
>
> — 2607.26967, sec 5 Why Does JUD Work, p5

**Expected answer.** Because it removes the set-level prediction bottleneck and more directly elicits the LLM's pair-recognition capability.

- [ ✓] accept

### g068  ·  negation  ·  2607.27134

**moderate lexical overlap (partly unavoidable for this negation)**

**Q.** Does recursive feedback on its own drive linguistic monoculture in the shared-model analysis?

> recursive feedback alone does not force monoculture when authors are pulled toward fixed targets
>
> — 2607.27134, sec 3.2 A shared model with recursive feedback, p6-7

**Expected answer.** No. When the adaptation target does not depend on the evolving model distribution, the author dynamics are unchanged from the fixed-model setting — recursive feedback alone does not force monoculture.

- [✓ ] accept

### g070  ·  negation  ·  2607.27201

**moderate lexical overlap**

**Q.** Are the latent states of existing POMDP world models optimised for simulating mental states?

> Their latent states, however, are usually optimized for physical control, reward prediction, visual dynamics, or nested decision-theoretic planning, rather than explicit physical-mental world simulation.
>
> — 2607.27201, sec 2.3 POMDP-based World Modeling, p5-6

**Expected answer.** No. They are usually optimised for physical control, reward prediction, visual dynamics, or nested decision-theoretic planning rather than explicit physical-mental world simulation.

- [✓ ] accept

## Routine

### g044  ·  negation  ·  2607.26977

**reviewer: clean**

**Q.** Was the Claude family left out of the TREK evaluation as a design decision?

> The Claude family is geo-blocked at the provider level from our run location and thus could not be evaluated-an availability constraint, not a design choice, so the leaderboard should be read accordingly
>
> — 2607.26977, Appendix F Limitations, p27

**Expected answer.** No. It was geo-blocked at the provider level from the run location, an availability constraint rather than a design choice, so the leaderboard should be read with that in mind.

- [✓] accept

### g045  ·  negation  ·  2607.26977

**reviewer: clean**

**Q.** Does TREK's knowledge base reflect real listing distributions or live pricing?

> TREK's knowledge base is synthetic and internally consistent by construction-the property that yields a deterministic ground truth and an achievable gold-but it therefore does not model real listing distributions, live availability, or prici
>
> — 2607.26977, Appendix F Limitations, p27

**Expected answer.** No. It is synthetic and internally consistent by construction, which is what yields a deterministic ground truth and an achievable gold answer, but it does not model real listing distributions, live availability or pricing.

- [✓] accept

### g046  ·  computable  ·  2607.27183

**reviewer: clean**

**Q.** How much did the newer Pangram release cut the overall false negative rate relative to its predecessor?

> At the production operating point, Pangram 4 achieves an overall false negative rate of 0.3396% . This is an improvement over Pangram 3.3.2, which reports a FNR of 1.9942% on the same dataset.
>
> — 2607.27183, sec 5.2 Overall False Negative Rate, p14-15

**Expected answer.** From 1.9942% to 0.3396% at the production operating point — roughly a 5.9x reduction, or about 1.65 percentage points.

- [✓] accept

### g050  ·  factual_single  ·  2607.27130

**reviewer: clean**

**Q.** On which ontology-matching sub-task does AgentMap win most consistently, and where is its margin narrowest?

> AgentMap achieved consistently best subsumption accuracy across all four datasets
>
> — 2607.27130, sec 4.4 Experimental Results, p8-9

> For equivalence accuracy, the gap between AgentMap and the other baselines is much smaller.
>
> — 2607.27130, sec 4.4 Experimental Results, p8-9

**Expected answer.** Subsumption: AgentMap is consistently best across all four datasets. Its margin is narrowest on equivalence accuracy, where on HeLiS-FoodOn a baseline (LLM+Neighbourhood) even scores higher.

- [✓] accept

### g052  ·  entity_anchored  ·  2607.26998

**reviewer: clean**

**Q.** How many CVE-Bench tasks and attacker models is AgentSnare evaluated against?

> Across 15 CVE-Bench tasks and three attacker models, AgentSnare achieves 46.8% Delay
>
> — 2607.26998, sec Conclusion, p7-8

**Expected answer.** Fifteen CVE-Bench tasks and three attacker models.

- [✓] accept

### g053  ·  negation  ·  2607.26670

**reviewer: clean**

**Q.** In the surveyed literature, is retrieval usually the central contribution of the systems described?

> In many systems, retrieval serves as a supporting component rather than the paper's main contribution
>
> — 2607.26670, sec 5 Discussion, p16-17

**Expected answer.** No. In many of the surveyed systems retrieval is a supporting component rather than the paper's main contribution.

- [✓] accept

### g054  ·  computable  ·  2607.27022

**reviewer: clean**

**Q.** In the regional-bias study, how do the correlations for the two stereotype dimensions compare in direction and strength?

> Competence is strongly positively associated with GDP, disposable income, and broadband users, with mean correlations of 0.81, 0.68, and 0.61, respectively. In contrast, Warmth shows Warmth Score weaker negative associations of -0.33, -0.31, and -0.21.
>
> — 2607.27022, sec 4.1 Bias Association Analysis, p5-6

**Expected answer.** They point in opposite directions and differ in magnitude: Competence correlates positively (0.81 GDP, 0.68 disposable income, 0.61 broadband users) while Warmth correlates negatively and more weakly (-0.33, -0.31, -0.21) — a gap of roughly 1.14 on GDP.

- [✓] accept

### g057  ·  entity_anchored  ·  2607.26621

**reviewer: clean**

**Q.** What baseline is WhisperRec built on, and what problem does it address in that baseline?

> Built upon OneReason, a strong FRM baseline, WhisperRec addresses the limitations of explicit CoT through MV-ACoT for diverse CoT construction, three-stage Latent Reasoning Alignment for internalizing teacher CoT into latent tokens,
>
> — 2607.26621, sec General Capability Analysis, p7-9

**Expected answer.** OneReason, a foundation recommendation model baseline. WhisperRec targets the limitations of explicit chain-of-thought, using MV-ACoT for diverse CoT construction and a three-stage Latent Reasoning Alignment that internalises teacher CoT into latent tokens.

- [✓] accept

### g058  ·  computable  ·  2607.26500

**reviewer: clean**

**Q.** Across the four target sets, what is the range of improvement the multi-decoder variant makes over the single-decoder baseline?

> improving the single-decoder OneRec [5] baseline by 1.69%, 4.04%, 5.54%, and 5.62% on Exposure, Long-View, Like, and Watch-time Recall, respectively
>
> — 2607.26500, sec 5.2 Overall Performance, p7

**Expected answer.** From 1.69% to 5.62% — smallest on Exposure Recall, largest on Watch-time Recall, a spread of 3.93 percentage points (also 4.04% Long-View, 5.54% Like).

- [✓] accept

### g059  ·  negation  ·  2607.27054

**reviewer: clean**

**Q.** In the heterogeneous distillation comparison, did feature-based methods beat training the student from scratch?

> Feature-based and responsebased methods obtain average Top-1 accuracies of 69.72% and 72.79%, respectively, and the former is below the scratch baseline of 71.45%.
>
> — 2607.27054, sec Main Results, p5

**Expected answer.** No. Feature-based methods averaged 69.72%, below the 71.45% scratch baseline; response-based methods reached 72.79%. CoCaRS averaged 84.70%.

- [✓] accept

### g060  ·  factual_single  ·  2607.27167

**reviewer: clean**

**Q.** On the specification-elicitation benchmark, how many instances does the strongest baseline fully resolve?

> even the strongest baseline, GPT5.5-high without spec elicitation, fully resolves only 1 of 200 instances (resolved rate 0.5%)
>
> — 2607.27167, sec C. Evaluation Metric, p5-6

**Expected answer.** One of 200 instances — a 0.5% resolved rate — which is why average test pass rate is used instead as the comparison signal.

- [✓] accept

### g061  ·  definitional  ·  2607.27143

**reviewer: clean**

**Q.** What does selective classification allow a classifier to do, and where does the idea originate?

> Selective classification, originating from Chow's optimal rejection rule [17], enables a classifier to abstain on uncertain predictions and delegate ambiguous cases to human experts
>
> — 2607.27143, sec 2.3 Selective Classification, p5

**Expected answer.** It lets a classifier abstain on uncertain predictions and delegate ambiguous cases to human experts. It originates from Chow's optimal rejection rule.

- [✓] accept

### g065  ·  negation  ·  2607.26893

**reviewer: clean**

**Q.** In the user-simulator study, did scaling the model and data alone deliver good thinking quality?

> This indicates that simulation depends not only on model and data scale, but also on effective domain adaptation and objective alignment
>
> — 2607.26893, sec 5.2 Overall Results (RQ1), p6

**Expected answer.** No. Despite gains in action quality, thinking quality stayed limited relative to baselines — simulation depends not only on model and data scale but also on domain adaptation and objective alignment via a thinking reward.

- [✓] accept

### g066  ·  factual_single  ·  2607.26928

**reviewer: clean**

**Q.** What does the speech-LLM paper conclude about controlling an intermediate conversational action?

> explicitly recovering and controlling an intermediate conversational action can match direct supervised fine-tuning while retaining a modular, label-free inference pipeline
>
> — 2607.26928, sec End-to-End Move Control, p5

**Expected answer.** It matches direct supervised fine-tuning while keeping a modular, label-free inference pipeline — the model often realises the appropriate move with lexically different wording.

- [✓] accept

### g067  ·  negation  ·  2607.26981

**reviewer: clean**

**Q.** Does the observed size-optimism gradient hold across every multi-tier provider tested, and is it causal evidence?

> The observational gradient is consistent with the controlled finding but does not stand on its own as causal evidence. Within three of four multi-tier providers, smaller models are more optimistic
>
> — 2607.26981, sec 4.2 Alignment Gradient, p5

**Expected answer.** No on both counts. It holds within three of four multi-tier providers — Mistral runs in the opposite direction — and the authors state the observational gradient is consistent with their controlled finding but does not stand alone as causal evidence.

- [✓] accept

### g069  ·  factual_single  ·  2607.27172

**reviewer: clean**

**Q.** Which evaluation metric proved most sensitive to decoding temperature in the e-commerce deployment, and how was the value chosen?

> Carousel Coherence (Table 4) was the metric most sensitive to decoding temperature: high temperatures diversified intents but caused titles to drift off-topic across the carousel set.
>
> — 2607.27172, sec 5 Deployment Lessons and Limitations, p5

**Expected answer.** Carousel Coherence. High temperatures diversified intents but caused titles to drift off-topic across the carousel; temperature 1.0 was selected by sweeping on that metric.

- [✓] accept
don