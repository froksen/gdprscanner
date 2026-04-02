# Requirements: GDPR Scanner

**Defined:** 2026-04-01
**Core Value:** Brugeren skal automatisk blive gjort opmærksom på GDPR-risikable filer — uden at skulle gøre noget aktivt.

## v1 Requirements

### System Tray & Livscyklus

- [x] **TRAY-01**: Programmet starter i Windows system tray (ikke et synligt vindue)
- [x] **TRAY-02**: Tray-ikon har en kontekstmenu med: "Åbn indstillinger", "Scan nu", "Afslut"
- [x] **TRAY-03**: Programmet kører stabilt i baggrunden uden at blokere UI eller bruge unødvendige ressourcer
- [x] **TRAY-04**: pystray ejer main thread; tkinter kører på worker thread (Win32-krav)

### Konfigurationsdialog

- [ ] **CONF-01**: Brugeren kan åbne en konfigurationsdialog fra tray-menuen
- [ ] **CONF-02**: Brugeren kan tilføje og fjerne mapper der skal skannes
- [ ] **CONF-03**: Brugeren kan sætte filaldergrænsen i dage (standard: 30)
- [ ] **CONF-04**: Brugeren kan sætte scanningsfrekvens (f.eks. dagligt, hvert 6. time, ugentligt)
- [ ] **CONF-05**: Brugeren kan vælge hvilke filtyper der indgår (.docx, .xlsx, .csv, .pdf, .txt, .log)
- [x] **CONF-06**: Konfiguration persisteres i `%APPDATA%\GDPRScanner\config.json`

### Fil-filter (lag 1: filtype + filnavn)

- [ ] **FILT-01**: Kun filer ældre end den konfigurerede grænse skannes
- [ ] **FILT-02**: Kun konfigurerede filtyper skannes
- [ ] **FILT-03**: Filer der matcher konfigurerede filnavn-søgeord flagges (f.eks. "cpr", "kunde", "patient", "personnummer", "kaldenavn", "adresse", "fortrolig")
- [ ] **FILT-04**: Filer på ignorer-listen springes over

### Indholdsscanning (lag 2)

- [ ] **SCAN-01**: .docx-filer skannes med python-docx (kun .docx, ikke legacy .doc)
- [ ] **SCAN-02**: .xlsx/.xls/.csv-filer skannes med openpyxl / csv-modul; encoding-fallback: utf-8-sig → cp1252 → latin-1
- [ ] **SCAN-03**: .pdf-filer skannes med pdfplumber; filer > 20 MB springes over; max 50 sider per fil
- [ ] **SCAN-04**: .txt/.log-filer skannes med encoding-fallback
- [ ] **SCAN-05**: Hvert fil-scan er isoleret i try/except — én fejlet fil stopper ikke hele scan-kørslen
- [ ] **SCAN-06**: CPR-numre detekteres: mønster DDMMYY[-]XXXX; dato-komponent valideres (dag 01-31, måned 01-12); modulus-11 bruges KUN som tillægsindikator (ikke som filter, da post-2007 CPR ikke opfylder det)
- [ ] **SCAN-07**: Email-adresser detekteres med standard RFC-subset regex
- [ ] **SCAN-08**: Danske telefonnumre detekteres: 8 sammenhængende cifre ELLER XX XX XX XX format; kræver kontekst (ikke rå cifre)
- [ ] **SCAN-09**: Kolonneoverskrifter/feltetiketter der indikerer persondata detekteres (Navn, Adresse, Fødselsdato, Kaldenavn, CPR, Personnummer, Email, Telefon og varianter)

### Alarm & Handlingsdialog

- [ ] **ALRT-01**: Når en fil med potentielt GDPR-brud opdages, vises en dialog til brugeren
- [ ] **ALRT-02**: Dialogen viser: filnavn, sti, alder, hvilken type fund der udløste alarmen
- [ ] **ALRT-03**: Brugeren kan vælge "Slet fil" — filen slettes permanent efter bekræftelse
- [ ] **ALRT-04**: Brugeren kan vælge "Behold" — filen ignoreres i denne kørsel, flagges igen næste scan
- [ ] **ALRT-05**: Brugeren kan vælge "Ignorer permanent" — filens sti tilføjes til ignorer-listen og vises ikke igen
- [ ] **ALRT-06**: Dialogs vises én ad gangen (ikke batch)

