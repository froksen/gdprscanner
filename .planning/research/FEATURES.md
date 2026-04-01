# Feature Landscape: GDPR File Scanner

**Domain:** Personal-use Windows GDPR compliance / data discovery tool
**Researched:** 2026-04-01
**Confidence note:** WebSearch unavailable. Findings based on training knowledge of GDPR tooling (Microsoft Purview, Spirion, Ground Labs, Varonis, open-source PII scanners), Danish data protection practice, and Windows tray application patterns. Core GDPR data patterns are stable and well-documented — confidence is HIGH for detection patterns, MEDIUM for UI convention details.

---

## Table Stakes

Features users expect from a GDPR file scanner. Missing any of these makes the tool feel broken or untrustworthy.

### Detection: Data Patterns

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| CPR-number detection (Danish) | The primary Danish GDPR identifier. Pattern is deterministic: `DDMMYY-XXXX` and `DDMMYYXXXX`. Modulus-11 checksum available but not universally applied on post-2007 CPR numbers. | Low | Regex + optional checksum validation. Post-2007 CPR numbers dropped the modulus-11 rule — do NOT rely on checksum alone as a filter |
| Email address detection | Near-universal personal data under GDPR. RFC-5322-compatible regex is table stakes. | Low | Standard `[\w.+-]+@[\w-]+\.[\w.]+` pattern is sufficient; full RFC-5322 is overkill |
| Danish phone number detection | `+45` prefix or 8-digit local numbers. Common format variations: `XX XX XX XX`, `XXXXXXXX`, `+45 XXXXXXXX`. | Low | Must handle spaces and formatting variation. Avoid matching 8-digit sequences that are product codes — context helps but strict grouping (space-separated pairs) reduces false positives |
| Filename/directory pattern matching | Tools always offer "flag by name" as a fast pre-filter before expensive content scanning. Keywords: CPR, kunde, patient, personnummer, CPR-nr, fortrolig, personfølsom, GDPR, fødselsdato | Low | Case-insensitive, substring match. This is the first-pass gate that avoids content-scanning irrelevant files |
| Column header / field label heuristics | For tabular data (CSV, XLSX), column names are reliable PII indicators without NLP. Expected headers: Navn, Fornavn, Efternavn, Adresse, Fødselsdato, CPR, Telefon, Email, Kaldenavn, Køn | Low–Med | Must handle both Danish and English variants (Name, Address, DateOfBirth). Row 1 or row 2 inspection only — no need to scan full file |

### Detection: File Types

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Plain text (.txt, .log, .csv) | Simplest case. Direct regex over file content. | Low | Encoding detection matters — UTF-8, Latin-1, CP1252 common on Windows |
| Word documents (.docx) | Extremely common for "personal data in documents" scenarios. DOCX is a ZIP — extract `word/document.xml`, scan text nodes. | Low–Med | `python-docx` handles this cleanly. Legacy `.doc` (OLE) requires `python-docx2txt` or `antiword` — much harder |
| Excel spreadsheets (.xlsx, .xls, .csv) | Spreadsheets are the most common GDPR landmine — customer lists, patient records. | Med | `openpyxl` for .xlsx. Legacy `.xls` requires `xlrd` (version-locked). CSV is trivial |
| PDF (.pdf) | Common for archived reports, invoices, contracts with personal data. | Med | `pdfplumber` or `pypdf` for text extraction. Scanned PDFs (image-only) cannot be read without OCR — this is a known limitation to document |
| Email files (.eml, .msg) | Common for "I saved an email with someone's personal data." | High | `.eml` is parseable with `email` stdlib. `.msg` (Outlook) requires `extract-msg` library. Can skip in v1 |

### Detection: False Positive Handling

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Strict/conservative pattern matching | Users stop trusting tools that flag benign content. A single "noise" alert trains users to dismiss everything. | Low | CPR regex must anchor to non-digit boundaries. Phone regex must require grouping or `+45` prefix. This is a design discipline, not a library feature |
| Permanent ignore list | Once a user says "this file is fine," they must never see it again. This is universally expected in any compliance tool. | Low | JSON file mapping absolute path → timestamp of ignore decision |
| Ignore-by-hash (content hash) | Handles files that are moved/renamed — the same content in a new location should not re-alert. | Med | SHA-256 of file content stored alongside path. Adds ~10ms per file scan |
| Context window around match | Showing 1-2 lines of surrounding text in the alert helps the user judge false positives. | Low–Med | Truncate to ~100 chars, anonymize if displaying to screen |

