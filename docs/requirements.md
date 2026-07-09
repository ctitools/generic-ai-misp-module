# Requirements Document

## Introduction

This feature defines a **Generic AI MISP Module**: a reusable base for AI-powered MISP
enrichment modules, plus the specific modules that inherit from it. The base module
accepts Cyber Threat Intelligence (CTI) report text (or a text/comment MISP attribute),
calls a configurable local or OpenAI-compatible backend with a deterministic fallback,
and returns MISP-standard enrichment results (Attributes, Objects, an EventReport, and
Tags). Specific modules (CTI info extraction, CTI NER / tag proposal, summarization, and
an ML "best-practice checker") reuse the base through object-oriented composition and add
only their own prompt, schema, and post-processing.

The current repository holds a thin summarization-only scaffold at
`expansion/generic_ai.py`. This spec re-designs that scaffold into a maintainable,
inheritance-friendly base while preserving the MISP core module contract, the deterministic
fallback, and the `misp_standard` output format.

The single highest-priority, non-negotiable value is **human maintainability**: excellent,
copy-pasteable documentation and very low code complexity ("less == more"). Completeness of
extraction never justifies increased code complexity. Maintainability constraints are
first-class acceptance criteria in this document, not aspirations.

All work stays within the Chosen Stack defined in `AGENTS.md`: Python 3.14/3.13/3.12, `uv`,
`pytest`, standard-library first. **No new third-party runtime dependency (except for 
explicitly approved dependencies , such as `pydantic`, `pydantic-ai`, `click`, `rich`) may be 
assumed or introduced by these requirements unless explicitly confirmed by the user.** 
Any requirement that would need a new dependency must instead be satisfied with the standard 
library, or be raised with the user for explicit approval before design.

## Glossary

- **Generic_AI_Module**: The reusable base module that implements the MISP core module
  contract, backend invocation, deterministic fallback, AI taxonomy tagging, and the
  `misp_standard` result assembly. Concrete modules inherit from it. It follows the MISP Modules contract. 
  See https://github.com/MISP/misp-modules 
- **Specific_Module**: A concrete module (for example CTI info extraction, NER / tag
  proposal, summarization, ML checker) that inherits from the Generic_AI_Module and
  supplies only its own prompt, extraction schema, and result mapping.
- **CTI_Report**: The input threat-intelligence text supplied to a module, either as raw
  `text` or as a MISP `text`/`comment` attribute value.
- **Backend**: The configured inference endpoint. Supported values are an Ollama endpoint
  or an OpenAI-compatible endpoint.
- **Deterministic_Fallback**: The stdlib-only, input-derived code path that produces a
  result without a Backend, used when no Backend is configured or a Backend call fails.
- **MISP_Attribute**: A typed MISP data element (for example `ip-src`, `domain`, `url`,
  `md5`, `sha256`, `email-src`, `vulnerability`, `filename`).
- **MISP_Object**: A structured MISP template grouping related attributes (for example
  `file`, `vulnerability`).
- **Galaxy_Cluster**: A MISP galaxy reference used for TTP and actor mapping (for example
  MITRE ATT&CK technique, threat-actor).
- **EventReport**: A markdown MISP EventReport returned as an enrichment result or as input
  to the AI MISP modules (CTI info extraction, tagging  may operate on the raw markdown text
  of an EventReport).
- **AI_Taxonomy_Tags**: Machine tags drawn from the `ai-computer-assisted` and `eu-ai-act`
  MISP taxonomies that mark content as AI-produced.
- **AI_Computer_Assisted_Taxonomy**: The MISP taxonomy at
  `misp-taxonomies/ai-computer-assisted/machinetag.json`.
- **EU_AI_Act_Taxonomy**: The MISP taxonomy at `misp-taxonomies/eu-ai-act/machinetag.json`.
- **Pinned_Tag_Set**: The exact predicate/value machine tag strings copied from the two
  taxonomy `machinetag.json` files and recorded in the repository.
- **Assistance_Level**: The `ai-computer-assisted` predicate expressing how much the AI
  contributed (for example an AI-generated value versus an AI-assisted value).
- **Review_Level**: The `ai-computer-assisted` predicate expressing review lifecycle state
  (for example unreviewed versus human-reviewed).
- **TLP_Level**: The Traffic Light Protocol classification supplied in the request as
  `tlp_level`, governing whether content may leave the MISP boundary.
