# v5 research dossier: market sizes (for M43a)

**Status:** starting list (2026-11-17). The M43a session finds a published 2025 size (and where possible 2010 and 2020) for every category in `categories.yaml`, cites it, and records the definition used. Use a consistent source family where possible (Gartner IT spending, IDC, Statista, company reports, IEA for vehicles), and note the range where sources disagree.

## Anchors

- **World GDP:** about $110 trillion nominal (2024–2025), IMF World Economic Outlook *(verify)*; regional GDP from the IMF for the game's regions *(verify)*.
- **Worldwide IT spending:** about $5.4–5.7 trillion (2025), Gartner *(verify)*, about 5% of world GDP. Gartner's segments: data centre systems, devices, software, IT services, communications services.
- **Generative AI and AI models:** model APIs and AI software revenue in 2024–2025 (OpenAI about $3.7B in 2024 and higher in 2025; Anthropic; Google, Microsoft and AWS AI services), and broader "AI software" estimates (IDC, Gartner) *(verify)*. The game's `ai_models` definition must be pinned: model APIs and AI applications, or also AI cloud infrastructure (which `cloud_hosting` and the chip categories may already count).

## Per category (find each)

- `b2b_saas`, `consumer_apps`, `dev_tools`, `cloud_hosting` (public cloud IaaS and PaaS: about $400–500B in 2025 *(verify)*), `fintech`, `ai_models`, `devices` (smartphones about $450–500B *(verify)*), the chip categories (`chips_mobile`, `server_cpu`, `ai_accelerator`: data-centre AI chips about $150–250B in 2025 *(verify)*), `vehicles` (M38's), the medical sub-categories (M41's), robotics (M39's).
- For each: 2010, 2020 and 2025 sizes; definition; source.

## Ceilings

- Long-run IT spending share of GDP (historically about 4–6%) *(verify)*; highest share any single segment has reached (software about 1.1–1.3% of world GDP) *(verify)*; long-run real GDP growth assumptions (IMF, OECD long-term scenarios) *(verify)*.