### UI: System Tray

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Tray icon with status indication | Users expect visual feedback that the tool is running. Minimum: icon present. Better: icon changes color/style when violations found. | Low | `pystray` supports icon image swap |
| Right-click context menu | Open settings, run scan now, exit. Standard tray pattern on Windows. | Low | `pystray` menu API |
| Non-blocking alert on violation | Toast notification or modal dialog that does not steal focus during active work. | Med | Windows toast via `win10toast` or `plyer`. Modal via `tkinter` works but steals focus |
| Action dialog: Delete / Keep / Ignore | The core user decision point. Must be clear, non-scary, reversible (Ignore is reversible; Delete is not). | Low–Med | `tkinter` dialog. Delete must prompt for confirmation. "Keep" means "dismiss this time, ask again next scan." |
| Startup with Windows | Users expect background tools to auto-start. | Low | Registry key `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` or Startup folder shortcut |

### Configuration

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Folder selection (which folders to scan) | Without this, the tool is useless — it must not scan the entire C: drive by default. | Low | `tkinter.filedialog.askdirectory`. Multiple folder support needed. |
| File age threshold | Core project requirement — files older than N days. Standard in compliance tools that focus on data retention. | Low | Compare `os.path.getmtime()` against threshold. Configurable default 30 days. |
| Scan frequency | Background polling. Options: on-demand only, hourly, daily, on-startup. | Low | Python `threading` + `time.sleep` loop or `schedule` library |
| Configurable file type list | Power users want to add `.json`, `.xml` etc. or exclude `.log`. | Low | Checkbox list in config dialog |
| Persist settings between sessions | JSON config file in user's AppData or alongside the script. | Low | `json.dump/load` to `%APPDATA%\GDPRScanner\config.json` |

---

## Differentiators

Features that set a tool apart — not expected by default, but valued when present.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Ignore by content hash (not just path) | Surviving file moves/renames without re-alerting. Especially useful for Downloads folders. | Med | SHA-256 hash index alongside path ignore list |
| Scan summary / history log | "Last scan: 14 files checked, 2 flagged, 1 ignored." Gives user confidence the tool is working. | Low | Append-only JSON log. Show in tray tooltip or settings dialog |
| Preview pane in alert dialog | Show the matched text with context before asking user to decide. Reduces friction, increases trust. | Med | Extract surrounding ~80 chars from match position. Mask partial data (e.g., `CPR: 010101-****`) |
| Column header match reporting | Tell the user WHICH header triggered the flag ("Column 'CPR-nr' found in row 1"). More actionable than "PII found." | Low | Available naturally if header-heuristic is already implemented |
| File size / scan-time guard | Skip files over N MB (e.g., 50MB) to avoid hanging on large log files or database dumps. Configurable. | Low | `os.path.getsize()` check before opening file |
| Configurable keyword list for filenames | Let users add their own organisation-specific terms (e.g., "klient", "member", "bruger"). | Low | Editable list in config dialog |
| Scan progress indicator | For large folder sets, show which file is being scanned. Prevents "is it frozen?" confusion. | Med | Requires threading model where UI thread can receive progress events |
| Export findings to CSV | For the rare user who wants to audit a large folder set and review offline. | Low | Write match records to CSV with path, pattern, date |

---

## Anti-Features

