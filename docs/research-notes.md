# DPRK Panel of Experts Reports — Research Notes

## Summary of Findings

The UN Security Council Panel of Experts established pursuant to Resolution 1874 (2009) produced **22 publicly known reports** between 2010 and 2024:
- **15 final (annual) reports** (2010–2024)
- **6 publicly released midterm reports** (2017, 2019–2023)
- **1 leaked/unofficial final report** (2011)
- **1 suppressed midterm report** (2018)

---

## Reports NOT Publicly Released

### 2011 Final Report
The Panel completed its 2011 final report (dated May 2011), but China's expert on the Panel refused to sign it. As a result, the Sanctions Committee was deadlocked and the report was **never officially released** as a UN document. It was never assigned an S/ document symbol. A leaked version circulated and is available at NCNK: https://www.ncnk.org/sites/default/files/content/resources/publications/UN-Panel-of-Experts-Report-May-2011.pdf

**Source:** SecurityCouncilReport DPRK November 2011 Monthly Forecast; NCNK page for the report

### Pre-2017 Midterm Reports (2010, 2011, 2012, 2013, 2014, 2015, 2016)
Midterm reports were required from the beginning (e.g., Resolution 1928 (2010) mandated one by 10 November 2010). However, these early midterm reports were submitted internally to the Committee and then to the Security Council as Committee documents, but were NOT publicly issued as Security Council documents with their own S/ document symbols.

Evidence:
- S/2012/982 (1718 Committee annual report) describes the 2012 midterm being transmitted to Committee on 7 Nov 2012 and to Council on 11 Dec 2012 — but gives NO document symbol for the midterm itself.
- S/2016/157 (2016 final report) and S/2017/150 (2017 final report) cite NO earlier midterm report symbols in their footnotes.
- Resolution 2321 (November 2016) explicitly requested midterm reports to include findings/recommendations "beginning with" the next midterm — signaling a change in practice toward public reporting.

### 2018 Midterm Report
The 2018 midterm was completed and submitted to the Committee, but the US blocked its publication. According to [SecurityCouncilReport November 2018 forecast](https://www.securitycouncilreport.org/monthly-forecast/2018-11/dprk_north_korea_30.php): "The tensions were further exacerbated over the midterm report of the Panel of Experts, publication of which was blocked by the US citing Russian..." The report was never assigned a public document symbol.

---

## Publicly Released Midterm Reports (Starting 2017)

Resolution 2321 (November 2016), paragraph 43, requested the Panel to include findings and recommendations in its midterm reports "beginning with the midterm report due to be submitted to the Committee." This was the turning point that made midterm reports publicly released documents.

The first publicly released midterm with a document symbol was **S/2017/742** (5 September 2017).

---

## Document URL Patterns

### Primary Source (UN Official Document System)
Direct PDF URL format obtained via API:
```
https://documents.un.org/api/symbol/access?s=S/YEAR/NUM&l=en&t=pdf
```
This redirects to a URL like:
```
https://documents.un.org/doc/UNDOC/GEN/NXX/XXX/XX/PDF/NXXXXXXX.PDF
```
These URLs return HTTP 301 without `-L` flag, HTTP 200 when following redirects.

### NCNK Mirrors (National Committee on North Korea)
NCNK hosts many reports at consistent URLs. These return HTTP 200 directly.
- Main page: https://www.ncnk.org/resources/publications/un-panel-experts

### SecurityCouncilReport Mirrors
Available for some earlier reports at:
```
https://www.securitycouncilreport.org/atf/cf/%7B65BFCF9B-6D27-4E9C-8CD3-CF6E4FF96FF9%7D/[filename].pdf
```

---

## Symbol Verification Notes

Several symbols previously believed to be DPRK PoE midterm reports were found to be other documents entirely:
- **S/2014/727** → Somalia/Eritrea Monitoring Group report on Eritrea
- **S/2015/736** → Israel/Palestine letter
- **S/2016/784** → General Assembly President letter re: Secretary-General selection
- **S/2018/850** → Syrian letter re: humanitarian reports
- **S/2012/947** → US letter updating ballistic missile items list (S/2012/235 update)

The correct symbols for DPRK PoE midterm reports were confirmed by:
1. Downloading and reading actual PDFs
2. Cross-referencing with SecurityCouncilReport sanctions documents page
3. Checking footnote citations in confirmed PoE reports

---

## Source Quality

| Source | Use |
|--------|-----|
| documents.un.org API | Definitive for document symbols and PDF URLs |
| SecurityCouncilReport | Best list of publicly released PoE reports |
| NCNK (ncnk.org) | Reliable mirror hosting; useful for 2011 leaked report |
| SecurityCouncilReport Monthly Forecasts | Key historical context for non-released reports |
