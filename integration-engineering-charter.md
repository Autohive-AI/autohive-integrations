# Integration Engineering Charter


## Preamble

Autohive integrations connect our users' workflows to third-party systems they rely on. A poor integration does not only produce bad code; it can break customer workflows, mishandle data, request excessive permissions or create long-term maintenance burden for the team.

AI-assisted development is a requirement, but authorship cannot be delegated to AI. The person opening the PR is responsible for understanding the provider API, the Autohive SDK, the implementation choices, the tests, the security implications, and the user experience.

Passing CI is the minimum technical gate. It is not proof that an integration is well-designed, well-understood, safe, or maintainable.


## Our principles

### 1. We understand the API before we wrap it

An integration author must read the provider's official API documentation and understand the endpoints, authentication model, scopes, pagination, rate limits, errors, and provider-specific behavior they are implementing.

We do not build integrations by guessing from examples, copying generated code, or trusting AI output without verification.

### 2. We build for user workflows, not endpoint coverage

A good integration is not a mechanical mirror of a 3rd-party API. It exposes actions that make sense for real Autohive workflows.

We intentionally choose what to include, what to leave out, and how to present actions so users can succeed without needing to understand the provider API.

### 3. We own AI-generated code

AI can help draft, explore, refactor, and test. It cannot fully own correctness.

If AI generated part of an integration, the author is responsible for reviewing it, simplifying it, removing hallucinated behavior, checking it against documentation, and making sure they can explain it.

Code that the author cannot explain is not ready for review.

### 4. We write maintainable Python

Integrations should be idiomatic, readable Python. The code should use simple data structures, clear control flow, accurate type hints where useful, and appropriate async patterns.

We avoid unnecessary abstractions, complicated cleverness, dead code, broad exception swallowing, hidden side effects, and dependencies that are not clearly justified.

### 5. We treat auth and permissions as security decisions

Scopes, permissions, credentials, files, and user data require care. Integrations should request the correct access needed for the implemented actions.

Secrets must never be committed in this repo. Test data must be safe. Provider responses should not leak credentials or sensitive data through logs, errors, or outputs.

### 6. We verify behavior, not just syntax

Tests should prove that actions behave correctly, handle errors, and match real provider response shapes.

Mocked tests are necessary, but they are not enough for integrations that depend on third-party APIs. Where credentials and safe test data are available, integration tests should exercise real API behavior. If real API tests are not included, the PR should explain why and describe how the real API behavior was verified.

### 7. We document what future maintainers need to know

A good README explains what the integration does, how authentication works, where the official API docs are, what actions exist, and any important provider limitations.

Documentation should describe the integration as shipped, not as imagined future work.

### 8. We self-review before asking others to review

Opening a PR is a request for another person's time and judgment. Authors should review their own diff first, run the review skill, remove low-quality artifacts, run local validation, check tests, and ensure the PR is focused.

Reviewers should not be the first people to discover obvious AI boilerplate, unused code, missing tests, hallucinated endpoints, excessive scopes, or unverified behavior.
