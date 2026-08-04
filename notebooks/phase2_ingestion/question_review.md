# Golden question review — batch 3 (15 drafts)

Sequential-recommendation cluster: IMFuse (2607.27002) and Privileged
Self-Distillation (2607.27055). Every quote is verbatim in a single indexed
chunk, and every fact an answer asserts is present in its evidence (except
arithmetic a computable question asks you to derive).

Tell me the IDs that are wrong and I will apply accepts/rejects in one pass.

### g034  ·  negation  ·  2607.27002

**Q.** When IMFuse is evaluated, is the next item ranked against a sampled set of negatives or against the whole catalogue?

> we evaluate full-catalog nextitem ranking using Hit Ratio (HR) [22] and Normalized Discounted Cumulative Gain (NDCG) [17]
>
> — 2607.27002, sec 4.1.3 Evaluation Metrics

> all configurations use InfoNCE [47] with 64 negative samples as the recommendation objective
>
> — 2607.27002, sec 4.1.2 Backbones and Baselines

**Expected answer.** Against the whole catalogue — a full-ranking protocol scored with HR and NDCG. The 64 negative samples belong to the InfoNCE training objective, not to evaluation.

- [ ] verified

### g035  ·  entity_anchored  ·  2607.27002

**Q.** Which three methods does IMFuse group under multi-layer fusion when selecting baselines?