Things to deliberately NOT build for v1. Each has a reason.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| NLP / ML name recognition | High false positive rate for common Danish words. Requires large model or API call. Fundamentally at odds with the project's "strict detection" principle. Well outside scope for a personal tool. | Header heuristics for column names; filename keyword matching for document names |
| Full-text name matching (regex for "Fornavn Efternavn" patterns) | Danish names are not distinguishable from normal prose. Would flood user with false positives on any document with people's names mentioned. | Rely on context: column headers, file names, CPR co-occurrence |
| Network share / UNC path scanning | Adds latency unpredictability (10ms–10min per file). Timeout handling is complex. Out of scope per PROJECT.md. | Document as a known limitation |
| OCR on scanned PDFs | Heavy dependency (Tesseract), slow, error-prone, requires separate install. | Document: "Scanned/image PDFs are not supported" in UI |
| Central reporting / dashboard | Overkill for personal single-machine use. Adds server complexity, data exfiltration risk. | Local scan log in settings dialog is sufficient |
| Multi-user / team deployment | Completely different architecture (server, admin console, agent). Out of scope per PROJECT.md. | — |
| Auto-quarantine / auto-delete | Irreversible automated actions on user data are dangerous and erode trust. GDPR compliance requires human judgment. | Always present a decision dialog |
| Email scanning via IMAP | Connecting to mail servers is a different product category. Complex auth, different data model. | Limit to saved .eml/.msg files if desired in v2 |
| ZIP / archive scanning | Recursive extraction is complex, slow, and can be exploited (zip bombs). | Document as out of scope. Consider in v2 with depth limit |
| Legacy .doc / .xls format support | OLE compound document format requires heavy libraries (`python-pptx` doesn't help, need `antiword` or COM automation). Minimal gain vs complexity cost. | Alert user that legacy Office formats are not scanned; suggest resaving as .docx/.xlsx |

---

## Feature Dependencies

```
Folder selection
    → File age threshold (both needed before any scan runs)
    → File type filter (determines what content scanning applies to)
        → Content scanning (docx, xlsx, csv, pdf, txt)
            → PII pattern matching (CPR, email, phone, headers)
                → Alert dialog (Delete / Keep / Ignore)
                    → Ignore list persistence
                        → Ignore-by-hash (extends ignore list)

Filename/directory keyword matching
    → runs in parallel with content scanning (faster pre-filter)

Scan frequency config
    → Background thread model (must not block UI thread)
        → Scan progress indicator (optional, requires same thread model)

Tray icon
    → Context menu (Open settings, Scan now, Exit)
    → Status indication (changes when violations found)

Settings persistence (JSON)
    → All config values (folders, age threshold, frequency, file types, keywords)
    → Ignore list (separate file or same file)
```

**Critical ordering constraint:** Config persistence must work before any scan feature is built. Without persistent folder selection, every session requires reconfiguration — this breaks the "no active effort required" core value.

---

## MVP Recommendation

Prioritize these in order:

1. Config persistence + folder selection + file age threshold (the scaffolding everything else runs on)
2. Filename/directory keyword matching (fast, high-value, no file parsing needed)
3. Content scanning: CSV + TXT first (trivial parsing), then DOCX, then XLSX, then PDF
4. CPR + email detection patterns (highest-value, most deterministic)
5. Phone number detection (easy, medium value)
6. Column header heuristics for CSV/XLSX (medium complexity, high value for spreadsheets)
7. Alert dialog with Delete / Keep / Ignore + ignore list persistence
8. System tray with context menu + Windows startup registration
9. Scan frequency / background polling

Defer to v2:
- Ignore by content hash (path-based ignore covers 80% of cases)
- Scan progress indicator (acceptable to show spinning icon for v1)
- PDF scanning (significantly more complex than text/Office formats; add after core is stable)
- Export to CSV
- Legacy .doc/.xls support

---

## Danish-Specific GDPR Pattern Reference

These are the patterns that matter most for the Danish context:

### CPR Number (Central Person Register)
- Format: `DDMMYY-XXXX` or `DDMMYYXXXX` (10 digits, optionally hyphen-separated after 6th digit)
- Regex: `\b(\d{2})(\d{2})(\d{2})-?(\d{4})\b`
- Validation: Day 01-31, Month 01-12, last 4 digits encode gender (odd = male) and century
- Post-2007: Modulus-11 checksum is no longer universally valid — do not filter out valid CPRs based on failed modulus-11
- False positive risk: 8-digit phone numbers can overlap — require the hyphen or verify date-validity of first 6 digits to disambiguate

### Email Address
- Pattern: standard RFC-5321-ish — `[\w.!#$%&'*+/=?^_{|}~-]+@[\w-]+(?:\.[\w-]+)+`
- Low false positive risk

### Danish Phone Number
- Format: 8 digits, often written as `XX XX XX XX` or `XXXXXXXX`
- With country code: `+45 XXXXXXXX` or `0045XXXXXXXX`
- Regex for local: `\b(\d{2}[\s.-]){3}\d{2}\b` (space/dot/dash separated pairs) OR `\b\d{8}\b` (bare 8-digit — higher FP risk)
- Recommended: require `+45` prefix OR space-separated pair format to reduce false positives from product codes, order numbers

### Column Headers (Danish + English)
High-confidence: `CPR`, `CPR-nr`, `CPR-nummer`, `Personnummer`, `Fødselsdato`, `Kaldenavn`
Medium-confidence: `Navn`, `Fornavn`, `Efternavn`, `Adresse`, `Postnr`, `Email`, `Telefon`, `Mobil`
English variants: `Name`, `FirstName`, `LastName`, `Address`, `DateOfBirth`, `Phone`, `Mobile`, `Email`

### Filename Keywords (Danish context)
High-confidence: `CPR`, `personnummer`, `patient`, `klient`, `fortrolig`, `personfølsom`, `GDPR`
Medium-confidence: `kunde`, `kontakt`, `member`, `bruger`, `kaldenavn`, `medarbejder`

---

## Sources

- Training knowledge: Microsoft Purview Information Protection documentation (pattern library for PII types)
- Training knowledge: GDPR Article 4 definition of personal data; Danish DPA (Datatilsynet) guidance on CPR numbers
- Training knowledge: CPR system documentation — post-2007 modulus-11 rule change (well-documented in Danish developer communities)
- Training knowledge: `pystray`, `python-docx`, `openpyxl`, `pdfplumber` library capabilities
- Training knowledge: Spirion (formerly Identity Finder), Varonis, Ground Labs Enterprise Recon feature sets
- Confidence: HIGH for detection patterns (stable, deterministic). MEDIUM for UI/UX conventions (based on pattern knowledge, not current doc verification).