- **External_Backend**: A Backend that is not on the operator-declared trusted/local
  network boundary.
- **Golden_File**: A committed known-good output file under `outputs/` compared against
  fresh module output for a fixed input.
- **Canonical_Fixture**: The fixed input file `tests/fixtures/orkl-sample.txt`.
- **Content_Hash**: A stable SHA-256 hash of the normalized source text used to detect
  input drift and stabilize golden comparisons.
- **MISP_Module_Server**: The `misp-modules` process that exposes `/version`, `/modules`,
  and `/query` and loads the module.
- **Cyclomatic_Complexity**: A per-function control-flow complexity metric measured by the
  repository linters.

## Requirements

### Requirement 1: MISP Core Module Contract

**User Story:** As a MISP administrator, I want the module to implement the standard
misp-modules contract, so that MISP core can discover and invoke it without custom glue.

#### Acceptance Criteria
1. THE Generic_AI_Module SHALL expose an `introspection` function returning a specification
   that declares the supported input attribute types, the output types, and `format` set to
   `misp_standard`.
2. THE Generic_AI_Module SHALL expose a `version` function returning module metadata that
   includes the module name, version, author, description, `module-type`, and config keys.
3. THE Generic_AI_Module SHALL expose a `handler` function that accepts a JSON string query
   and returns a result dictionary containing either a `results` object or an `error` field.
4. WHEN the `handler` function is invoked with a falsy or empty query, THE Generic_AI_Module
   SHALL return the misp-modules discovery response without raising an exception.
5. WHEN the MISP_Module_Server requests `/modules`, THE Generic_AI_Module SHALL be listed
   with its introspection metadata.
6. WHEN a `/query` request names the module and provides a supported input, THE
   Generic_AI_Module SHALL return results in `misp_standard` format.
7. THE Generic_AI_Module SHALL declare `module-type` values of `expansion` and `hover`.
8. IF a request omits required input fields, THEN THE Generic_AI_Module SHALL return an
   `error` field with a human-readable message naming the missing input, without raising an
   unhandled exception and without partial results.
9. IF a request supplies an attribute whose `type` is unsupported, THEN THE Generic_AI_Module
   SHALL return a descriptive `error` object rather than raising an exception.

### Requirement 2: Enrichment Output Contract

**User Story:** As a MISP analyst, I want enrichment results in the standard result shape,
so that MISP stores extracted data and reports on the correct event.

#### Acceptance Criteria

1. THE Generic_AI_Module SHALL return a `results` object that always contains the keys
   `Attribute`, `Object`, `EventReport`, and `Tag`, with each key present as a list even
   when the list is empty.
2. WHEN extraction produces one or more indicators, THE Generic_AI_Module SHALL populate
   `results.Attribute` with entries that each declare a MISP_Attribute type and a
   corresponding value.
3. WHEN extraction produces two or more related indicators that match a recognized
   MISP_Object template, THE Generic_AI_Module SHALL populate `results.Object` with one
   MISP_Object entry per matched template grouping.
4. THE Generic_AI_Module SHALL return at least one EventReport entry in `results.EventReport`,
   and each entry SHALL contain a non-empty markdown summary and traceability metadata
   identifying the source `content_hash` and the `model_id`.
5. THE Generic_AI_Module SHALL include a `metadata` block reporting non-empty values for
   `status_code`, `model_id`, `model_fingerprint`, `content_hash`, `mode`,
   `use_case_category`, and a timestamp expressed in ISO 8601 UTC format.
6. IF no indicators are extracted, THEN THE Generic_AI_Module SHALL return `results.Attribute`
   and `results.Object` as empty lists together with at least one EventReport entry, and
   SHALL NOT return an error object.

### Requirement 3: Zero-Configuration Ease of Use

**User Story:** As a MISP analyst, I want to click enrich and get useful results without
tuning parameters, so that AI enrichment requires no per-request setup.

#### Acceptance Criteria

1. WHERE a MISP administrator has set module configuration once, THE Generic_AI_Module SHALL
   run using those stored configuration values as defaults without requiring any per-request
   parameter beyond the supported input attribute.
2. WHEN a request supplies only a supported input attribute and no optional parameters, THE
   Generic_AI_Module SHALL return a result containing all of the `Attribute`, `Object`,
   `EventReport`, and `Tag` keys (with empty lists where nothing is produced) using the
   stored configuration defaults.
