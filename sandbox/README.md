# Widget sandbox (story 1.11)

`POST /run` accepts `source_tsx`, 1–3 `param_sets`, `mode`, `labels`, `locale`,
and an optional `viewport` (defaults to 800×500). Compilation errors are
HTTP 200 with `ok: false`. A full response has `compiled_js`,
`console_errors`, base64-encoded PNG `screenshots`, and `timings`.

The sandbox image builds `widget-host/host.html` from the same source that the
widget-host image serves. The page exposes `__graspHarness` only for direct
Playwright initialization; it also supports `grasp:init` messages from a parent
iframe. A production parent **must** use an iframe sandbox with `allow-scripts`
but **without** `allow-same-origin`. The host's CSP blocks external images and
reports attempted requests to the runner; the browser context separately
aborts requests that reach the network layer. The full widget iframe embedding workflow
belongs to story 3.5; this repository does not yet have a user-facing widget
renderer or judge model.

In Compose only the worker and sandbox join `sandbox_net` (`internal: true`).
The sandbox has no published ports and uses the Playwright v1.65 seccomp
profile (`infra/playwright-seccomp.json`) so Chromium's sandbox stays enabled.
Never add `--no-sandbox` or connect the sandbox to the default network.

Checks: `pnpm --filter sandbox test` checks compilation and queue limits;
`pnpm --filter sandbox build` compiles TypeScript. The CI `sandbox-integration`
job builds the sandbox and worker images, verifies browser screenshots and
failure recovery, checks `/health` and rendering from the worker image on an
internal network, and verifies that external HTTPS is unreachable.
