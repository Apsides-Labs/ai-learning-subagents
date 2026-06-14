# Article candidates

Tick `[x]` the ones you want written (change `[ ]` to `[x]`), tweak titles/angles
inline if you like, then run `--mode produce` on the ticked ones.

SEO numbers come from DataForSEO (US, English). `n/a` = no data returned for that keyword.

---

### 1. Your first agent loop will fail here: the control points that actually matter
- [ ] write this
- Segment: developer building their first agent loop and realizing the model is not the only moving part
- Angle: Focuses on the places beginners usually ignore — state transitions, stop conditions, and tool calls — instead of treating an agent as a prompt plus autonomy.
- Primary keyword: agent loop control points  (volume n/a · difficulty n/a)
- SERP: reachable — top results are blogs / smaller sites
    - blogs.oracle.com — What Is the AI Agent Loop? The Core Architecture Behind ...
    - code.claude.com — How the agent loop works - Claude Code Docs
    - stevekinney.com — The Anatomy of an Agent Loop
- Type: standard · Category: AI Engineering

---

### 2. Design tools for agents like an interface, not like a script
- [ ] write this
- Segment: developer wiring the first real tool into an agent and unsure why results are flaky
- Angle: Shows how tool contracts, argument shape, and error surfaces change agent behavior, and why “just expose the API” is usually a mistake.
- Primary keyword: design tools for ai agents  (volume n/a · difficulty n/a)
- SERP: mixed — 1/5 top results are high-authority
    - www.anthropic.com — Writing effective tools for AI agents—using ...
    - www.reddit.com — My guide on what tools to use to build AI agents (if you are ...
    - www.mindstudio.ai — MindStudio: Build powerful AI agents
- Type: standard · Category: AI Engineering

---

### 3. When memory makes your agent worse: the point where recall turns into noise
- [ ] write this
- Segment: builder adding memory after a prototype works once but starts drifting on longer runs
- Angle: Explains the tradeoff between helpful persistence and polluted context, with a practical cutoff for when to store, summarize, or drop state.
- Primary keyword: agent memory tradeoffs  (volume n/a · difficulty n/a)
- SERP: reachable — top results are blogs / smaller sites
    - valkey.io — Reduce Token Cost for LLMs: AI Agent Memory with ...
    - www.techtarget.com — What Is AI Agent Memory? Types, Tradeoffs and ...
    - sqlsummit.com — Agent Memory Design: Short-Term vs. Long-Term Tradeoffs
- Type: standard · Category: AI Engineering

---

### 4. One agent or many? The moment multi-agent systems become expensive theater
- [ ] write this
- Segment: developer tempted to split tasks into multiple agents after reading about orchestration
- Angle: Helps readers decide when multiple agents add real separation of concerns versus when they just add latency, confusion, and more failure modes.
- Primary keyword: multi agent systems tradeoffs  (volume n/a · difficulty n/a)
- SERP: reachable — top results are blogs / smaller sites
    - www.dataiku.com — Single-agent vs. multi-agent systems: enterprise AI tradeoffs
    - zilliz.com — How do multi-agent systems balance trade-offs?
    - www.reddit.com — Are multi-agent systems actually better than a single ...
- Type: standard · Category: AI Engineering

---

### 5. CLAUDE.md is not documentation; it is your repo’s operating contract
- [ ] write this
- Segment: Claude Code user setting up a project for the first time and trying to make the assistant stay consistent
- Angle: Treats the file as a behavioral contract with conventions for style, boundaries, and project rules, not as a dumping ground for notes.
- Primary keyword: claude.md conventions  (volume n/a · difficulty n/a)
- SERP: mixed — 1/5 top results are high-authority
    - uxplanet.org — CLAUDE.md Best Practices
    - ranthebuilder.cloud — Claude Code Best Practices: Lessons From Real Projects
    - github.com — case/docs/conventions/claude-md-ordering.md at main
- Type: topic_teaser · Category: Claude Code

---

### 6. Stop rewriting the same prompt: use a slash command when the workflow is fixed
- [ ] write this
- Segment: Claude Code user repeating the same multi-step task across branches or files
- Angle: Shows where slash commands beat copy-pasted prompts: repeatable work that deserves a named command and a predictable output shape.
- Primary keyword: claude code slash commands  (volume 880 · difficulty 32)
- Secondary keywords: claude code custom slash commands, slash commands claude code, claude code slash commands github
- SERP: mixed — 1/5 top results are high-authority
    - code.claude.com — Commands - Claude Code Docs
    - www.reddit.com — Here are 50+ slash commands in Claude Code that most of ...
    - www.youtube.com — Claude Code Tutorial #6 - Slash Commands
- Type: topic_teaser · Category: Claude Code

---

### 7. Subagents are for narrow jobs, not extra intelligence
- [ ] write this
- Segment: Claude Code user considering subagents after the main agent keeps losing focus on a long task
- Angle: Clarifies when a subagent is worth the overhead and when a simpler single-agent workflow is more reliable.
- Primary keyword: claude code subagents  (volume 2900 · difficulty 18)
- Secondary keywords: how to use subagents in claude code, awesome claude code subagents, awesome-claude code subagents
- SERP: mixed — 1/5 top results are high-authority
    - anthropic.skilljar.com — Introduction to subagents - Anthropic Courses
    - www.reddit.com — What's your best way to use Sub-agents in Claude Code so ...
    - github.com — VoltAgent/awesome-claude-code-subagents
- Type: standard · Category: Claude Code

---

### 8. MCP is only useful when your assistant needs a real boundary
- [ ] write this
- Segment: Claude Code builder deciding whether to connect an external system through MCP instead of a one-off integration
- Angle: Frames MCP as an interface choice, with emphasis on permissioning, portability, and keeping the assistant from becoming a bespoke script pile.
- Primary keyword: mcp servers for claude code  (volume 170 · difficulty 17)
- Secondary keywords: slack mcp for claude code, mcp for claude code, supabase mcp for claude code
- SERP: reachable — top results are blogs / smaller sites
    - www.reddit.com — The 10 best MCP servers for Claude Code right now (2026 ...
    - platform.claude.com — MCP connector - Claude API Docs
    - claudemarketplaces.com — MCP Servers | Discover Model Context Protocol Servers
- Type: standard · Category: Claude Code

---

### 9. The Python you actually need for agent work starts with dataclasses and typing
- [ ] write this
- Segment: Python learner who can write loops and functions but freezes when a codebase starts using types and structured objects
- Angle: Targets the practical gap between “I know Python” and “I can maintain an agent project,” using the subset that makes code easier to reason about.
- Primary keyword: python dataclasses and typing  (volume n/a · difficulty n/a)
- SERP: mixed — 2/5 top results are high-authority
    - stackoverflow.com — python - type hint for an instance of a non specific dataclass
    - typing.python.org — Dataclasses — typing documentation
    - education.molssi.org — Python Type Hints, Dataclasses, and Pydantic
- Type: standard · Category: Python

---

### 10. Async in Python stops being scary once you know what is waiting on what
- [ ] write this
- Segment: Python dev debugging a slow API-backed agent and realizing synchronous code is the bottleneck
- Angle: Explains async in terms of concurrent waiting, not theory, so readers can decide when it helps and when it just adds complexity.
- Primary keyword: python async for beginners  (volume n/a · difficulty n/a)
- SERP: hard — 3/5 top results are high-authority domains
    - realpython.com — Python's asyncio: A Hands-On Walkthrough
    - docs.python.org — A Conceptual Overview of asyncio
    - bbc.github.io — Python Asyncio Part 1 – Basic Concepts and Patterns
- Type: standard · Category: Python

---

### 11. In JavaScript, runtime and browser are different worlds — and your AI app depends on both
- [ ] write this
- Segment: backend-minded builder adding a frontend to an AI service and mixing up what can run where
- Angle: Covers the practical boundary between Node and the browser, especially when shipping an AI interface that needs streaming, state, and environment variables.
- Primary keyword: javascript browser vs node  (volume n/a · difficulty n/a)
- SERP: hard — 4/5 top results are high-authority domains
    - nodejs.org — Differences between Node.js and the Browser
    - www.w3schools.com — Node.js vs Browser
    - www.reddit.com — What is the difference between Javascript and Node.js?
- Type: standard · Category: JavaScript

---

### 12. Learn a new framework by shipping the smallest broken version of it
- [ ] write this
- Segment: developer starting a framework or AI SDK with an assistant and not knowing how to avoid doc paralysis
- Angle: Gives a concrete learning loop: build the tiniest end-to-end slice, let the assistant fill gaps, then iterate from failures instead of reading everything first.
- Primary keyword: how to learn a framework by building  (volume n/a · difficulty n/a)
- SERP: reachable — top results are blogs / smaller sites
    - www.reddit.com — What is the best way to learn new frameworks/libraries ...
    - dev.to — Best way to learn a framework/language
    - brianjenney.medium.com — The 3-Step Learning Framework No One Taught You
- Type: topic_teaser · Category: Developer Workflow