3. THE Generic_AI_Module SHALL expose configuration keys for Backend selection, endpoint
   address, model identifier, request timeout, and TLP handling, and SHALL report these keys
   in its `version` config metadata.
4. WHERE the module runs as `module-type` `hover`, THE Generic_AI_Module SHALL return a
   human-readable summary that contains only summary text (no structured extraction block)
   and does not exceed 1000 characters.
5. IF an optional configuration value is absent from a request and from the stored
   configuration, THEN THE Generic_AI_Module SHALL apply the default value documented in its
   `version` config metadata and SHALL produce a result rather than an error.

### Requirement 4: Structured CTI Extraction Scope

**User Story:** As a CTI analyst, I want the module to extract structured attributes and
objects from report text, so that I get machine-usable indicators and not only prose.

#### Acceptance Criteria

1. WHEN a CTI_Report is processed for extraction, THE Generic_AI_Module SHALL extract exactly
   one MISP_Attribute entry per distinct in-scope indicator value found in the source text,
   for the enumerated in-scope types: `ip-src`, `ip-dst`, `domain`, `hostname`, `url`, `md5`,
   `sha1`, `sha256`, `email-src`, `email-dst`, `vulnerability` (CVE), and `filename`.
2. WHEN two or more extracted attributes describe the same file (file hashes, optionally with
   a filename), THE Generic_AI_Module SHALL group them into a `file` MISP_Object; and WHEN a
   CVE reference is extracted, THE Generic_AI_Module SHALL produce a `vulnerability`
   MISP_Object.
3. WHEN a CTI_Report references adversary techniques or actors, THE Generic_AI_Module SHALL
   map them only to existing Galaxy_Cluster references (MITRE ATT&CK technique clusters and
   threat-actor clusters) matched by name or ID, and SHALL NOT invent new clusters.
4. THE Generic_AI_Module SHALL treat the attribute, object, and galaxy scope in criteria 1
   through 3 as the complete definition of "most important" for this feature, and SHALL
   document any type outside that scope as explicitly out of scope.
5. WHERE a Specific_Module narrows or extends the extraction scope, THE Specific_Module
   SHALL declare its scope explicitly rather than relying on implicit behavior.
6. IF an extracted indicator has a type outside the in-scope set in criterion 1, THEN THE
   Generic_AI_Module SHALL exclude it from results.
7. IF a referenced technique or actor has no matching existing Galaxy_Cluster, THEN THE
   Generic_AI_Module SHALL omit it rather than fabricate a cluster.

### Requirement 5: Generic Base and Inheritance

**User Story:** As a module developer, I want specific AI modules to inherit from one
generic base, so that I add a new use-case with minimal duplicated code.

#### Acceptance Criteria
1. THE Generic_AI_Module SHALL implement backend invocation, deterministic fallback, AI
   taxonomy tagging, and result assembly as reusable base behavior exposed through
   inheritable methods that a Specific_Module does not redefine.
2. WHERE a Specific_Module is created, THE Specific_Module SHALL inherit the base behavior
   and SHALL define only these three extension points: its prompt, its extraction schema,
   and its result mapping.
3. THE feature SHALL provide exactly four Specific_Module implementations, one each for CTI
   info extraction, CTI NER / tag proposal, summarization, and ML best-practice checking.
4. THE Specific_Module implementations SHALL NOT redefine any method or function that the
   Generic_AI_Module already provides other than the three extension points named in
   criterion 2, and the repository duplicate-logic linters (ruff, pylint, semgrep) SHALL
   report zero duplicated logic blocks between any Specific_Module and the Generic_AI_Module.
5. WHEN the Generic_AI_Module base behavior changes, THE Specific_Module implementations
   SHALL exhibit the changed behavior with zero edits to any Specific_Module source file, as
   verified by an automated test.
6. IF a Specific_Module does not supply one of the three required extension points (prompt,
   extraction schema, or result mapping), THEN THE Generic_AI_Module SHALL raise a
   descriptive error identifying the missing extension point at instantiation rather than
   producing a result.

### Requirement 6: AI Taxonomy Tagging and Pinning

**User Story:** As a compliance-conscious analyst, I want every AI-produced element tagged
with the correct AI taxonomies, so that AI provenance is auditable per MISP and the EU AI
Act.

#### Acceptance Criteria

