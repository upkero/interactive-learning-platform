# Primitive framework (SCRUM-123)

The proposed cross-team contract is documented in [ADR-0010](../docs/adr/0010-primitive-contract.md).

`pnpm --filter @grasp/primitives storybook` opens the development showcase at
http://localhost:6006. Select **Primitives / Three frame**. This test fixture
adds two integers in three frames. It is not registered in the production
registry or sent to the resolver; the MVP selection belongs to section 3.4.

- **Add two**: automatic playback, continuing through inactive question frames.
- **Add zero**: predict whether adding zero increases the quantity.
- **Add one**: manual steps.
- **Invalid params**: a schema error instead of rendering the component.

Select an example and mode in Controls; switch `ru/en` and `light/dark` in the
toolbar. Actions records `step`, `predict` and `complete` events. Answer
buttons submit immediately, once per visit. Both correct and incorrect answers
unlock Next and reveal an explanation. Returning to a question resets the answer.

## Authoring

Each `src/primitives/<id>/index.ts` exports one `definePrimitive(...)` definition.
Add it to `src/registry.ts` and add a story for every named example. A definition
contains a Zod input schema, supported modes, translated label keys, component,
English description and 2–4 examples with `name`, `intent`, `mode`, `params`.

Descriptions explain domain concepts, when to select the primitive, and its
exclusions. An example intent is a realistic English resolver request. Every
schema field, including a discriminator, has English `.meta({ description })`; numbers and arrays have
explicit bounds and categorical strings use enums. Defaults are optional in the
exported input schema and are applied by `safeParse` before rendering.

Use `createStepPrimitive({ buildFrames, Scene, modes })` for a pure frame
builder and a scene renderer. No network, time or randomness in frame builders.
The shell renders an accessible fallback for empty sequences or sequences longer
than `MAX_FRAMES = 200`; the factory also catches errors while building frames.
The configured mode is fixed for the learner; an unsupported mode displays a
fallback. Parameter or externally configured mode changes reset the session; locale/theme
changes retain progress. Watch starts when visible, advances every 1200ms and
pauses at the final frame; reduced motion requires a manual start. Questions are
active in Predict, where Next is blocked until an answer.
Steps and Predict have no automatic playback control.

The public `StepControls` component also accepts optional `canAdvance`,
`showPlayback` and `playbackDisabled` props to control the Next button and
playback controls. Generated widgets should use this shared component when
they need step navigation, as required by checklist rule DS-04.

`labelKeys` lists all primitive-specific keys; common shell labels are supplied
by both exported dictionaries. `t` interpolates `{name}`, leaves missing values
visible, and warns about missing keys only in development.

## Consumer contract (application / backend handoff)

Application imports `getPrimitive` from `@grasp/primitives/registry` and the locale
from `@grasp/primitives/i18n/<locale>.json`. Resolve `primitive_id`, validate
`params` via `definition.paramsSchema.safeParse`, then render
`definition.component` with the parsed data, mode, labels and onEvent. Unknown
ids, invalid params or unsupported modes must use the application's fallback and
client logging. The application must also use an ErrorBoundary around each widget
to contain unforeseen scene-rendering errors. That integration is owned by the
application team. Since the package currently exports TypeScript sources, Next.js
consumers should add `@grasp/primitives` to `transpilePackages`.

`pnpm --filter @grasp/primitives catalog` produces canonical Draft 2020-12 input
schemas, examples, MVP modes, English descriptions and the existing design
checklist in `dist/catalog.json`. Its object shape is:

```json
{ "catalogVersion": 1, "design": {}, "primitives": [] }
```

`primitives` contains registered production entries (currently empty). This is
the published interface: backend consumes `catalog.primitives`, upserts by `id`,
and maps each `paramsSchema` to `params_schema`. `backend/resources/catalog.json` is an identical
generated delivery copy. After changing definitions, regenerate and copy:

```sh
pnpm --filter @grasp/primitives catalog
cp primitives/dist/catalog.json backend/resources/catalog.json
```

Backend owns seed, the Python `Draft202012Validator` integration test, and copying
resources into its image. This change does not implement or assert completion of
those backend tasks. Frontend-side Ajv Draft 2020-12 tests independently validate
every exported example and input defaults.

## Mobile question-panel contract

The question is in normal document flow below the scene/caption and above step
controls. At narrow widths options form a vertical list; no overlay, sticky panel
or focus trap. Keyboard focus stays on the navigation control on frame changes;
caption and answer feedback use polite live regions. Browser tests cover 320px
and both locales/themes. This is the proposed behavior for application-team
review, not a claim of team approval. Lead approval of the primitive contract is
also external to the implementation.

## Verification

```sh
pnpm --filter @grasp/primitives typecheck
pnpm --filter @grasp/primitives test
pnpm --filter @grasp/primitives lint
pnpm --filter @grasp/primitives check:contrast
pnpm --filter @grasp/primitives build-storybook
pnpm --filter @grasp/primitives exec playwright install chromium
pnpm --filter @grasp/primitives test-storybook
```

The browser suite serves the static artifact on 127.0.0.1:6007, tests all demo
examples across three modes, two locales and two themes, and checks invalid
parameters and existing UI stories. CI uploads `design-system-storybook`; extract
and serve it over HTTP (opening index.html via file:// is not supported).
