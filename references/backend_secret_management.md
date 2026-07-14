# Backend Secret Management

## Principle

Secrets are runtime configuration, not paper project state.

API keys, access tokens, passwords, session secrets, provider credentials, and signing keys must not be written into:

- `events/event_log.yml`
- `state/paper.yml`
- `proposals.yml`
- `Artifact` payloads or artifact files
- `visualization/*.json`
- `handoff_manifest.yml`
- repository files committed to Git

Project state may record only non-secret metadata:

```yaml
ai_provider:
  provider: openai
  model: gpt-5
  secret_ref: local:user-default-openai
```

Do not record:

```yaml
api_key: sk-...
authorization: Bearer ...
```

## Backend Components

The eventual backend should separate these responsibilities:

```text
Project Store
  event logs, projected state, artifacts, citations

Action Runtime
  proposal validation, human gates, apply, revert, projection

AI Runtime
  provider adapter, expert runner, AI checks, token/cost metadata

Secret Store
  user API keys, provider credentials, secret rotation/deletion

Redaction Layer
  logs, errors, manifests, visualization JSON, debug output
```

The AI runtime receives resolved secrets only at call time. Other layers should pass `secret_ref`, not raw secret values.

## Local Prototype

For a local desktop/single-user prototype, prefer OS-backed storage:

```text
Windows: Credential Manager
macOS: Keychain
Linux: Secret Service / libsecret
```

If OS-backed storage is not available yet, use local runtime files that are ignored by Git:

```text
.env.local
secrets.local.yml
secrets.local.json
.credentials/
.secrets/
```

These files are acceptable as a temporary local fallback only. They must not be copied into generated paper projects, handoff packages, or skill release zips.

## Web Backend

For a hosted multi-user backend:

- accept secrets only over HTTPS;
- encrypt secrets at rest;
- use KMS or an application master key outside the database;
- scope secrets per user or workspace;
- never return the full secret after submission;
- provide replace/delete controls;
- redact secrets from logs, traces, errors, and LLM prompts;
- record audit events such as `secret_ref_created` or `secret_ref_rotated`, not the secret value.

## Event Log and Handoff Rules

Event log entries may record:

```yaml
provider: openai
model: gpt-5
secret_ref: local:user-default-openai
secret_present: true
```

Event log entries must not record:

```yaml
api_key: sk-...
request_headers:
  Authorization: Bearer ...
```

Handoff manifests may record whether a required secret was configured, but not the secret:

```yaml
ai_runtime:
  provider: openai
  secret_present: true
  secret_ref: local:user-default-openai
```

If a project is shared, zipped, or committed, it must remain usable as a project without exporting the user's key.

## Redaction Rules

Before writing logs, manifests, visualizations, or debug output:

- replace known secret fields with `[REDACTED]`;
- redact `Authorization` headers;
- redact values for keys named `api_key`, `access_token`, `refresh_token`, `password`, `secret`, `client_secret`;
- do not include raw provider request headers in artifacts;
- do not put secrets into LLM prompt context, even for debugging.

If a secret is ever committed or shared, assume it is compromised and rotate it.

## Frontend Boundary

A future frontend settings page can let the user submit an API key, but the frontend should not persist it in local project files.

The frontend submits the key to the backend secret store and receives a stable reference:

```json
{
  "provider": "openai",
  "secretRef": "local:user-default-openai"
}
```

All later actions, proposals, and AI checks use `secretRef`.

## Validation Expectations

Future validators should fail or warn when they see likely secrets in:

- project event logs;
- projected state;
- artifact payloads;
- handoff manifests;
- visualization JSON;
- generated release packages.

The current `.gitignore` blocks common local secret files, but `.gitignore` is not the security boundary. The hard boundary is: raw secrets never become project data.
