# Portable Loader Prompt

Use this prompt in agents that do not natively discover `SKILL.md` folders, including Claude Code, Hermes, and OpenClaw deployments that receive skills as copied folders.

```text
You have access to a local skill named roll-cta at:
<ROLL_CTA_SKILL_ROOT>

When the user asks to compare futures roll rules, audit roll cost or roll gaps, reproduce a CTA roll ledger, or explain how roll timing changes real contract PnL:
1. Read <ROLL_CTA_SKILL_ROOT>/SKILL.md.
2. For API fields and data contracts, read <ROLL_CTA_SKILL_ROOT>/references/api_guide.md.
3. Use the local pandadata-api skill to verify exact method parameters before any real Pandadata call.
4. Set PANDA_DATA_USERNAME and PANDA_DATA_PASSWORD before fetching data, or pass config["data_dir"].
5. Preserve product universe, date range, cost assumptions, roll thresholds, and data dates.
6. Do not invent data interfaces, fields, prices, or trading advice.
```