> Multi-layer fusion methods : LAEF (arXiv'25) [11] applies average, max, and min aggregation over selected layers; CASEMLP (EACL'26) [59] uses supervised MLP projection for multilayer representation fusion; and VA-HS (ICML'26) [62] adopts cross-layer value aggregation on cached hidden states.
>
> — 2607.27002, sec 4.1.2 Backbones and Baselines

**Expected answer.** LAEF, CASEMLP and VA-HS.

- [ ] verified

### g036  ·  factual_single  ·  2607.27002

**Q.** How does IMFuse decide which interaction of a user is held out for testing?

> we sort each user's interactions by timestamp, reserve the last interaction for testing and the penultimate interaction for validation, and use all remaining interactions for training
>
> — 2607.27002, sec 4.1.1 Datasets

**Expected answer.** Chronological leave-one-out: the last interaction is used for testing, the penultimate for validation, the rest for training.

- [ ] verified

### g037  ·  negation  ·  2607.27055

**Q.** In the PSD training objective, is the student supervised directly against the observed next item?

> the objective contains NO student cross-entropy term: the causal view is shaped entirely by the teacher's softened distribution rather than by the one-hot target
>
> — 2607.27055, sec 3.4 Optimization Objective

**Expected answer.** No — there is no student cross-entropy term; the student is shaped entirely by the teacher's softened distribution, not the one-hot target.

- [ ] verified

### g038  ·  negation  ·  2607.27055

**Q.** Does PSD need a warm-up or pretraining stage before distillation can begin?

> The whole model is trained in a single stage without any pretraining or teacher-warmup phase
>
> — 2607.27055, sec 3.4 Optimization Objective

**Expected answer.** No — it trains end to end in a single stage, with no pretraining and no teacher warm-up.

- [ ] verified

### g039  ·  definitional  ·  2607.27055

**Q.** What makes the suffix of a user's interaction sequence privileged information in PSD?

> This is precisely the setting of privileged information [16, 30]: an auxiliary view that may inform learning but must not enter the deployed predictor.
>
> — 2607.27055, sec 2.2 Future as Privileged Information

**Expected answer.** It is an auxiliary view available during training that may inform learning but must not enter the deployed predictor — the suffix is observed at training time yet never available at serving.

- [ ] verified

### g040  ·  definitional  ·  2607.27055

**Q.** What separates the teacher from the student in PSD, given they share parameters?

> The teacher and the student are distinguished solely by their attention scope.
>
> — 2607.27055, sec 3.1 Dual-Mask Teacher and Student

**Expected answer.** Only their attention scope: the student attends to the prefix alone (matching deployment), while the teacher additionally sees the suffix.

- [ ] verified

### g041  ·  factual_single  ·  2607.27055

**Q.** What guards against label leakage in the teacher's wider receptive field?

> the target item 𝑖 𝑡 is excluded from its own receptive field to prevent label leakage, and the student never observes the suffix
>
> — 2607.27055, sec 3.1 Dual-Mask Teacher and Student

**Expected answer.** The target item is excluded from its own receptive field, and the student never observes the suffix.

- [ ] verified

### g042  ·  entity_anchored  ·  2607.27055

**Q.** Which encoder turns item text into representations in the PSD experiments?

> we retain the title, price, and description of each Amazon item, and the name, category, city, and state of each Yelp business, and encode the text with Qwen3-Embedding-8B [40]
>
> — 2607.27055, sec 4.1.1 Datasets

**Expected answer.** Qwen3-Embedding-8B.

- [ ] verified

### g043  ·  factual_single  ·  2607.27055

**Q.** What rating threshold decides whether an interaction counts as positive in the PSD datasets?

> an interaction is regarded as positive only if its rating exceeds 3, and the remaining interactions are removed
>
> — 2607.27055, sec 4.1.1 Datasets

**Expected answer.** Only interactions rated above 3 count as positive; the rest are discarded.

- [ ] verified

### g044  ·  computable  ·  2607.27055

**Q.** Relative to its backbone, how does the RD baseline change HR@10 on Video Games for the two architectures it was applied to?

> RD, whose supervision comes from a separately pre-trained static teacher, raises the HR@10 of SASRec from 0.0455 to 0.0509 on Video Games yet drags UniSRec down from 0.0693 to 0.0595
>
> — 2607.27055, sec 4.2 Overall Performance

**Expected answer.** It helps SASRec (0.0455 to 0.0509, about +11.9%) but harms UniSRec (0.0693 to 0.0595, about -14.1%).

- [ ] verified

### g045  ·  factual_single  ·  2607.27055

**Q.** Why does the bidirectional backbone lose to the unidirectional one in the PSD comparison?

> BERT4Rec generally underperforms SASRec despite observing richer bidirectional context during training, trailing by nearly 20% on average and by up to 41.7% for HR@10 on CDs & Vinyl
>
> — 2607.27055, sec 4.2 Overall Performance

**Expected answer.** BERT4Rec trails SASRec by nearly 20% on average and up to 41.7% on CDs & Vinyl HR@10: its masked-item objective conditions on context that never exists at serving time.

- [ ] verified

### g046  ·  multi_paper  ·  2607.27002, 2607.27055

**Q.** Both of these sequential-recommendation papers evaluate on Amazon data. Which subsets does each one use?

> We conduct experiments on four widely used realworld Amazon product datasets: Amazon Toys and Games , Amazon Beauty , Amazon Clothing, Shoes and Jewelry , and Amazon Office Products
>
> — 2607.27002, sec 4.1.1 Datasets

> We conduct experiments on three widely used benchmarks: two subsets of the Amazon review corpus [10], Video Games and CDs & Vinyl , and the Yelp business-review dataset.
>
> — 2607.27055, sec 4.1.1 Datasets

**Expected answer.** IMFuse uses four Amazon subsets (Toys and Games, Beauty, Clothing Shoes and Jewelry, Office Products); PSD uses two (Video Games, CDs & Vinyl) plus Yelp. They share no Amazon subset.

- [ ] verified

### g047  ·  multi_paper  ·  2607.27002, 2607.27055

**Q.** Each of these papers argues the one-hot next-item label is too weak a signal. What does each add instead?

> the student inherits from the teacher a preference structure over the entire item set, a strictly richer supervisory signal than the one-hot label
>
> — 2607.27055, sec 3.2 Gated Privileged Distillation

> Multi-layer fusion methods : LAEF (arXiv'25) [11] applies average, max, and min aggregation over selected layers
>
> — 2607.27002, sec 4.1.2 Backbones and Baselines

**Expected answer.** PSD adds a teacher's full preference distribution over the item set, distilled from a suffix-aware view; IMFuse instead enriches item representations by fusing multiple layers of an LLM encoder.

- [ ] verified

### g048  ·  multi_paper  ·  2607.27002, 2607.27055

**Q.** Which of the two papers deliberately withholds information from the deployed model, and why?

> an auxiliary view that may inform learning but must not enter the deployed predictor
>
> — 2607.27055, sec 2.2 Future as Privileged Information

> we evaluate full-catalog nextitem ranking using Hit Ratio (HR) [22] and Normalized Discounted Cumulative Gain (NDCG) [17]
>
> — 2607.27002, sec 4.1.3 Evaluation Metrics

**Expected answer.** PSD: the suffix is privileged information used only in training, since the deployed model must rank from the prefix alone. IMFuse imposes no such asymmetry.

- [ ] verified
