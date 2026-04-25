from prompts.loader import load_prompt, load_system_prompt

RESEARCH_SETUP_SYSTEM_PROMPT  = load_system_prompt("research_setup_system.md")
RESEARCH_SETUP_KICKOFF        = load_system_prompt("research_setup_kickoff.md")
RESEARCH_MARKET_SYSTEM_PROMPT = load_system_prompt("research_market_system.md")
RESEARCH_MARKET_KICKOFF       = load_system_prompt("research_market_kickoff.md")

research_setup_synthesis_prompt  = load_prompt("research_setup_synthesis.md")
research_market_synthesis_prompt = load_prompt("research_market_synthesis.md")
