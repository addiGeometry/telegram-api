## Development Principles

1. No artifacts.
2. Less code is better than more code.
3. No fallback mechanisms — they hide real failures.
4. Rewrite existing components over adding new ones.
5. Flag obsolete files to keep the codebase lightweight.
6. Avoid race conditions at all costs.
7. Always output the full component unless told otherwise.
8. Never say "X remains unchanged" — always show the code.
9. Be explicit on where snippets go (e.g., below "abc", above "xyz").
10. If only one function changes, just show that one.
11. Take your time to ultrathink when on extended thinking mode — thinking is cheaper than fixing bugs.