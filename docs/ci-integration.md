# CI Integration — Analysing Your Code with This SonarQube

How to add **automated, multi-language code analysis** to any repository using
the reusable workflows from
[`bauer-group/automation-templates`](https://github.com/bauer-group/automation-templates)
and **this** self-hosted SonarQube Server
(`https://sonarqube.development.app.bauer-group.com`).

> This server runs SonarQube Community Build **with the Community Branch Plugin**
> (see [branch-analysis.md](branch-analysis.md)), so **branch and pull-request
> decoration work** — not just main-branch analysis. Scanners authenticate with
> **user tokens** (see [security.md](security.md)).

Copy the parts you need into your repository. Everything **builds on the shared
reusable workflows** — no scanner logic is reinvented per repo.

---

## This repository (dogfooding)

XPD-SonarQube analyses **its own** code (the Python backup sidecar + the env
script) by reusing the shared workflow — see
[`.github/workflows/code-analysis.yml`](../.github/workflows/code-analysis.yml):

```yaml
jobs:
  code-quality:
    uses: bauer-group/automation-templates/.github/workflows/modules-code-quality.yml@main
    with:
      enable-sonar: true
    secrets: inherit
```

Project config is in [`sonar-project.properties`](../sonar-project.properties)
(`projectKey=bauer-group_xpd-sonarqube`, sources `src/sonarqube-backup/src` +
`scripts`). This is **Level A** (analysis only) — deliberately no hand-rolled
test job. It's tolerant: until the org secrets are granted to the repo, the
scan warns and skips. The sections below are the reusable patterns for **any**
consuming repo.

---

## 0. How it fits together

```text
your repo (.github/workflows/ci.yml)
        │  uses: …/<lang>-build.yml@main   with: enable-sonar: true
        ▼
automation-templates → <lang>-build.yml
        │  job: code-quality  (uses modules-code-quality.yml)
        ▼
modules-code-quality.yml → actions/sonar-scan → this SonarQube Server
```

Two integration levels — pick per repository:

| Level | What you get | Effort |
|-------|--------------|--------|
| **A — Analysis only** | Bugs, code smells, security hotspots, duplication. **No test coverage.** | One line: `enable-sonar: true` |
| **B — Analysis + coverage** | Everything above **plus** test coverage %. | A small per-language job that runs tests and the scan together |

> Coverage is **not** auto-handed from the build job to the analysis job, so
> Level A intentionally reports no coverage. Use Level B when you need coverage.

---

## GitHub App vs. the scanner (you need both)

Connecting SonarQube to GitHub via a **GitHub App** does **not** replace the CI
workflow — they do different jobs:

- **The scanner (CI workflow) does the analysis** — it clones the code, scans
  it and uploads the report. SonarQube Server **never fetches or analyses code
  itself** (there is no auto-analysis on the self-hosted server).
- **The GitHub App connects SonarQube to GitHub** — pull-request decoration
  (quality-gate check + issue comments), repository/project import, and
  optionally GitHub login. It runs **no** analysis.

```text
push / PR ─▶ CI workflow ─▶ scanner ─▶ SonarQube (analysis + quality gate)
                                              │
                                  GitHub App  ▼
                                    PR gets the check + comments
```

Without the workflow nothing is analysed; without the App there's no PR
decoration. The bundled **Community Branch Plugin uses this GitHub App
configuration** to decorate pull requests.

### Set up the GitHub App (once, org-wide)

Per the
[official SonarQube guide](https://docs.sonarsource.com/sonarqube-community-build/devops-platform-integration/github-integration/setting-up-at-global-level/setting-up-github-app).

1. **GitHub → Org → Settings → Developer settings → GitHub Apps → New GitHub App**
   - **GitHub App name:** e.g. `SonarQube`
   - **Homepage URL** and **Callback URL:** your SonarQube base URL —
     `https://sonarqube.development.app.bauer-group.com`
   - **Webhook:** **clear the *Active* checkbox** and clear the *Webhook URL* and
     *Webhook secret* fields (not used).
   - **Repository permissions:**
     - *Administration* → Read-only
     - *Checks* → Read & write
     - *Contents* → Read-only
     - *Metadata* → Read-only (mandatory)
   - **Organization permissions:**
     - *Administration* → Read-only
     - *Members* → Read-only
     - *Projects* → Read-only
   - **Account permissions:**
     - *Email addresses* → Read-only
   - **Where can this app be installed:** Only on this account
   - Create it, then **note the App ID**, **generate a Client secret**, and
     **generate a private key** (`.pem`).
2. **Install the App** on the org (all or selected repos): the App's page →
   *Install App*.
3. **SonarQube → Administration → Configuration → DevOps Platform Integrations →
   GitHub → Create configuration:**
   - Configuration name (free text)
   - **GitHub API URL:** `https://api.github.com` (for github.com)
   - **GitHub App ID**, **Client ID**, **Client secret**, and the **private key**
     (`.pem` contents)

   All of this lives in the SonarQube UI/database — **no env vars** (consistent
   with [authentication.md](authentication.md)).

> The above is the SonarSource-documented permission set (it also covers
> repository import and GitHub login). The bundled Community Branch Plugin posts
> PR decoration via the **Checks** permission; if you also want it to leave a
> summary **comment** on the PR, additionally grant *Pull requests → Read & write*.

### Bind a project (enables PR decoration)

- **New project:** *Projects → Create Project → GitHub* → pick the repo (uses
  the App), **or**
- **Existing project:** *Project → Administration → General Settings → DevOps
  Platform Integration* → select the GitHub configuration + repository.
- Ensure the CI job grants `pull-requests: write` (see the workflow examples
  below) so the decoration check can be posted.

> The same GitHub App can also provide **GitHub login** — an alternative to the
> [Entra ID / Zitadel SSO](authentication.md). Pick one identity provider; you
> don't need all of them.

---

## 1. Prerequisites (once per repository)

1. **Grant the repo access to the org secrets** (they exist organization-wide):
   - `SONARQUBE_TOKEN` — a SonarQube user token (My Account → Security → Tokens)
   - `SONARQUBE_HOST_URL` — `https://sonarqube.development.app.bauer-group.com`

   GitHub → Organization → *Settings → Secrets and variables → Actions* →
   open each secret → *Repository access* → add your repo.

2. **Create the project in SonarQube** and note its **Project Key**.

3. **Add `sonar-project.properties`** to the repo root (see §3).

No secrets are stored in the repo — they flow in via `secrets: inherit`.

---

## 2. Level A — analysis only (fastest)

Add `enable-sonar: true` to your existing build-workflow call. Done.

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

permissions:
  contents: read
  pull-requests: write   # lets SonarQube decorate the PR (branch plugin)

jobs:
  build:
    uses: bauer-group/automation-templates/.github/workflows/nodejs-build.yml@main
    with:
      enable-sonar: true          # default: false
    secrets: inherit              # provides SONARQUBE_TOKEN + SONARQUBE_HOST_URL
```

Swap `nodejs-build.yml` for `dotnet-build.yml`, `python-build.yml`, or
`php-build.yml` as needed — the `enable-sonar` input and `secrets: inherit`
pattern is identical for all four.

---

## 3. `sonar-project.properties` (per language)

Place this in the repo root. The coverage report path must match what your test
step produces (see §4).

```properties
# Common
sonar.projectKey=my-team_my-service
sonar.sources=src
sonar.tests=test
sonar.sourceEncoding=UTF-8

# --- pick the line(s) for your language ---
# Node.js / TypeScript
sonar.javascript.lcov.reportPaths=coverage/lcov.info
# Python
# sonar.python.coverage.reportPaths=coverage.xml
# PHP
# sonar.php.coverage.reportPaths=coverage.xml
# .NET (OpenCover)
# sonar.cs.opencover.reportsPaths=**/coverage.opencover.xml
```

---

## 4. Level B — analysis **with coverage** (tests + scan in one job)

Coverage requires the coverage report to exist in the same job that runs the
scan. Add a dedicated job that runs your tests **and then** calls the
`sonar-scan` composite action. `fetch-depth: 0` is required for accurate
new-code/branch detection.

### Node.js / TypeScript

```yaml
jobs:
  sonar:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: npm ci
      - run: npm test -- --coverage        # produces coverage/lcov.info
      - uses: bauer-group/automation-templates/.github/actions/sonar-scan@main
        with:
          sonar-host-url: ${{ secrets.SONARQUBE_HOST_URL }}
          sonar-token: ${{ secrets.SONARQUBE_TOKEN }}
```

### Python

```yaml
jobs:
  sonar:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install -r requirements.txt pytest pytest-cov
      - run: pytest --cov --cov-report=xml  # produces coverage.xml
      - uses: bauer-group/automation-templates/.github/actions/sonar-scan@main
        with:
          sonar-host-url: ${{ secrets.SONARQUBE_HOST_URL }}
          sonar-token: ${{ secrets.SONARQUBE_TOKEN }}
```

### PHP

```yaml
jobs:
  sonar:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: shivammathur/setup-php@v2
        with:
          php-version: '8.2'
          coverage: xdebug
      - run: composer install --no-interaction --prefer-dist
      - run: vendor/bin/phpunit --coverage-clover coverage.xml
      - uses: bauer-group/automation-templates/.github/actions/sonar-scan@main
        with:
          sonar-host-url: ${{ secrets.SONARQUBE_HOST_URL }}
          sonar-token: ${{ secrets.SONARQUBE_TOKEN }}
```

### .NET / C# (use the MSBuild scanner for full coverage)

For C#, the dedicated `dotnet-sonarscanner` (begin → build → test → end) gives
proper Roslyn-based analysis and coverage — better than the generic CLI scanner.

```yaml
jobs:
  sonar:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: actions/setup-dotnet@v4
        with: { dotnet-version: '8.0.x' }
      - uses: actions/setup-java@v4        # scanner needs a JRE
        with: { distribution: 'temurin', java-version: '17' }
      - run: dotnet tool install --global dotnet-sonarscanner
      - name: Begin analysis
        env:
          SONAR_TOKEN: ${{ secrets.SONARQUBE_TOKEN }}
          SONAR_HOST_URL: ${{ secrets.SONARQUBE_HOST_URL }}
        run: >
          dotnet sonarscanner begin
          /k:"my-team_my-service"
          /d:sonar.host.url="$SONAR_HOST_URL"
          /d:sonar.token="$SONAR_TOKEN"
          /d:sonar.cs.opencover.reportsPaths='**/coverage.opencover.xml'
      - run: dotnet build --no-incremental
      - run: dotnet test --collect:"XPlat Code Coverage;Format=opencover"
      - name: End analysis
        env:
          SONAR_TOKEN: ${{ secrets.SONARQUBE_TOKEN }}
        run: dotnet sonarscanner end /d:sonar.token="$SONAR_TOKEN"
```

> Tip: run tests/coverage in your normal build, and the `sonar` job above in
> parallel — or combine them if you want a single job.

---

## 5. Enforce the Quality Gate (optional)

By default the scan is **non-blocking** (it reports but never fails the build).
To make a failing Quality Gate fail the workflow:

- **Level A:** call `modules-code-quality.yml` directly with
  `fail-on-quality-gate: true`.
- **Level B:** add `fail-on-quality-gate: 'true'` to the `sonar-scan` step.

```yaml
  code-quality:
    uses: bauer-group/automation-templates/.github/workflows/modules-code-quality.yml@main
    with:
      enable-sonar: true
      fail-on-quality-gate: true
    secrets: inherit
```

---

## 6. Behaviour & tolerance

- **Opt-in:** nothing runs unless `enable-sonar: true` (build workflows) or you
  add the job explicitly.
- **Tolerant:** if the scan is enabled but `SONARQUBE_TOKEN` / `SONARQUBE_HOST_URL`
  are missing, it logs a **warning and skips** — it never fails the build.
- **Caching:** the scanner and analysis data are cached automatically.

---

## 7. Troubleshooting

| Symptom | Cause / Fix |
|---------|-------------|
| `SonarQube analysis was enabled but … not set` warning | Repo has no access to the org secrets — grant it (§1.1). |
| Coverage shows 0% | Level A reports no coverage by design — use Level B (§4) and verify the report path in `sonar-project.properties`. |
| `Project not found` | `sonar.projectKey` does not match the SonarQube project (§1.2). |
| New-code / branch / blame inaccurate | Ensure `fetch-depth: 0` on checkout. |
| PR not decorated | Caller must grant `pull-requests: write` (and this server has the branch plugin — see [branch-analysis.md](branch-analysis.md)). |
| `401 Unauthorized` | The `SONARQUBE_TOKEN` is invalid/expired — reissue the user token. |

---

## 8. Reference

- automation-templates: <https://github.com/bauer-group/automation-templates>
  - Module `modules-code-quality.yml`, action `.github/actions/sonar-scan`
- This server's branch/PR analysis: [branch-analysis.md](branch-analysis.md)
- Tokens & auth: [security.md](security.md) · [authentication.md](authentication.md)
- SonarSource action: <https://github.com/SonarSource/sonarqube-scan-action>
