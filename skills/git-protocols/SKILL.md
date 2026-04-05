# Git Protocols Skill

Expert in Conventional Commits and high-quality Merge Request descriptions.

## Instructions
When activated, you MUST ensure all Git operations follow these standardized protocols.

### 1. Conventional Commits
- Every commit MUST follow the format: `<type>: <description>`
- Types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`.
- Subject line: Max 50 characters.
- Body: Explain "why" the change was made, if not obvious.

### 2. Merge Request (MR) Description Protocol
Every MR description MUST follow this exact structural template for clarity:

# [MR Title: Conventional Commit Format]

## 📝 Context
[Explain why this change is necessary. Link to any relevant task IDs or issues.]

## 🚀 Changes
[Provide a bulleted list of high-level implementation details.]
- ...

## 🛡️ Impact & Risks
[Describe how this affects the system, performance, or other developers.]

## ✅ Verification & Testing
[Detail how the changes were verified. List specific tests run and their results.]
