# Authentication & SSO

SonarQube Community Build has a built-in user store (local accounts) and
supports single sign-on. This stack is prepared for two providers:

| Provider | Protocol | SonarQube support | Plugin needed |
| --- | --- | --- | --- |
| Microsoft **Entra ID** | SAML 2.0 | **native** (Community Build) | no |
| **Zitadel** | generic OIDC | via third-party plugin | **yes** — `sonar-auth-oidc` |

Common prerequisites:

* `SONARQUBE_SERVER_BASE_URL` (→ `SONAR_CORE_SERVERBASEURL`) must be the public
  HTTPS URL — SAML/OIDC redirect URLs are derived from it.
* After enabling an IdP, set **Administration → Security → "Allow users to
  sign up"** to off if you want admin-/IdP-controlled accounts only.
* Auth-provider settings are applied in the **SonarQube web UI** (stored in the
  database). The exact property keys are listed below for reference/automation;
  whether they can also be injected via `SONAR_*` environment variables depends
  on the SonarQube version, so the UI is the reliable path.

---

## Microsoft Entra ID (SAML 2.0)

No plugin required — SAML is built into Community Build.

**1. Entra ID (Azure portal) → Enterprise applications → New → Create your own:**
* Identifier (Entity ID) = `sonarqube` (matches `sonar.auth.saml.applicationId`)
* Reply URL (ACS) = `https://<your-host>/oauth2/callback/saml`
* Add claims for login / name / email / groups; download the **Base64 signing
  certificate** and note the **Login URL** and **Microsoft Entra Identifier**.

**2. SonarQube → Administration → Authentication → SAML** (property keys):

| UI field | Property | Example |
| --- | --- | --- |
| Enabled | `sonar.auth.saml.enabled` | `true` |
| Application ID | `sonar.auth.saml.applicationId` | `sonarqube` |
| Provider name | `sonar.auth.saml.providerName` | `Entra ID` |
| Provider ID (IdP entity ID) | `sonar.auth.saml.providerId` | `https://sts.windows.net/<tenant>/` |
| SAML login URL | `sonar.auth.saml.loginUrl` | `https://login.microsoftonline.com/<tenant>/saml2` |
| Identity provider certificate | `sonar.auth.saml.certificate.secured` | _(Base64 cert)_ |
| Login attribute | `sonar.auth.saml.user.login` | `http://schemas.../emailaddress` |
| Name attribute | `sonar.auth.saml.user.name` | `http://schemas.../name` |
| Email attribute | `sonar.auth.saml.user.email` | `http://schemas.../emailaddress` |
| Group attribute (optional) | `sonar.auth.saml.group.name` | `groups` |

Test with the **"Test configuration"** button on the SAML settings page before
rolling out.

---

## Zitadel (generic OIDC)

SonarQube has no native generic-OIDC; this uses the third-party
[`sonar-auth-oidc`](https://github.com/vaulttec/sonar-auth-oidc) plugin
(v3.0.0), which **ships in the wrapper image by default** — verified booting on
SonarQube 26.5 (the plugin deploys and registers cleanly). To omit it, build
with `--build-arg INCLUDE_OIDC_PLUGIN=false`.

**1. Zitadel:** create an application of type **Web / OIDC**, set the redirect
URI to `https://<your-host>/oauth2/callback/oidc`, and note the **Issuer**,
**Client ID** and **Client Secret**.

**2. SonarQube → Administration → Authentication → OpenID Connect** (property keys):

| UI field | Property | Example |
| --- | --- | --- |
| Enabled | `sonar.auth.oidc.enabled` | `true` |
| Issuer URI | `sonar.auth.oidc.issuerUri` | `https://zitadel.example.com` |
| Client ID | `sonar.auth.oidc.clientId.secured` | _(from Zitadel)_ |
| Client secret | `sonar.auth.oidc.clientSecret.secured` | _(from Zitadel)_ |
| Scopes | `sonar.auth.oidc.scopes` | `openid email profile` |
| Login strategy | `sonar.auth.oidc.loginStrategy` | `Preferred username` |
| Groups sync | `sonar.auth.oidc.groupsSync` | `true` |
| Groups claim | `sonar.auth.oidc.groupsSync.claimName` | `groups` |
| Login button text | `sonar.auth.oidc.loginButtonText` | `Zitadel` |

---

## Scanners under SSO

SSO governs **interactive** login. CI scanners keep using **user tokens**
(My Account → Security → Tokens) — SSO does not change that.
