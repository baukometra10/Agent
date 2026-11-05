# Operating rules (non-negotiable)

1. Do not assume project facts without evidence.
2. Distinguish **fact / inference / unverified** in every knowledge write.
3. Do not execute a change without understanding the affected surface.
4. Do not treat “code compiled/wrote successfully” as proof the change is correct.
5. Developers cannot self-approve; Independent Critic / Code Reviewer must review.
6. No merge/deploy without human approval (unless an explicit scoped permission exists).
7. Every change must be testable and reversible.
8. Every agent result must include evidence.
9. Projects never share workspaces, sandboxes, knowledge, or evolution state.
10. Continuous evolution may only propose and notify until a human confirms.
11. Email proposals must explain *why* the change is needed, expected impact, and risks.
12. Untrusted project code runs only inside Docker sandbox; disabled by default in Phase 1.
13. Real LoRA / GPU ownership proofs are deferred until full deploy on a private staging server; do not treat local placeholder adapters as production Coding readiness.
14. Public multi-tenant server comes only after staging validation (auth, billing, isolation, factory human gates).
15. Spixa Proprietary Intelligence Ecosystem is adopted: six specialties + Orchestrator; huge-from-scratch foundation training is not a success gate (`docs/SPIXA_INTELLIGENCE.md`).
16. Specialty maturity is judged by quality gates (success, benchmark, regression, cost/task, human acceptance, generalization, safety) — never by corpus or adapter counts. Production approve requires gates unless explicit staging `force`.
17. Model Independence Mode must be proven by an executable probe with externals disabled, not by a config flag alone.
