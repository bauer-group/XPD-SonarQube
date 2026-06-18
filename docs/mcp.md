# SonarQube MCP Server (AI agents ↔ this SonarQube)

Lets AI coding agents (Claude Code, Cursor, VS Code / Copilot) query and act on
**this** SonarQube instance straight from the editor — "why is the quality gate
red?", "show the open blocker issues in project X", "check this snippet against
our rules".

It's a **read-mostly bridge**, not a second scanner: it surfaces what the CI
scan already produced. The chain is:

```text
CI scan ─▶ SonarQube ─▶ MCP server (local container) ─▶ your AI agent
```

Each developer runs it **locally** (STDIO transport) with their **own** token,
so actions are correctly attributed and scoped to that developer.

## Prerequisites (per developer)

- **Docker** — the MCP server runs as a short-lived local container.
- A SonarQube **user token**: `https://sonarqube.development.app.bauer-group.com`
  → *My Account → Security → Generate Tokens* (type: **User Token**).
  Project/global/analysis tokens (`sqp_`/`sqa_`) do **not** work here.

## Connection settings

- `SONARQUBE_URL` = `https://sonarqube.development.app.bauer-group.com`
- `SONARQUBE_TOKEN` = your user token
- No `SONARQUBE_ORG` — that's a SonarQube **Cloud**-only setting.
- Image: `mcp/sonarqube` (auto-pulled `latest`) — or pin
  `sonarsource/sonarqube-mcp:1.19.0.2785` for reproducibility.

## Setup per client

### Claude Code

```bash
claude mcp add sonarqube \
  --env SONARQUBE_URL=https://sonarqube.development.app.bauer-group.com \
  --env SONARQUBE_TOKEN=<YOUR_USER_TOKEN> \
  -- docker run --init --pull=always -i --rm \
       -e SONARQUBE_TOKEN -e SONARQUBE_URL mcp/sonarqube
```

### Cursor / generic MCP client

```json
{
  "mcpServers": {
    "sonarqube": {
      "command": "docker",
      "args": ["run", "--init", "--pull=always", "-i", "--rm",
               "-e", "SONARQUBE_TOKEN", "-e", "SONARQUBE_URL", "mcp/sonarqube"],
      "env": {
        "SONARQUBE_TOKEN": "<YOUR_USER_TOKEN>",
        "SONARQUBE_URL": "https://sonarqube.development.app.bauer-group.com"
      }
    }
  }
}
```

### VS Code (`.vscode/mcp.json`)

```json
{
  "inputs": [
    { "id": "sonarqube_token", "type": "promptString",
      "description": "SonarQube user token", "password": true }
  ],
  "servers": {
    "sonarqube": {
      "command": "docker",
      "args": ["run", "--init", "--pull=always", "-i", "--rm",
               "-e", "SONARQUBE_TOKEN", "-e", "SONARQUBE_URL", "mcp/sonarqube"],
      "env": {
        "SONARQUBE_TOKEN": "${input:sonarqube_token}",
        "SONARQUBE_URL": "https://sonarqube.development.app.bauer-group.com"
      }
    }
  }
}
```

### Optional: project-scoped `.mcp.json` (Claude Code)

Commit a `.mcp.json` at a repo root that references the token via **env var**
(no secret in git) so contributors get the server automatically once they export
`SONARQUBE_TOKEN`:

```json
{
  "mcpServers": {
    "sonarqube": {
      "command": "docker",
      "args": ["run", "--init", "--pull=always", "-i", "--rm",
               "-e", "SONARQUBE_TOKEN", "-e", "SONARQUBE_URL", "mcp/sonarqube"],
      "env": {
        "SONARQUBE_TOKEN": "${SONARQUBE_TOKEN}",
        "SONARQUBE_URL": "https://sonarqube.development.app.bauer-group.com"
      }
    }
  }
}
```

## What you can ask it (≈70 tools)

- **Issues & hotspots:** search issues, change issue status, search/show/change
  security hotspots.
- **Quality:** project quality-gate status, list quality gates, component
  measures, search metrics, duplications, coverage.
- **Code intelligence:** `analyze_code_snippet`, source/SCM lookup, rules
  (`show_rule`, `list_languages`).
- **Projects:** search your projects, list pull requests.
- **System:** health, status, logs, ping.

Most tools are read-only; the few write tools (issue/hotspot status, webhooks)
act **as you**, via your token.

## Security

- The user token carries **your** SonarQube permissions — keep it private, never
  commit it, and rotate it periodically.
- STDIO means the container runs **locally** and talks only to SonarQube — nothing
  is exposed publicly.
- Scanners/CI are unaffected — they keep using their own analysis tokens
  (see [ci-integration.md](ci-integration.md)).
