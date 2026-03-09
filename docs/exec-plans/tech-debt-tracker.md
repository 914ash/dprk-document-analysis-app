# Tech Debt Tracker

| Date | Area | Debt | Impact | Exit Criteria |
|------|------|------|--------|---------------|
| 2026-03-09 | Dashboard data export | Guidance payloads are still hand-authored in static JSON rather than exported from a canonical pipeline step. | Dashboard docs can drift from pipeline logic. | Add a dedicated export step that emits dashboard guidance/data from package outputs. |
| 2026-03-09 | Extractor fallback | Hugging Face fallback adapter exists by contract but is not yet covered by model-backed integration tests in this workspace. | Runtime fallback quality is unproven. | Add fixture-backed fallback integration test and package install docs. |
| 2026-03-09 | Attribution language risk | Upstream RAND legal/attribution language may demand stricter credit wording or license phrasing. | Public release could fail a policy review if wording is off. | Verify exact upstream requirements before public announcement, then align credits and README wording. |