1. THE feature SHALL fetch the `machinetag.json` files for the AI_Computer_Assisted_Taxonomy
   and the EU_AI_Act_Taxonomy and record the resulting Pinned_Tag_Set as a committed
   repository file holding exact `predicate="value"` machine-tag strings, including the
   confirmed `ai-computer-assisted` values `assistance-level="ai-generated"`,
   `assistance-level="ai-assisted"`, `review-level="unreviewed"`, and
   `review-level="human-reviewed"`.
2. WHEN the Generic_AI_Module produces an AI-generated EventReport, Attribute, or Object,
   THE Generic_AI_Module SHALL attach to that element one AI_Computer_Assisted_Taxonomy tag
   and one EU_AI_Act_Taxonomy tag, each matching a Pinned_Tag_Set entry verbatim.
3. WHEN the module produces unattended output, THE Generic_AI_Module SHALL set the
   Assistance_Level tag to `assistance-level="ai-generated"`.
4. WHEN an element is first produced by the module, THE Generic_AI_Module SHALL set the
   Review_Level tag to `review-level="unreviewed"`.
5. WHERE an analyst confirms an element, THE Generic_AI_Module SHALL support transitioning
   the Review_Level tag from `review-level="unreviewed"` to `review-level="human-reviewed"`.
6. IF a required machine tag value is absent from the Pinned_Tag_Set, THEN THE feature SHALL
   fail its taxonomy validation check with a descriptive error identifying the missing
   predicate/value, and SHALL NOT attach an unpinned tag string.
7. WHERE the module produces an analyst-confirmed proposal, THE Generic_AI_Module SHALL set
   the Assistance_Level tag to `assistance-level="ai-assisted"`.

### Requirement 7: TLP Governance

**User Story:** As a data-protection-conscious analyst, I want restricted TLP content kept
away from external backends, so that classified intelligence does not leak.

#### Acceptance Criteria

1. THE Generic_AI_Module SHALL read the `tlp_level` value from the request and SHALL
   normalize it against the recognized TLP_Level values `tlp:clear`/`tlp:white`, `tlp:green`,
   `tlp:amber`, `tlp:amber+strict`, and `tlp:red`.
2. IF the request omits `tlp_level` or supplies a value that does not match a recognized
   TLP_Level, THEN THE Generic_AI_Module SHALL treat the content as the most restrictive
   TLP_Level (`tlp:red`) for the purpose of Backend routing.
3. IF the normalized `tlp_level` is at or above the operator-configured restriction threshold
   (default: `tlp:amber`, `tlp:amber+strict`, or `tlp:red`) AND the selected Backend is an
   External_Backend, THEN THE Generic_AI_Module SHALL NOT transmit any CTI_Report content to
   that Backend and SHALL return a descriptive refusal that identifies the applied TLP_Level
   and the Backend classification.
4. WHEN content is withheld from an External_Backend for TLP reasons, THE Generic_AI_Module
   SHALL produce the result using the Deterministic_Fallback and SHALL record the
   withholding, the applied TLP_Level, and the restriction threshold in the result metadata.
5. WHERE the operator marks a Backend as local or trusted, THE Generic_AI_Module SHALL allow
   content at any TLP_Level to be sent to that Backend.
6. THE Generic_AI_Module SHALL document the default restriction threshold (`tlp:amber` and
   above) and the default Backend classification (External_Backend unless the operator marks
   it local or trusted).

### Requirement 8: Hallucination Control and Traceability

**User Story:** As a CTI analyst, I want extracted indicators to be real and traceable, so
that I do not act on fabricated data from the model.

#### Acceptance Criteria

1. WHEN an indicator is extracted, THE Generic_AI_Module SHALL validate the indicator value
   against the format rules of its MISP_Attribute type before including it in results.
2. IF an extracted indicator value fails MISP_Attribute type validation, THEN THE
   Generic_AI_Module SHALL exclude that indicator from results and SHALL record in metadata
   an exclusion entry with the excluded value, its declared type, and the failure reason.
3. WHEN an indicator is included in results, THE Generic_AI_Module SHALL confirm the
   indicator value appears as a case-insensitive substring of the normalized source
   CTI_Report text, using the same normalization used to compute the Content_Hash.
4. IF an extracted indicator value is not present as a substring of the normalized source
   CTI_Report text, THEN THE Generic_AI_Module SHALL exclude that indicator from results and
   SHALL record the exclusion in metadata.
5. THE Generic_AI_Module SHALL record, for each included indicator, the matched substring
   plus its start and end character offsets in the normalized source text.
6. THE count of included indicators SHALL be less than or equal to the count of extracted
   indicator candidates, such that validation only removes indicators and never invents them.

