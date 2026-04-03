"""
Bundled skills — built-in skills shipped with claw-code.

Ports: skills/bundled/*.ts
"""
from __future__ import annotations

from dataclasses import dataclass

from .loader import Skill


@dataclass(frozen=True)
class BundledSkillDef:
    """Definition of a bundled skill."""
    name: str
    description: str
    tags: list[str]
    content_template: str


_BUNDLED_SKILLS: list[BundledSkillDef] = []


def _md(name: str, description: str, body: str, tags: list[str] | None = None) -> BundledSkillDef:
    return BundledSkillDef(
        name=name,
        description=description,
        tags=tags or [],
        content_template=body,
    )


# ---------------------------------------------------------------------------
# Register all bundled skills
# ---------------------------------------------------------------------------

_BUNDLED_SKILLS.extend([
    _md(
        name="debug",
        description="Systematic debugging methodology — reproduce, isolate, fix, verify",
        body="""\
# Debug Skill

Use this skill when you need to debug an issue systematically.

## Methodology

1. **Reproduce** — Get the exact error with clear steps to reproduce it
2. **Isolate** — Narrow down to the smallest possible failing case
3. **Hypothesize** — Identify the root cause (not the symptom)
4. **Fix** — Implement the fix
5. **Verify** — Confirm the fix resolves the original problem

## Before Debugging Anything

- Get the exact error message and stack trace
- Identify which file/function/line the error originates from
- Check git log for recent changes that might have introduced the bug

## Python Debugging Checklist

- Print the types and values of variables at key points
- Check for None/null before accessing attributes
- Verify list indices are in bounds
- Check for off-by-one errors in loops
- Verify import paths are correct

## When Stuck

- rubber duck: explain the problem out loud line by line
- binary search: comment out half the code to find which half causes the error
- simplify: create a minimal reproduction case
""",
        tags=["debugging", "methodology"],
    ),

    _md(
        name="verify",
        description="Code verification — run tests, check types, lint",
        body="""\
# Verify Skill

Use this skill after making changes to ensure correctness.

## Verification Steps

### 1. Syntax & Type Check
Run the appropriate checker for the language:
- Python: mypy or pyright
- TypeScript: tsc --noEmit
- Ruby: ruby -c

### 2. Lint
- Python: ruff, flake8, pylint
- TypeScript: eslint
- Shell: shellcheck

### 3. Tests
Run the relevant test suite:
```bash
pytest tests/
npm test
```

### 4. Manual Review
- Read the changed code back
- Ask: "Does this do what the comment claims?"
- Check edge cases (empty input, large input, errors)

## Pre-commit Checklist
- [ ] All tests pass
- [ ] No new lint errors introduced
- [ ] Types are correct
- [ ] Error cases are handled
- [ ] Docs updated if needed
""",
        tags=["testing", "verification", "qa"],
    ),

    _md(
        name="remember",
        description="Persist important facts across sessions for this project",
        body="""\
# Remember Skill

Use this skill to store important facts, decisions, and context for this project.

## Usage

When something important happens, ask yourself:
- Will I need to know this in a future session?
- Is this a decision that was made?
- Is there context that would help a future session?

## What to Remember

### Project Facts
- Architecture decisions and why they were made
- Key dependencies and their versions
- Custom configurations
- Gotchas or known issues

### Decisions Made
- Why a particular approach was chosen
- What alternatives were considered
- What was explicitly rejected and why

### Context
- What the project does
- Who the stakeholders are
- Important dates or milestones

## How to Remember

Use the Session Memory tool to store facts:
```
set(key, value, tags=["context", "important"])
```

## Example

If you discover the project uses a custom logging format:
```
Remember: This project uses a custom JSON log format defined in src/utils/logging.py
  key: log_format
  value: JSON with timestamp, level, message, and metadata fields
  tags: architecture, logging
```
""",
        tags=["memory", "context", "documentation"],
    ),

    _md(
        name="simplify",
        description="Refactor complex code to be simpler and more readable",
        body="""\
# Simplify Skill

Use this skill when code is overly complex and needs to be refactored.

## Simplicity Principles

1. **Clear over clever** — Code is read more than it's written
2. **Do one thing well** — Split functions that do multiple things
3. **Name reveals intent** — Variables and functions should be self-documenting
4. **Delete dead code** — If it's not used, remove it
5. **Prefer composition** — Small pieces that fit together over big monolithic blocks

## Refactoring Triggers

- Function longer than 20-30 lines
- More than 3 levels of nesting
- Repeated code patterns (copy-paste)
- Magic numbers or strings without explanation
- Comments that explain *what* instead of *why*

## Techniques

### Extract Function
```python
# Before: long function doing multiple things
def process(data):
    # validate
    # transform
    # save
    ...

# After: each step is clear
def process(data):
    validate(data)
    transformed = transform(data)
    save(transformed)
```

### Replace Magic Number with Constant
```python
MAX_RETRIES = 3  # matches backend rate limit

def call_api():
    for i in range(MAX_RETRIES):
        ...
```

### Use Standard Library
Before writing utility code, check if Python already has it:
- collections.Counter, defaultdict
- itertools for sequence operations
- functools for higher-order functions
""",
        tags=["refactoring", "readability", "best-practices"],
    ),

    _md(
        name="stuck",
        description="When you're blocked — structured problem-solving approach",
        body="""\
# Stuck Skill

Use this skill when you're blocked on a problem and need a structured approach.

## Step 1: Clarify

Before solving anything, make sure you understand:
- What is the exact expected behavior?
- What is the actual behavior?
- What are the exact steps to reproduce?

## Step 2: Decompose

Break the problem into smaller pieces:
- Which part is unclear?
- What information is missing?
- What have you already tried?

## Step 3: Research

- Search for the error message
- Check documentation for the tool/library
- Look at similar problems in the codebase
- Check git history for related changes

## Step 4: Ask for Help

If you've spent meaningful time stuck:
- State the problem clearly
- Share what you've tried
- Share the relevant code/error
- Ask a specific question

## When to Escalate

- The problem involves infrastructure you can't access
- A dependency is broken in a way you can't fix
- You're repeating the same unsuccessful attempts

## Anti-Stuck Mindset

- "Stuck" is part of the process, not a failure
- Narrowing down a problem IS progress
- A different approach is often better than pushing through
- Take a break — your brain continues working on problems in the background
""",
        tags=["problem-solving", "methodology", "help"],
    ),

    _md(
        name="api-review",
        description="Review API changes for correctness, security, and usability",
        body="""\
# API Review Skill

Use this skill when reviewing or designing APIs.

## Questions to Ask

### Correctness
- Does the API do what the documentation claims?
- Are all parameters validated?
- Are error cases handled gracefully?
- Is the response format consistent?

### Security
- Is authentication required and enforced?
- Are inputs sanitized against injection?
- Is rate limiting in place?
- Are secrets kept out of logs and error messages?

### Usability
- Are error messages helpful?
- Does the API have sensible defaults?
- Is the API consistent with similar APIs?
- Can a caller use the API correctly without reading the source?

### Performance
- Are expensive operations async where appropriate?
- Is pagination used for large result sets?
- Are appropriate HTTP status codes used?

## Common Issues

- Using POST for everything (vs GET for reads, DELETE for removes)
- Returning 200 OK for errors
- Leaking internal error details to clients
- Missing or incorrect Content-Type headers
""",
        tags=["api", "review", "security", "design"],
    ),

    _md(
        name="security",
        description="Security checklist for code changes",
        body="""\
# Security Skill

Use this skill when reviewing or writing security-sensitive code.

## Input Validation
- Never trust user input — validate and sanitize everything
- Use allowlists over denylists where possible
- Validate type, format, length, and range
- Sanitize before storing or displaying

## Authentication & Authorization
- Verify auth tokens on every request
- Check permissions before each action
- Don't rely solely on client-side checks
- Log authentication failures

## Secrets Management
- Never commit secrets to version control
- Use environment variables or secret managers
- Rotate secrets regularly
- Don't log secrets (even partial)

## Data Handling
- Encrypt sensitive data at rest
- Use HTTPS for all network communication
- Don't store passwords — store salted hashes
- Be careful with PII — minimize collection

## Injection Prevention
- Parameterize all database queries
- Escape output based on context (HTML, SQL, shell)
- Don't use user input in file paths without validation
- Validate file types, not just extensions

## Security Checklist
- [ ] All user input is validated
- [ ] SQL queries use parameterized statements
- [ ] No secrets in code or logs
- [ ] Auth checks on every protected action
- [ ] Errors don't leak sensitive info
- [ ] Dependencies are up to date
""",
        tags=["security", "review", "best-practices"],
    ),

    _md(
        name="update-config",
        description="Update project configuration files safely",
        body="""\
# Update Config Skill

Use this skill when modifying project configuration files.

## Before Editing Config

1. Read the existing config fully
2. Understand what each setting does
3. Check for schema/validation rules
4. Back up the original (git will handle this, but confirm)

## Common Config Files

| Type | Files |
|------|-------|
| Python | pyproject.toml, setup.py, .env |
| Node | package.json, tsconfig.json |
| Project | CLAUDE.md, AGENTS.md |
| Editor | .editorconfig, .prettierrc |

## Best Practices

- Use environment variables for secrets
- Keep configs version-controlled
- Document non-obvious settings
- Use config schemas when available
- Validate after making changes

## Config Pattern

```python
# Good: environment-based config
API_KEY = os.environ.get("API_KEY")  # must be set
TIMEOUT = int(os.environ.get("TIMEOUT", "30"))  # default 30

# Bad: hardcoded secrets
API_KEY = "sk-1234567890abcdef"
```
""",
        tags=["configuration", "best-practices"],
    ),
])


def get_bundled_skill(name: str) -> Skill | None:
    """Return a bundled skill by name, or None if not found."""
    for defn in _BUNDLED_SKILLS:
        if defn.name == name:
            return Skill(
                name=defn.name,
                description=defn.description,
                content=defn.content_template,
                source="bundled",
                tags=defn.tags,
            )
    return None


def list_bundled_skills() -> list[Skill]:
    """Return all bundled skills."""
    return [
        Skill(
            name=d.name,
            description=d.description,
            content=d.content_template,
            source="bundled",
            tags=d.tags,
        )
        for d in _BUNDLED_SKILLS
    ]


__all__ = [
    "BundledSkillDef",
    "get_bundled_skill",
    "list_bundled_skills",
]
