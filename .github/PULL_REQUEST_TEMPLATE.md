## Author commitment

Before opening an integration PR, I confirm that:

- I understand the third-party API areas I implemented.
- I can explain every action, endpoint, permission, dependency, and important helper.
- I used the documented Autohive SDK process and repository conventions.
- I reviewed the generated or written code myself.
- I removed dead code, generic boilerplate, hallucinated behavior, and unnecessary abstractions.
- I tested the integration with meaningful mocked tests.
- I included real API integration tests where safe and practical, or documented why not.
- I ran local validation and fixed issues before requesting review.
- I documented the integration clearly for users and future maintainers.

If I cannot honestly confirm these points, the PR is not ready.


## Review standard

Reviewers are expected to hold integration PRs to this charter.

A PR may be sent back even if CI passes when the author has not demonstrated API understanding, intentional scope, safe permissions, meaningful tests, maintainable Python, or adequate self-review.

The goal is not to slow down integration development. The goal is to decrease time to develop and maintenance by avoiding shipping code we do not understand, cannot maintain long term, or cannot safely stand behind.

If you are unsure about anything on the above to help you move forward in the integration, reach out to a peer to get clarity
