# Content Factory — OpenClaw Skill

Fully automated faceless YouTube channel. Send a topic via WhatsApp, get a documentary published at 9am.

## Install

```bash
bash install.sh
```

## Update your factory

Copy the files from `factory_updates/` into your `~/factory/` directory:

```bash
cp factory_updates/render_agent.py   ~/factory/agents/
cp factory_updates/upload_agent.py   ~/factory/agents/
cp factory_updates/config.py         ~/factory/core/
cp factory_updates/job_templates.json ~/factory/schemas/
cp factory_updates/start.sh          ~/factory/
```

## Usage

Start the factory:
```bash
bash ~/factory/start.sh
```

Message OpenClaw on WhatsApp:
```
make a video about the rise and fall of Nokia
```

That's it.
