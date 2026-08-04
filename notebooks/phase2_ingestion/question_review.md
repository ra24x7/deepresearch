# Golden question review — 30 drafts awaiting verification

For each: does the question have a single defensible answer, is the quote genuinely
the evidence for it, and is the reference answer correct?

Easiest way to respond: read through and tell me the IDs that are wrong —
I will apply accepts and rejects in one pass. Flag anything that needs rewording
rather than accepting it, so the same flaw does not repeat in later batches.

## 2606.21649

### g042  ·  definitional

**Q.** In EvoEmbedding, what counts as a segment?

> A segment refers to a text unit to be retrieved, such as a single sentence or a conversational turn.
>
> — 2606.21649, sec 3.1 footnote 2, p4

**Expected answer.** A text unit to be retrieved, such as a single sentence or a conversational turn.

- [ ] verified

### g043  ·  factual_single

**Q.** How is the capacity of EvoEmbedding's latent memory queue determined?

> designed to store the latent representations generated from the most recent L steps
>
> — 2606.21649, sec 3.1 Latent Memory Queue, p4
> formula (linearized): C = L * K   (linearized transcription)

**Expected answer.** Capacity C = L x K, storing latent representations from the most recent L steps.

- [ ] verified

### g044  ·  negation

**Q.** While the memory-generation loss is computed, which model components stay inactive?

> we keep the backbone LLM parameters frozen and deactivate all LoRA adapters
>
> — 2606.21649, sec 3.2 Training and Optimization, p5

**Expected answer.** The backbone LLM parameters are frozen and all LoRA adapters are deactivated.

- [ ] verified

### g045  ·  computable

**Q.** By how many percentage points does EvoEmbedding's margin over Qwen3-Embedding-8B exceed its margin over KaLM-Embedding-Gemma3-12B?

> It surpasses generalist KaLM-Embedding-Gemma3-12B (Zhao et al., 2025) by +6.4% and Qwen3-Embedding-8B (Zhang et al., 2025) by +11.1%.
>
> — 2606.21649, sec 1 Introduction, p2

**Expected answer.** 4.7 percentage points (11.1% - 6.4%).

- [ ] verified

### g046  ·  factual_single

**Q.** How many template types guide question generation for the training corpus?

> We pre-define over 40 template types
>
> — 2606.21649, sec 3.3 Stage2 Dynamic QA Generation, p5

**Expected answer.** Over 40 template types, e.g. coreference resolution and temporal understanding.

- [ ] verified

### g047  ·  definitional

**Q.** Which two techniques address varying context lengths in training, and what failure do they avert?

> These techniques successfully prevent representation collapse and improve training efficiency by 3.8 × without curriculum learning
>
> — 2606.21649, sec 1 Introduction, p2

**Expected answer.** The memory queue and segment-batching techniques; they prevent representation collapse and speed training 3.8x.

- [ ] verified

### g048  ·  computable

**Q.** Relative to its longest training window, how much longer are the contexts EvoEmbedding can handle at inference?

> effectively handling 128K contexts (10 × its maximum training window, and >100 × its average sample length of 1.2K)
>
> — 2606.21649, sec 1 Introduction, p2

**Expected answer.** 10x its maximum training window (128K contexts), and over 100x its 1.2K average sample length.

- [ ] verified

## 2607.24663

### g034  ·  factual_single

**Q.** How many operational intents does the APS-RAG query router classify incoming requests into?

> A query router classifies each request into one of eight operational intents
>
> — 2607.24663, sec III.D Adaptive three-way retrieval fusion, p5

**Expected answer.** Eight operational intents, each mapping to its own dense/BM25/graph weight profile.

- [ ] verified

### g035  ·  negation

**Q.** Does APS-RAG learn its retrieval channel weights from training data?

> The weights are hand-set from operational experience rather than learned.
>
> — 2607.24663, sec III.D, p5

**Expected answer.** No — the channel weights are hand-set from operational experience, not learned.

- [ ] verified

### g036  ·  negation

**Q.** Did the domain-pretrained encoder beat general-purpose embedding models on the facility corpus?

> the domain-pretrained encoder does not surpass general-purpose models on this corpus
>
> — 2607.24663, sec III.F, p6

**Expected answer.** No. The domain-pretrained accphysbert model did not surpass general-purpose models.

- [ ] verified

### g037  ·  factual_single

**Q.** Which encoder scored best on vector-only MRR@10, and how did the deployed one compare?