### Requirement 9: Deterministic Fallback Integrity

**User Story:** As an operator, I want a dependable fallback that never silently drops data,
so that the pipeline stays observable when a Backend is unavailable.

#### Acceptance Criteria

1. IF no Backend is configured, THEN THE Generic_AI_Module SHALL produce a result using the
   Deterministic_Fallback.
2. IF a Backend call fails, THEN THE Generic_AI_Module SHALL produce a result using the
   Deterministic_Fallback AND SHALL record in the result metadata an error description
   identifying the Backend failure, without discarding the source CTI_Report content.
3. WHEN the Deterministic_Fallback runs, THE Generic_AI_Module SHALL set the result `mode`
   metadata to a documented fallback identifier value that is distinct from the identifier
   used for successful Backend results.
4. IF the input supplied to the Deterministic_Fallback is empty or contains only whitespace
   after normalization, THEN THE Generic_AI_Module SHALL return a descriptive error
   identifying the reason AND SHALL NOT return an empty success result.
5. WHEN the Deterministic_Fallback produces a result for non-empty input, THE
   Generic_AI_Module SHALL include the source CTI_Report content, or a traceable reference to
   it, in the result rather than dropping it.
6. THE Deterministic_Fallback SHALL use only the Python standard library.

### Requirement 10: Synchronous Timeout Behavior

**User Story:** As a MISP administrator, I want the module to respect the synchronous
`/query` timeout, so that enrichment requests do not hang MISP core.

#### Acceptance Criteria

1. THE Generic_AI_Module SHALL apply a bounded request timeout, covering both connection wait
   and response wait, to every Backend call, applying the documented default timeout value
   when a request supplies no `timeout` value.
2. WHEN a request supplies a numeric `timeout` value greater than zero, THE Generic_AI_Module
   SHALL bound total Backend call wait time to at most that value.
3. IF a request supplies a `timeout` value that is missing, non-numeric, or not greater than
   zero, THEN THE Generic_AI_Module SHALL apply the documented default timeout value.
4. IF a Backend call reaches the applicable timeout without returning a complete response,
   THEN THE Generic_AI_Module SHALL abort the Backend call, produce a result using the
   Deterministic_Fallback, and record the timeout as the Backend error in the result
   metadata.
5. THE Generic_AI_Module SHALL operate as a synchronous `/query` responder, and SHALL treat
   asynchronous job execution as out of scope for this feature.

### Requirement 11: Golden-File Testability

**User Story:** As a maintainer, I want deterministic golden-file tests, so that I can
detect output regressions from a fixed input.

#### Acceptance Criteria

1. THE feature SHALL use `tests/fixtures/orkl-sample.txt` as the Canonical_Fixture for
   automated tests.
2. WHEN a golden test runs the Deterministic_Fallback on the Canonical_Fixture, THE feature
   SHALL compare fresh output against the committed Golden_File under `outputs/` by
   Content_Hash equality and byte-for-byte serialized content equality.
3. IF fresh Deterministic_Fallback output differs from the committed Golden_File, THEN the
   golden test SHALL fail and emit output identifying the differing lines or fields.
4. IF the committed Golden_File is absent, THEN the golden test SHALL fail with a descriptive
   error and SHALL NOT auto-create the Golden_File or silently pass.
5. WHEN identical input is processed twice through the Deterministic_Fallback, THE
   Generic_AI_Module SHALL produce identical Content_Hash values and byte-for-byte identical
   result content.
6. THE automated test suite SHALL NOT fetch remote CTI reports, and SHALL rely only on
   committed fixtures.
7. THE feature SHALL provide unit tests for every module source file.
8. THE feature SHALL provide end-to-end tests covering the MISP_Module_Server endpoints
   `/version`, `/modules`, and `/query`.

### Requirement 12: Maintainability and Simplicity

**User Story:** As a human maintainer, I want minimal, well-documented code, so that I can
understand and change the module quickly.

#### Acceptance Criteria

1. THE feature SHALL keep the module source file count equal to exactly one base module file
   plus one file per Specific_Module, with no additional module source files.
2. THE feature SHALL keep every function at or below a Cyclomatic_Complexity of 10, enforced
   by the repository linters (ruff, pylint).
3. IF any function exceeds a Cyclomatic_Complexity of 10, THEN THE repository linters SHALL
   report a violation and THE feature SHALL be treated as failing this requirement.
