# GDPR Scanner

## What This Is

Et Windows system tray-program skrevet i Python, der løbende scanner valgte mapper for filer der potentielt bryder GDPR — baseret på filtype, filnavnsmønstre og indholdsscanning. Filer ældre end en konfigurerbar grænse (standard 30 dage) der indeholder persondata flagges til brugeren, som herefter kan slette, beholde eller ignorere dem permanent.

## Core Value

Brugeren skal automatisk blive gjort opmærksom på GDPR-risikable filer — uden at skulle gøre noget aktivt.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] System tray-ikon med baggrundskørsel (Windows)
- [ ] Konfigurationsdialog der kan åbnes fra tray-menu
- [ ] Mappevalg — brugeren vælger hvilke mapper der skannes
- [ ] Konfigurabel filaldergrænse (standard 30 dage)
- [ ] Konfigurabel scanningsfrekvens
- [ ] Konfigurabel liste af filtyper der indgår i skanningen
- [ ] Filtyp + filnavn-detektion (mønstermatch på fx "CPR", "kunde", "patient", "personnummer", "kaldenavn")
- [ ] Indholdsscanning af .docx/.doc, .xlsx/.xls/.csv, .pdf, .txt/.log
- [ ] Detektering af: CPR-numre, email-adresser, danske telefonnumre, kolonneoverskrifter som indikerer persondata (Navn, Adresse, Fødselsdato, Kaldenavn o.l.)
- [ ] Streng detektion — kun sikre mønstre + stærke header-indikatorer (lav falsk-positiv rate)
- [ ] Alarmdialog ved fund: mulighed for Slet / Behold / Ignorer permanent
- [ ] Ignorer-liste persisteres (filer på listen springes over ved fremtidige skanninger)
- [ ] Indstillinger persisteres mellem sessioner

### Out of Scope

- Multi-bruger / netværksinstallation — kun til eget brug på én PC
- Central IT-administration eller deployment — ikke relevant for use case
- NLP/AI-baseret navnegenkendelse — for komplekst og fejlbehæftet; bruger header-heuristik i stedet
- macOS / Linux support — kun Windows
- Netværksdrev-scanning — for langsomt og uden for scope i første version
- Rapportering / logning til ekstern server — ikke relevant for personligt brug

## Context

- Python er valgt som programmeringssprog
- Windows-only — kan bruge win32api / pystray til system tray
- Personligt brug — én maskine, ingen installer krævet nødvendigvis
- GDPR-detektion kombinerer to lag: (1) filtype/navn-filter og (2) indholdsscanning
- Streng tilstand valgt for at minimere falske positiver — CPR-mønstre er deterministiske, øvrige baseres på kolonneoverskrifter/felt-labels frem for fritekstgenkendelse
- "Kaldenavne" medtages som søgeord i filnavn-detektion og som header-indikator i indholdsscanning

## Constraints

- **Tech stack**: Python — brugerens valg, holdes rent Python uden tunge frameworks
- **Platform**: Windows only — system tray via `pystray`, GUI via `tkinter` (standard bibliotek)
- **Scope**: Enkeltbruger, lokal installation — ingen database, ingen server, JSON/INI til config
- **Detektion**: Kun deterministiske mønstre + header-heuristik — ingen ML/NLP

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Streng detektion frem for aggressiv | Minimerer falske positiver — brugeren undgår alarmtræthed | — Pending |
| tkinter til GUI | Standard bibliotek, ingen ekstra afhængigheder, tilstrækkeligt til simpel config-dialog | — Pending |
| pystray til system tray | Mest brugte og vedligeholdte Python tray-bibliotek til Windows | — Pending |
| JSON til persistens (config + ignorer-liste) | Simpelt, menneskeligt læsbart, ingen DB overhead | — Pending |
| Header-heuristik frem for NLP til navne | Praktisk tradeoff: deterministisk, forklarlig, hurtig | — Pending |

---
*Last updated: 2026-04-01 after initialization*

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state
