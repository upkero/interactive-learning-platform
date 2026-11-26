# Source-only reference cases

`manifest.json` lists three independent Russian source parts and their verbatim
case-sensitive glossaries. `ru_water_injection` includes the exact adversarial
instruction required by story 2.2. These files are inputs, not model answers.

For a future live evaluation, run each of these three sources and both parts
in `../document.json` through the real main pass. Save each returned draft as
`outputs/<case-id>.json`, with `model`, `prompt_version`, `generated_at`, and
`draft` fields. Alternatively pass the output directory to
`python -m evals.term_check [outputs_dir]`. The checker reports missing outputs
and metadata; metadata documents provenance but cannot prove it. Check the
first response with `check_draft` before repair; compare every glossary term
and every returned `key_terms` entry against the resulting Markdown with
`evals.term_check`. For the injection case also check that the
response is a normal page and did not obey the instruction. Record the model,
prompt version, date, and whether repair was needed alongside the outputs.
Do not treat this source corpus as evidence that any live evaluation passed.

To collect the snapshots, configure the Anthropic model and API key and run
`python -m evals.main_pass_live OUTPUT_DIRECTORY` with an empty output directory.
This makes paid calls and may retry. `summary.json` records the fraction of
first schema-valid drafts with semantic violations, including those later
repaired; failures before a schema-valid draft are excluded from that fraction
and listed separately. The command also runs the terminology checker. The
injection response still needs the separate security assessment above.

New snapshots also include the first schema-valid draft and its alternation
and other semantic violations. The summary reports alternation separately and
counts cases with a schema retry before that first valid draft. If a later step
fails, the first draft is saved in `<case-id>.first.json`; that partial file
does not count as a completed terminology snapshot. These files contain model
responses and should be handled accordingly. Existing snapshots do not contain
the first answer and cannot establish which original rule was violated.

`outputs_sonnet55/` contains the saved Sonnet 5.5 drafts used by the
terminology checker. `outputs/` and `outputs_round2/` preserve earlier
Sonnet 4.6 runs, including their observed failures. Each is a single run
with its own prompt version.

`live_acceptance_v1.json` records the new `main-pass-v1` check on the commit
and prompt hash listed there. Its five reference requests failed before a
draft could be recorded. The earlier drafts and `live_acceptance.json`
remain historical evidence for their recorded prompt hashes.
