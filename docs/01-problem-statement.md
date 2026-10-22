# 1. Problem Statement

## 1.1 Background

Indian agriculture employs roughly 45 % of the workforce but contributes about 17–18 %
of the Gross Value Added, and the average holding is under two hectares. The problems
that dominate that picture are not a shortage of technology; they are a shortage of
**timely, affordable and specific advice**.

Three failures recur on smallholdings across the country:

1. **Late disease recognition.** A farmer usually notices a fungal or bacterial outbreak
   only after visual symptoms have spread across a third of the plot. By that point the
   chemical bill has doubled and much of the yield is unrecoverable.
2. **Sub-optimal crop choice.** Land is frequently assigned a crop based on habit or a
   neighbour's success rather than on the field's own nitrogen, phosphorus and potassium
   status, pH and the season's rainfall and temperature.
3. **No forward-looking yield picture.** A farmer who cannot estimate the harvest has
   no basis for negotiating a contract price, planning labour or ordering inputs.

The tools that do exist for these problems are either laboratory services (which are
accurate but out of reach of a smallholder) or consumer applications that give generic,
region-agnostic advice. Neither is a decision aid for a specific field.

## 1.2 Problem definition

> Build a single web platform that, given a photograph of a leaf, a set of soil and
> climate readings and a location, returns **specific, field-level and actionable**
> guidance: what disease the plant has and how to treat it, which crop to sow, roughly
> what the harvest will be worth, and what the weather will do — and that keeps a
> personal, auditable record of every recommendation made.

## 1.3 Objectives

| # | Objective | Success measure |
| --- | --- | --- |
| O1 | Classify crop disease from a leaf photograph | ≥ 38 PlantVillage classes with a calibrated confidence and the top-5 alternatives |
| O2 | Recommend a crop for a given soil/climate profile | Ranked list over 22 crops with a match score and a rationale |
| O3 | Estimate the expected harvest | Point estimate in t/ha with a 95 % planning interval |
| O4 | Add live weather context | Current conditions and a 7-day forecast for an arbitrary field |
| O5 | Persist everything the user does | Per-user, isolated, queryable history in MongoDB |
| O6 | Secure the platform | Argon2id hashing, JWT sessions, CSRF defence, RBAC, rate limiting, upload validation |
| O7 | Give administrators oversight | User directory, platform statistics, model status, audit trail |
| O8 | Stay honest | No fabricated predictions, metrics or weather — an unavailable model must be reported as unavailable |

## 1.4 Scope

**In scope**

- A responsive web application (desktop and mobile browser) with a public landing page.
- Account lifecycle: registration, sign-in, refresh, sign-out, profile management,
  password change.
- Three machine-learning capabilities: disease classification, crop recommendation,
  yield estimation.
- A weather service integrated from the server side.
- A personal dashboard and a full prediction history with search and pagination.
- An administrative console with role management and an audit trail.
- A REST API documented with OpenAPI/Swagger.

**Out of scope**

- Native mobile applications.
- Direct actuation of irrigation or spraying hardware.
- Satellite/drone imagery analysis.
- A marketplace, payment gateway or insurance module.
- On-device (offline) inference — the models are server-side only.

## 1.5 Stakeholders

| Stakeholder | Interest | What the platform gives them |
| --- | --- | --- |
| Smallholder farmer | Correct diagnosis and a workable plan | Field-specific disease identification, crop ranking, yield estimate |
| Agricultural extension officer | Reach and consistent messaging | Agronomic guidance attached to every diagnosis |
| Agronomy researcher | Labelled, structured field data | A growing corpus of prediction metadata (no image binaries) |
| System administrator | Operational safety and oversight | Admin console, audit trail, model status, rate limiting |
| College / examiner | A complete, working, honest system | Real datasets, real training, a real test suite, measured metrics |

## 1.6 Why a full-stack, ML-backed web application

The three requirements above are inseparable from each other in practice:

- A **diagnosis is only useful with a plan** — treatment, prevention and the caveat
  that a photograph is not a laboratory test. That content is part of the response
  contract, not an afterthought.
- A **recommendation is only trustworthy with its history** — a farmer needs to see
  what they were told last season and compare it with this season's readings.
- **Nothing is deployable without security and administration** — real user data and
  real accounts demand hashing, sessions, authorisation and an audit trail.

Therefore the deliverable is a complete web application rather than a notebook or a
standalone model.

## 1.7 Constraints and assumptions

| Type | Statement |
| --- | --- |
| Constraint | CPU-only execution environment — the models must be trainable and servable without a GPU budget. |
| Constraint | Cloud database access is credential-gated, so the schema and the data-access layer must be exercised against an emulator in CI. |
| Constraint | A public weather provider with no key must be used, so no secret is ever shipped to the browser. |
| Assumption | The PlantVillage images were captured under controlled conditions; field photographs will be harder, and this is stated in the limitations. |
| Assumption | Soil test values come from the farmer or an extension officer; the platform does not perform soil analysis. |
| Non-goal | The system is an **advisory** tool. Every model response carries an explicit disclaimer. |

## 1.8 Success criteria

1. `GET /api/v1/health` reports a healthy service with the real state of the database
   and each model.
2. All 180 backend tests pass, including the negative paths (unauthorised access,
   database outage, missing model, malformed image, out-of-range inputs).
3. The three models report measured metrics on a held-out split, published in
   `docs/07-results.md`.
4. A signed-in user can complete the full journey — register → analyse → review →
   export history — without a single console error and without leaving the SPA.
5. No request returns a fabricated result: absent capability ⇒ `503` with an
   actionable message.
