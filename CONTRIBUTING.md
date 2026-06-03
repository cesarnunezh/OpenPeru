# Collaboration Principles

## Coordination
Tasks are tracked through GitHub issues. Each GitHub issue is tracked on GitHub Projects, moving through the stages of "Backlog," "To Do," "In Progress," "On Hold," and "Done." Once issues are in the "In Progress" stage there will be a single issue owner who is responsible for updating each project, assigned on GitHub.

Beyond GitHub issues, minor project communication will also go through CAPP Slack for coordination and quick updates quick updates. Project information will be shared on GitHub in formal documentation

There will not be any regularly scheduled meetings, except as needed.

### Decisions

César and José are project leaders. They will make key design and architecture decisions about how the product is created. Contributors will make implementation decisions. In other words, decisions on "what" to make and the tools to use will be made by César and José. Decisions on "how" to use the tools will be made by the implementor.

Decisions on feature implementation are up to the programmer. Individual design decisions on technology will be recorded in the /documentation/ directory. In that directory, there will be files for major design decisions, API performance, norms (ex., using camel case for front end, what low-level abstractions will use) and architecture.

Decisions should be justified by (1) user needs, then (2) project goals, and finally (3) personal opinions of the implementor. Implementation decisions will be owned by the implementor of the feature, including discussion with the César and José as appropriate.

The project will aim to avoid over-discussing decisions. To do so, we provide broad leeway to the programmer and include a robust quality assurance process so that major decisions have two eyes over them. These are described more in the code collaboration section.

## Code collaboration

### Commits

Each commit will be, ideally, a single unit of work, in the sense that each commit will have an specific isolated advancement and it will be named properly (no "idk :/", "trying", or "asd" as name).

In general, this will mean also to don't do too many different things in the same commit (e.g. ideally one commit will be "adds submit button", not "adds submit button, fixes data model, and updates server").

Commits should follow the conventional commits guidelines for commit syntax.

### Pull requests

Everyone merges their own code, after meeting the following criteria:

* Style: has been linted
* Validated: pass all already existing tests and has new tests if it introduces new features/fixes bugs not  previously tested, and;
* Documented: any PR includes updates to  the documentation with new features or API changes.
* Reviewed: has been reviewed for  another person.

For the creation of the pull request, include a summary of what the new/modified code does in the description of the pull request on Github. Delete the branch after pulling if the task for that branch has been completed by that pull.

The project will include a pull request template that tracks these requirements.

### Branching

There will be no long-lived branches for the project, only `main`.

All branches will be short-lived branches related to additions/modifications of specific features. Since each issue is a feature that means a contributor can have multiple active short-lived branches at different times if these branches reflect sets of unrelated changes. Those branches would be related to different issues and are not dependent one of the other.

### Generative AI

We will use AI tools as references, but we should write our own code. Specifically, we can ask AI tools to:

* Provide existing solutions related to features we're trying to implement when we get stuck
* Explain how a particular function works
* Help explain error messages
* Proofread documentation
* Make proper citations for AI-generated code
* Refactoring with human review
* Generate test cases

AI should never be used to support both test generation and code generation. A human should be fully responsible for either (1) making the feature work (code) or (2) making the standards of how a feature works (tests).

This is meant to provide protections against subtle architectural decisions and bugs introduced by AI, which cannot fully understand context.