> The bge-m3 model yielded the highest vector-only MRR@10 at 79.2%, with the deployed e5-large-v2 achieving 70.2%.
>
> — 2607.24663, sec III.F, p6

**Expected answer.** bge-m3 was highest at 79.2% MRR@10; the deployed e5-large-v2 reached 70.2%.

- [ ] verified

### g038  ·  computable

**Q.** What is the gap in vector-only MRR@10 between the best-scoring encoder and the one actually deployed?

> The bge-m3 model yielded the highest vector-only MRR@10 at 79.2%, with the deployed e5-large-v2 achieving 70.2%.
>
> — 2607.24663, sec III.F, p6

**Expected answer.** 9.0 percentage points (79.2% - 70.2%).

- [ ] verified

### g039  ·  factual_single

**Q.** Under what conditions does APS-RAG fire its corrective re-retrieval trigger?

> The corrective trigger is activated when the supported fraction of retrieved evidence is less than one-half, or when at least three knowledge-graph entities remain unverified.
>
> — 2607.24663, sec III.E, p5

**Expected answer.** When supported evidence falls below one-half, or at least three knowledge-graph entities remain unverified.

- [ ] verified

### g040  ·  entity_anchored

**Q.** What software framework implements the orchestrator described in APS-RAG?

> The orchestrator is a LangGraph
>
> — 2607.24663, sec III.E, p5

**Expected answer.** A LangGraph state machine.

- [ ] verified

### g041  ·  factual_single

**Q.** Which factor did the authors find matters more for retrieval quality — the reranker or the encoder?

> retrieval performance is influenced more by the cross-encoder reranker than by the choice of embedding model
>
> — 2607.24663, sec III.F, p6

**Expected answer.** The cross-encoder reranker influences retrieval performance more than the embedding model choice.

- [ ] verified

## 2607.26429

### g056  ·  factual_single

**Q.** Which benchmarks does NMKFR use, and under which evaluation protocols?

> NMKFR is evaluated on Amazon Video Games and MovieLens-32M under the Time-aware Cold-Start and Item Cold-Start protocols.
>
> — 2607.26429, sec 4 Experiment setting, p5

**Expected answer.** Amazon Video Games and MovieLens-32M, under Time-aware Cold-Start and Item Cold-Start protocols.

- [ ] verified

### g057  ·  factual_single

**Q.** How are the NMKFR datasets split, and how many negatives accompany each positive?

> Both datasets use 70/10/20 chronological next-item splits with one positive and 100 timestamp-available negatives
>
> — 2607.26429, sec 4 Experiment setting, p5

**Expected answer.** 70/10/20 chronological next-item splits, one positive against 100 timestamp-available negatives.

- [ ] verified

### g058  ·  definitional

**Q.** In NMKFR, what quantity serves as the uncertainty signal, and what does it calibrate?

> uses posterior covariance as an uncertainty signal to calibrate semantic memory retrieval and adaptive static-temporal fusion
>
> — 2607.26429, abstract, p1

**Expected answer.** Posterior covariance, used to calibrate semantic memory retrieval and adaptive static-temporal fusion.

- [ ] verified

### g059  ·  factual_single

**Q.** Which two branches make up the NMKFR framework?

> which combines a Titans-based semantic encoder with time-aware Kalman state tracking
>
> — 2607.26429, abstract, p1

**Expected answer.** A Titans-based semantic encoder and time-aware Kalman state tracking.

- [ ] verified

## 2607.26429 + 2607.26832

### g060  ·  multi_paper

**Q.** Two of these papers attack cold-start recommendation. What evaluation data does each rely on?

> NMKFR is evaluated on Amazon Video Games and MovieLens-32M under the Time-aware Cold-Start and Item Cold-Start protocols.
>
> — 2607.26429, sec 4 Experiment setting, p5

> an article corpus ( N = 385) reflecting regional news outlet volume within a 48 h window
>
> — 2607.26832, sec 3.1 Evaluation, p6

**Expected answer.** NMKFR uses Amazon Video Games and MovieLens-32M; Kairos uses a 385-article regional news corpus from a 48-hour window.

- [ ] verified

### g061  ·  multi_paper

**Q.** Compare how the two cold-start approaches handle time: what mechanism does each use?

> which combines a Titans-based semantic encoder with time-aware Kalman state tracking
>
> — 2607.26429, abstract, p1

> transitioning from passive data-driven modeling to active online learning via contextual bandits
>
> — 2607.26832, sec 1.2 Proposed approach, p2

