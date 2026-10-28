# Install Modal's Agent Skill in Antigravity (Windows)

The official Modal skill helps coding agents follow the current Modal SDK and deployment patterns. It is useful here because the project plans to use Modal for the Python API/background media-processing jobs.

## 1. Open the repository terminal in Antigravity

Confirm you are in the root of `lolixco-pilot`, not in the existing Lolixco repo.

## 2. Install or update the Modal CLI

Use whichever Python toolchain you normally manage CLI tools with. For a standard Windows Python installation, try:

```powershell
py -m pip install --upgrade modal
```

If the `modal` executable isn't found after installation, reopen the terminal or install it through your preferred `uv` CLI workflow.

## 3. Authenticate the Modal CLI

```powershell
modal setup
```

Complete browser authentication using your existing Modal account/workspace `golixco40`. Do not paste tokens into the chat or repository.

## 4. Install the agent skill and its documentation

```powershell
modal skills install
```

The default target is the standard `.agents/` skills directory. If Antigravity doesn't pick it up in the current session, restart/reload the workspace and ask it to read the installed `SKILL.md` files before changing Modal code.

Useful follow-up commands:

```powershell
modal skills show
modal skills update
modal --help
```

Official references:

- Modal skills CLI: https://modal.com/docs/cli/latest/skills
- Modal Python client/skills overview: https://github.com/modal-labs/modal-client
- Modal ASGI app: https://modal.com/docs/sdk/py/latest/asgi_app

## Secret policy

After the app architecture exists, create Modal secrets in the Modal dashboard/CLI for the server-side values needed by the app. Typical names are `MODEL_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and S3 signing credentials. These are examples of variable names, not secret values. Scope secrets to the functions that need them. Never commit a filled `.env` file.