### Ignorer-liste

- [ ] **IGNR-01**: Ignorer-listen persisteres i `%APPDATA%\GDPRScanner\ignorelist.json`
- [ ] **IGNR-02**: Opslag i ignorer-listen er O(1) (set i hukommelsen)
- [ ] **IGNR-03**: Brugeren kan se og redigere ignorer-listen fra konfigurationsdialogen

### Scanning & Planlægning

- [x] **SCHED-01**: Automatisk scanning sker med den konfigurerede frekvens
- [x] **SCHED-02**: Brugeren kan manuelt starte en scanning fra tray-menuen
- [x] **SCHED-03**: Scanning kører i en baggrundstråd og blokerer ikke UI

## v2 Requirements

### Udvidet detektion

- **DET-01**: Indholds-hash-baseret ignorer (ignorer specifikt indhold, ikke kun filsti)
- **DET-02**: .doc legacy format support (kræver win32com / Word installeret)
- **DET-03**: .msg Outlook-fil support
- **DET-04**: OCR-scanning af billede-PDF'er

### Rapportering

- **RPT-01**: Scan-historik / log der viser hvad der er fundet og hvad brugeren valgte
- **RPT-02**: Eksport af fund til rapport

## Out of Scope

| Feature | Reason |
|---------|--------|
| Multi-bruger / netværksinstallation | Kun til personlig brug — én PC |
| Central IT-deployment | Ikke relevant for use case |
| NLP/AI navnegenkendelse | For komplekst og fejlbehæftet; header-heuristik er tilstrækkelig |
| macOS / Linux | Kun Windows |
| Netværksdrev | For langsomt, uden for scope v1 |
| Auto-slet uden bekræftelse | Kræver altid menneskelig godkendelse — GDPR-princip |
| Real-time filsystem-overvågning (watchdog) | Planlagt scanning er tilstrækkeligt for v1 |
| .doc legacy format (v1) | Kræver Word installeret; ikke selvstændigt bundle-kompatibelt |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| TRAY-01 | Phase 1 | Complete |
| TRAY-02 | Phase 1 | Complete |
| TRAY-03 | Phase 1 | Complete |
| TRAY-04 | Phase 1 | Complete |
| CONF-01 | Phase 1 | Pending |
| CONF-02 | Phase 1 | Pending |
| CONF-03 | Phase 1 | Pending |
| CONF-04 | Phase 1 | Pending |
| CONF-05 | Phase 1 | Pending |
| CONF-06 | Phase 1 | Complete (01-01) |
| FILT-01 | Phase 2 | Pending |
| FILT-02 | Phase 2 | Pending |
| FILT-03 | Phase 2 | Pending |
| FILT-04 | Phase 2 | Pending |
| SCAN-01 | Phase 2 | Pending |
| SCAN-02 | Phase 2 | Pending |
| SCAN-03 | Phase 2 | Pending |
| SCAN-04 | Phase 2 | Pending |
| SCAN-05 | Phase 2 | Pending |
| SCAN-06 | Phase 2 | Pending |
| SCAN-07 | Phase 2 | Pending |
| SCAN-08 | Phase 2 | Pending |
| SCAN-09 | Phase 2 | Pending |
| ALRT-01 | Phase 3 | Pending |
| ALRT-02 | Phase 3 | Pending |
| ALRT-03 | Phase 3 | Pending |
| ALRT-04 | Phase 3 | Pending |
| ALRT-05 | Phase 3 | Pending |
| ALRT-06 | Phase 3 | Pending |
| IGNR-01 | Phase 3 | Pending |
| IGNR-02 | Phase 3 | Pending |
| IGNR-03 | Phase 3 | Pending |
| SCHED-01 | Phase 1 | Complete |
| SCHED-02 | Phase 1 | Complete |
| SCHED-03 | Phase 1 | Complete |

**Coverage:**
- v1 requirements: 33 total
- Mapped to phases: 33
- Unmapped: 0 ✓

---
*Requirements defined: 2026-04-01*
*Last updated: 2026-04-01 after initial definition*