**Expected answer.** NMKFR tracks latent temporal state with a Kalman filter; Kairos learns online with contextual bandits (LinUCB) against short article TTLs.

- [ ] verified

### g062  ·  multi_paper

**Q.** Which of the cold-start papers optimises for inference cost, and by what mechanism?

> to dynamically adjust inference compute load, enabling efficient candidate generation with minimal precision loss
>
> — 2607.26832, sec 1.2, p2

> The semantic branch extracts memory-enhanced item observations from text, while the temporal branch estimates latent states under irregular interaction intervals.
>
> — 2607.26429, abstract, p1

**Expected answer.** Kairos, via Matryoshka Representation Learning that shrinks the retrieval subspace; NMKFR targets robustness under irregular intervals rather than inference cost.

- [ ] verified

## 2607.26832

### g049  ·  computable

**Q.** How much faster is candidate generation in the reduced subspace than at full dimensionality, and what latency does each incur?

> Full 768d space incurs 0 . 337 ± 0 . 024 ms latency per 100 articles, whereas the MRL 128d subspace reduces latency to 0 . 069 ± 0 . 019 ms-a 79% compute reduction (4.85-fold speed
>
> — 2607.26832, sec 3.2 Computational efficiency, p6

**Expected answer.** 0.337 ms per 100 articles at 768d vs 0.069 ms at 128d — a 79% compute reduction, 4.85-fold speedup.

- [ ] verified

### g050  ·  factual_single

**Q.** What does Kairos substitute for Sherman-Morrison matrix inversion, and what property does it preserve?

> Kairos replaces this with direct Cholesky factor updates, preserving SPD structure implicitly.
>
> — 2607.26832, sec 1.2 Proposed approach, p2

**Expected answer.** Direct Cholesky factor updates, which preserve symmetric positive-definite structure implicitly.

- [ ] verified

### g051  ·  negation

**Q.** Under sustained high load, do classical matrix-inversion updates stay numerically consistent?

> Kairos maintains numerical consistency under high load, whereas conventional inversion diverges
>
> — 2607.26832, sec 4.1 Numerical resilience, p7

**Expected answer.** No — conventional inversion diverges under high load, while Kairos's Cholesky updates stay consistent.

- [ ] verified

### g052  ·  computable

**Q.** Across how many article pairs was approximation quality assessed, and what mean absolute error resulted?

> Approximation quality was evaluated via cosine similarity deviations across all 73,920 article pairs. The mean absolute error (MAE) of 0 . 036 ± 0 . 022 confirms 96.4% structural retention
>
> — 2607.26832, sec 3.2, p6

**Expected answer.** 73,920 article pairs; MAE of 0.036 ± 0.022, i.e. 96.4% structural retention.

- [ ] verified

### g053  ·  definitional

**Q.** What role does Matryoshka Representation Learning play in the Kairos architecture?

> to dynamically adjust inference compute load, enabling efficient candidate generation with minimal precision loss
>
> — 2607.26832, sec 1.2 Proposed approach, p2

**Expected answer.** It lets inference compute load be adjusted dynamically, enabling efficient candidate generation with minimal precision loss.

- [ ] verified

### g054  ·  negation

**Q.** Does truncating the news embeddings to a 128-dimensional subspace discard most of the semantic variance?

> confirms that at 𝑚 = 128 dimensions, over 95% of semantic variance is preserved
>
> — 2607.26832, sec 3.1 Spectral analysis, p6

**Expected answer.** No — over 95% of semantic variance is preserved at 128 dimensions.

- [ ] verified

### g055  ·  factual_single

**Q.** What exploration algorithm does Kairos use to move from passive modelling to active learning?

> the implemented Linear Upper Confidence Bound (LinUCB) algorithm uses contextual embeddings to estimate recommendation payoffs while modeling uncertainty
>
> — 2607.26832, sec 1.2, p2

**Expected answer.** LinUCB (Linear Upper Confidence Bound), a contextual bandit that models uncertainty for exploration.

- [ ] verified

### g063  ·  computable

**Q.** Between the full and reduced representation spaces in Kairos, by what factor does the dimensionality shrink?

> denote feature space dimension with 𝑑 = 128 in the MRL subspace and 𝑑 = 768 in full space
>
> — 2607.26832, sec 2.3 Computational effort, p4

**Expected answer.** 6x — from 768 dimensions in full space to 128 in the MRL subspace.

- [ ] verified