4. THE Specific_Module implementations SHALL share base logic through inheritance and SHALL
   contain no duplicated base logic.
5. THE feature SHALL document the end-to-end data flow from `/query` input to
   `misp_standard` output.
6. THE feature SHALL provide copy-pasteable usage commands for running the module and
   reproducing a Golden_File result.
7. WHEN behavior changes, THE feature documentation SHALL be updated within the same change.
8. THE feature SHALL pass ruff, semgrep, and pylint with zero new violations relative to the
   pre-change baseline.

### Requirement 13: Structured Extraction Without New Dependencies

**User Story:** As a maintainer bound by the dependency policy, I want structured extraction
built on the standard library, so that no new package is introduced.

#### Acceptance Criteria
1. THE Generic_AI_Module SHALL define extraction schemas using only the standard-library
   constructs `dataclasses` and `typing`, with no third-party import for schema declaration.
2. THE Generic_AI_Module SHALL validate structured output using only the Python standard
   library.
3. THE Generic_AI_Module SHALL serialize structured output using only the Python standard
   library.
4. IF structured-output validation fails, THEN THE Generic_AI_Module SHALL record the failure
   and exclude the invalid data rather than silently dropping it without record.
5. THE Generic_AI_Module SHALL NOT require any third-party runtime dependency beyond the
   Python standard library, as observable from its imports and project configuration.
6. IF a candidate design would require a new third-party dependency, THEN the feature SHALL
   NOT add the dependency and SHALL record the need in documentation for explicit user
   approval.

## Correctness Properties

These properties are candidates for property-based testing. They express invariants that
must hold for arbitrary valid inputs, not only the Canonical_Fixture.

1. **Taxonomy completeness (invariant).** For every AI-produced EventReport, Attribute, and
   Object in a result, both a valid AI_Computer_Assisted_Taxonomy tag and a valid
   EU_AI_Act_Taxonomy tag from the Pinned_Tag_Set are attached.
2. **Attribute-type validity (invariant).** Every entry in `results.Attribute` has a value
   that passes the MISP_Attribute type validation rules for its declared type.
3. **No fabricated indicators (metamorphic).** Every extracted indicator value appears as a
   substring of the normalized source CTI_Report text.
4. **Fallback never drops silently (invariant).** For any input that the Deterministic_Fallback
   cannot process, the result is a descriptive error, never an empty success result.
5. **Deterministic stability (idempotence / round-trip).** Processing identical input twice
   through the Deterministic_Fallback yields identical Content_Hash values and identical
   result content, and matches the committed Golden_File.
6. **Result-shape totality (invariant).** For any accepted input, the result contains all of
   `Attribute`, `Object`, `EventReport`, and `Tag` keys, with lists (possibly empty) rather
   than missing keys.
7. **TLP containment (invariant).** For any request whose `tlp_level` is at or above the
   restriction threshold and whose Backend is external, no source content is transmitted to
   the External_Backend.
8. **Timeout boundedness (metamorphic).** For any configured or requested timeout, total
   Backend wait time does not exceed that timeout before the Deterministic_Fallback engages.
9. **Extraction monotonicity (metamorphic).** The count of validated extracted indicators is
   less than or equal to the count of indicator candidates present in the source text
   (validation only removes, never invents).

## Open Questions

These items need a decision before or during design. Sensible defaults are proposed so
design can proceed if answers are deferred.

1. **TLP restriction threshold and Backend trust default.** Proposed default: treat
   `tlp:amber`, `tlp:amber+strict`, and `tlp:red` as restricted, and treat the configured
   Backend as external unless the administrator marks it local. Confirm the threshold and
   default trust classification (Requirement 7).
2. **Assistance-level mapping per use-case.** Proposed default: summarization and info
   extraction emit AI-generated; NER / tag proposal and ML checker emit AI-assisted since an
   analyst confirms them. Confirm this mapping (Requirement 6.3).
3. **Galaxy mapping depth.** Proposed default: map to MITRE ATT&CK technique clusters and
   threat-actor clusters by name/ID match only, without inventing new clusters. Confirm
   scope (Requirement 4.3).
4. **Cyclomatic-complexity threshold.** Resolved: the per-function ceiling is pinned to 10,
   enforced by pylint/ruff, as stated in Requirement 12 (default 10).
5. **Hover output content.** Proposed default: hover returns the summary text only, without
   the structured extraction block. Confirm (Requirement 3.4).
