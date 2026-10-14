# Evidence and model policy

## Three different objects

- **Research dictionary:** 45 candidate model input names (`assets/parameter_dictionary.json`) with stable IDs, semantic grouping, type and units. These are a starting checklist, not a verified model-version-specific dependency graph.
- **Paper extraction:** independent paper-author-reported values and evidence, potentially multiple candidate values with different roles and study conditions. Do not populate from PyBaMM source code.
- **Model adaptation:** reviewed values converted to PyBaMM keys. A simulation may require additional keys/function definitions beyond the checklist depending on PyBaMM version, chosen options and geometry.

## Roles and statuses

Source types `PAPER`, `CITED`, `DERIVED`, `EXTERNAL`, `UNKNOWN` are separate from value role `experimental`, `adjusted`, `simulation`, `assumed`, `fitted`, `unspecified`. Review statuses `MISSING`, `PENDING`, `CONFLICT`, `DERIVED`, `VERIFIED`. Do not conflate `PENDING` with `VERIFIED`.

## Citation record

`{document_id, quote, page, table, figure, section, bbox_norm, location_status}`; page numbering is physical PDF-page indexing starting at 1, not necessarily printed page labels. `bbox_norm` = `[x0,y0,x1,y1]` top-left normalized. Keep DOI and SHA256 document metadata.

## False comparison traps

1. O'Kane 2022 references Chen 2020 and other studies; source-chain extraction required.
2. `Chen2020` may reflect adjusted/fitted rather than experimentally measured values; compare same role and same conditions.
3. Code functions such as OCP or diffusivity need expression/data-array comparison, not just numbers.
4. Units and versions must match; compare `um` with `m` only after explicit conversion.
5. Matching names without matching cell chemistry, electrode or temperature are not matches.
