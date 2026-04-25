from prompts.loader import load_prompt, load_system_prompt

SEO_AGENT_SYSTEM_PROMPT = load_system_prompt("seo_system.md")
SEO_KICKOFF             = load_system_prompt("seo_kickoff.md")

seo_synthesis_prompt = load_prompt("seo_synthesis.md")
