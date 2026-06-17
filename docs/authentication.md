# Authentication & SSO

SonarQube is a **developer tool** — developers should sign in with the identity
they already use for their **code platform**, not a corporate IdP. So the login
provider follows where the code lives:

| Code platform | SonarQube login | SonarQube support | Plugin |
| --- | --- | --- | --- |
| **GitHub** | GitHub authentication | **native** | none |
| **Codeberg** / self-hosted forge (Forgejo/Gitea) | **Zitadel** (generic OIDC) | via plugin | `sonar-auth-oidc` (bundled) |

> Corporate SAML / Microsoft Entra ID is intentionally **not** used here — it
> doesn't fit a developer product. Pick **one** provider for your instance.

Common to both:

- `SONARQUBE_SERVER_BASE_URL` (→ `SONAR_CORE_SERVERBASEURL`) must be the public
  HTTPS URL — the OAuth/OIDC redirect URLs are derived from it.
- Configured in the **SonarQube web UI** (Administration → Authentication);
  the property keys are listed for reference. Scanners are unaffected (below).
- Decide **"Allow users to sign up"** (auto-create accounts on first login) vs.
  admin-controlled; optionally restrict to your org/group.

---

## GitHub authentication (GitHub-hosted projects)

Native to SonarQube — and it **reuses the same GitHub App** you set up for PR
decoration (see [ci-integration.md](ci-integration.md)).

**1. In that GitHub App:**

- *Account permissions → Email addresses → Read-only* (already in the documented
  permission set).
- **User authorization callback URL:**
  `https://sonarqube.development.app.bauer-group.com/oauth2/callback/github`
- Note the **Client ID** and **generate a Client secret**.

**2. SonarQube → Administration → Authentication → GitHub:**

| UI field | Property | Example |
| --- | --- | --- |
| Enabled | `sonar.auth.github.enabled` | `true` |
| Client ID | `sonar.auth.github.clientId.secured` | *(from the App)* |
| Client secret | `sonar.auth.github.clientSecret.secured` | *(from the App)* |
| App ID | `sonar.auth.github.appId` | *(the App ID)* |
| GitHub API URL | `sonar.auth.github.apiUrl` | `https://api.github.com/` |
| GitHub web URL | `sonar.auth.github.webUrl` | `https://github.com/` |
| Allow users to sign up | `sonar.auth.github.allowUsersToSignUp` | `true` |
| Restrict to organizations | `sonar.auth.github.organizations` | `bauer-group` |
| Sync teams → groups | `sonar.auth.github.groupsSync` | `true` |

Developers then log in with **"Log in with GitHub"**. Restricting to your
organization(s) keeps it to your developers.

---

## Zitadel (generic OIDC — Codeberg / self-hosted forge)

When the code lives on **Codeberg / Forgejo / Gitea** (no native SonarQube auth
for those forges), broker login through **Zitadel** via OIDC. This uses the
third-party [`sonar-auth-oidc`](https://github.com/vaulttec/sonar-auth-oidc)
plugin (v3.0.0), which **ships in the wrapper image by default** — verified
booting on SonarQube 26.5. Omit it with `--build-arg INCLUDE_OIDC_PLUGIN=false`.

**1. Zitadel:** create an application of type **Web / OIDC**, set the redirect
URI to `https://sonarqube.development.app.bauer-group.com/oauth2/callback/oidc`,
and note the **Issuer**, **Client ID** and **Client Secret**.

**2. SonarQube → Administration → Authentication → OpenID Connect:**

| UI field | Property | Example |
| --- | --- | --- |
| Enabled | `sonar.auth.oidc.enabled` | `true` |
| Issuer URI | `sonar.auth.oidc.issuerUri` | `https://zitadel.example.com` |
| Client ID | `sonar.auth.oidc.clientId.secured` | *(from Zitadel)* |
| Client secret | `sonar.auth.oidc.clientSecret.secured` | *(from Zitadel)* |
| Scopes | `sonar.auth.oidc.scopes` | `openid email profile` |
| Login strategy | `sonar.auth.oidc.loginStrategy` | `Preferred username` |
| Groups sync | `sonar.auth.oidc.groupsSync` | `true` |
| Groups claim | `sonar.auth.oidc.groupsSync.claimName` | `groups` |
| Login button text | `sonar.auth.oidc.loginButtonText` | `Zitadel` |

---

## Scanners are unaffected

SSO governs **interactive** (browser) login only. CI scanners always authenticate
with **tokens** (My Account → Security → Tokens, or a project/global analysis
token) — see [ci-integration.md](ci-integration.md) and [security.md](security.md).
