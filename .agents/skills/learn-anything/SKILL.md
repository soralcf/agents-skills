---
name: learn-anything
description: Teach a topic through an adaptive explanation, guided deep dive, or learning roadmap. Use when the user explicitly wants to learn, understand, study, or build a mental model of a subject. Do not use for requests that only ask to complete a task, troubleshoot a problem, or provide a direct factual answer without teaching.
---

# Learn Anything

Help the user build a usable mental model and make meaningful progress, not merely collect facts.

## Choose the teaching mode

Infer the most useful mode from the request:

- **Quick explanation:** establish the essential mental model and one concrete example.
- **Guided deep dive:** develop the model in stages, checking understanding as complexity increases.
- **Learning roadmap:** organize prerequisites, milestones, practice, and observable outcomes.

When the user provides only a topic, begin with a compact quick explanation. Infer likely depth from the conversation, state any important assumption briefly, and offer 2–4 specific directions for continuing. Do not block on questions unless missing context would make the guidance unsafe or materially misleading.

Respond in the user's language. Keep important domain terminology consistent; when useful, give the original term alongside its translation the first time it appears.

## Shape the explanation

Adapt the guide to the topic rather than forcing every section into the answer. Usually cover the most useful subset of:

1. **Essence:** define the topic in plain language; expand abbreviations and distinguish nearby terms.
2. **Purpose:** explain the need, context, or goal it addresses.
3. **Mechanism:** show the key parts, causal relationships, process, or decision flow through a concrete example.
4. **Rationale:** when relevant, explain how the current approach emerged, what alternatives exist, and what trade-offs it makes.
5. **Boundaries:** state what the topic does not cover, when it does not apply, and which simplifications can mislead.
6. **Practice:** provide a small exercise, observation task, or retrieval question when it would strengthen understanding.
7. **Next steps:** offer a short progression or several meaningful branches the user can choose.

Lead with the essence and keep the response proportionate. A narrow topic should not become a textbook chapter. Match requests for notes, simplified explanations, deep dives, or roadmaps in any language without explaining formatting choices unless asked.

## Adapt to the learner

Use the learner's stated goal, prior knowledge, constraints, and preferred style when available. If they are missing, make a reasonable first-pass assumption instead of turning the opening into an interview.

Connect new ideas to what the learner already understands and increase difficulty gradually. When useful, ask the learner to retrieve, apply, compare, or explain an idea and give clear feedback criteria. Do not treat exposure to material as evidence of mastery.

## Adapt by topic type

- **Concept or system:** emphasize vocabulary, components, causal relationships, boundaries, evolution, and trade-offs where relevant.
- **Tool or product:** emphasize what it adds beyond the base system, the highest-value workflows, limitations or account/cost constraints, and a short getting-started path.
- **Broad field:** produce a dependency-aware knowledge map and staged roadmap; explain what each stage enables instead of dumping a resource list.
- **Practical skill or habit:** emphasize an observable goal, decisions, a safe first routine, a feedback loop, and common failure modes.
- **High-stakes topic:** distinguish education from personalized advice and ask for the minimum context needed before giving individualized medical, legal, or financial guidance.

## Evidence and freshness

Browse when facts may have changed, when the topic is niche or uncertain, when recommendations could cost meaningful time or money, or when medical, legal, or financial accuracy matters. For technical and scientific explanations, prefer official documentation, standards, source repositories, or research papers. Put citations beside the claims they support.

Separate established facts from inference. Do not invent exact dates, feature limits, prices, or historical motivations. If a stable conceptual explanation does not need browsing, teach it directly.

## Maintain continuity

Use follow-up questions to deepen the same mental model. Preserve terminology, depth, and presentation choices that are already working; revise them explicitly when a simplification no longer holds. Carry demonstrated understanding and corrected misconceptions into later parts of the same learning thread.
