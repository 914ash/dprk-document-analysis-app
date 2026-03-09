# Data Policy

## Included in the public repo
- Source manifests and public report metadata
- Processed dashboard JSON
- Fixture and test datasets needed for package verification
- Public source URLs for provenance

## Excluded from the public repo
- Downloaded raw PDFs
- Local caches and interim parquet extracts
- Review parquet files with analyst-specific history
- Machine-local absolute paths and private session artifacts

## Reviewer identifiers
Reviewer fields must use pseudonymous identifiers such as `analyst-001` or `pipeline`, not emails.
