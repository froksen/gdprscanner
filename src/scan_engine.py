import os
import re
import time
import csv
import logging
import pathlib
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import List, Dict, Optional

import PyPDF2
import xlrd

from src.config_store import ConfigStore

CPR_FILENAME_KEYS = [
    "cpr",
    "kunde",
    "patient",
    "personnummer",
    "kaldenavn",
    "adresse",
    "fortrolig",
    "journal",
    "sygejournal",
    "lægeerklæring",
    "straffeattest",
    "fagforening",
    "lønliste",
    "lønseddel",
    "ansatte",
    "medarbejder",
    "ansøgning",
    "kreditkort",
    "bankkonto",
]

HEADER_KEYS = [
    # Identifikation
    "cpr", "personnummer", "person_id", "personid", "national_id", "ssn",
    # Navn og kontakt
    "navn", "name", "fornavn", "efternavn", "firstname", "lastname", "surname",
    "adresse", "address", "gade", "street", "postnr", "postnummer", "zip", "postcode",
    "telefon", "phone", "mobil", "mobile", "tlf",
    "email", "e-mail", "mail",
    # Datoer
    "fødselsdato", "fodselsdato", "birthdate", "birthday", "birth_date", "fødselsdår",
    # Økonomi
    "løn", "salary", "indkomst", "income", "lønoplysning",
    "kontonr", "kontonummer", "account_number", "iban", "bankkonto",
    "kreditkort", "credit_card",
    # Helbred
    "diagnose", "diagnosis", "sygdom", "disease", "helbredsstatus", "health",
    "medicinering", "medication", "behandling", "treatment",
    # Særlige kategorier
    "religion", "trosretning", "faith",
    "etnicitet", "ethnicity", "nationalitet", "nationality",
    "fagforening", "union",
    "politisk", "political",
    "seksuel", "sexual",
    "genetisk", "genetic",
]

# Indhold-nøgleord for særlige kategorier (GDPR art. 9)
SENSITIVE_CATEGORY_KEYWORDS = {
    "Helbredsoplysninger": [
        "diagnose", "sygejournal", "patientjournal", "medicinering",
        "lægeerklæring", "helbredsoplysning", "sygdomshistorie",
        "psykiatrisk", "psykologjournal",
    ],
    "Racemæssig/etnisk oprindelse": [
        "racemæssig oprindelse", "etnisk oprindelse", "racetilhørsforhold",
        "etnisk baggrund",
    ],
    "Politisk overbevisning": [
        "politisk overbevisning", "politisk tilhørsforhold", "partibog",
        "politisk parti", "partitilhørsforhold",
    ],
    "Religiøs overbevisning": [
        "religiøs overbevisning", "trosbekendelse", "religiøst tilhørsforhold",
    ],
    "Fagforeningsmedlemskab": [
        "fagforeningsmedlemskab", "fagforbund", "fagforeningsoplysning",
    ],
    "Genetiske oplysninger": [
        "genetisk profil", "dna-profil", "genetiske oplysninger",
        "dna-analyse", "genetisk test",
    ],
    "Biometriske oplysninger": [
        "fingeraftryk", "ansigtsgenkendelse", "iris-scanning",
        "biometrisk identifikation", "stemmegenkendelse",
    ],
    "Seksuel orientering": [
        "seksuel orientering", "seksuel præference",
    ],
    "Strafbare forhold": [
        "straffeattest", "strafferegister", "kriminalregister",
        "straffedom", "straffesag",
    ],
}

# ---------------------------------------------------------------------------
# Detection type registry — canonical list used by both scan engine and UI
# ---------------------------------------------------------------------------

# Maps detection type ID → (display_label, group)
ALL_DETECTION_TYPES = [
    # Gruppe: Identificerende oplysninger
    ("cpr",              "CPR-numre",                         "Identificerende oplysninger"),
    ("email",            "E-mailadresser",                    "Identificerende oplysninger"),
    ("phone",            "Telefonnumre",                      "Identificerende oplysninger"),
    # Gruppe: Finansielle oplysninger
    ("iban",             "IBAN / bankkonto",                  "Finansielle oplysninger"),
    ("credit_card",      "Kreditkortnumre",                   "Finansielle oplysninger"),
    # Gruppe: Særlige kategorier (GDPR art. 9)
    ("health",           "Helbredsoplysninger",               "Særlige kategorier (GDPR art. 9)"),
    ("race_ethnicity",   "Race / etnisk oprindelse",          "Særlige kategorier (GDPR art. 9)"),
    ("political",        "Politisk overbevisning",            "Særlige kategorier (GDPR art. 9)"),
    ("religion",         "Religiøs overbevisning",            "Særlige kategorier (GDPR art. 9)"),
    ("trade_union",      "Fagforeningsmedlemskab",            "Særlige kategorier (GDPR art. 9)"),
    ("genetics",         "Genetiske oplysninger",             "Særlige kategorier (GDPR art. 9)"),
    ("biometric",        "Biometriske oplysninger",           "Særlige kategorier (GDPR art. 9)"),
    ("sexual_orientation","Seksuel orientering",              "Særlige kategorier (GDPR art. 9)"),
    ("criminal",         "Strafbare forhold",                 "Særlige kategorier (GDPR art. 9)"),
    # Gruppe: Strukturelle indikatorer
    ("spreadsheet_headers", "Regneark-kolonneoverskrifter",   "Strukturelle indikatorer"),
    ("filename_keywords",   "Filnavns-nøgleord",              "Strukturelle indikatorer"),
]

# Maps SENSITIVE_CATEGORY_KEYWORDS key → detection type ID
SENSITIVE_CATEGORY_ID_MAP = {
    "Helbredsoplysninger":          "health",
    "Racemæssig/etnisk oprindelse": "race_ethnicity",
    "Politisk overbevisning":       "political",
    "Religiøs overbevisning":       "religion",
    "Fagforeningsmedlemskab":       "trade_union",
    "Genetiske oplysninger":        "genetics",
    "Biometriske oplysninger":      "biometric",
    "Seksuel orientering":          "sexual_orientation",
    "Strafbare forhold":            "criminal",
}

EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", re.IGNORECASE)
PHONE_INTERNATIONAL_PATTERN = re.compile(r"(?<!\d)(?:\+45|0045)[ -]?(?:\d{2}[ -]?){3}\d{2}(?!\d)")
# Kræver mellemrum som separator (XX XX XX XX) — bindestreg afvises bevidst
# for at undgå falske positive på årsperioder som "2012-2021".
PHONE_PATTERN = re.compile(r"(?<!\d)\d{2} \d{2} \d{2} \d{2}(?!\d)")
CPR_PATTERN = re.compile(r"\b(\d{6})[- ]?(\d{4})\b")
# Dansk IBAN: DK + 2 kontrolcifre + 4 registreringsnummer + 10 kontonummer = 18 tegn
IBAN_DK_PATTERN = re.compile(r"\bDK\d{2}[ ]?\d{4}[ ]?\d{4}[ ]?\d{4}[ ]?\d{2}\b", re.IGNORECASE)
# Kreditkort: Visa (4), Mastercard (51-55), Amex (34/37), Discover (6011)
CREDIT_CARD_PATTERN = re.compile(
    r"\b(?:4[0-9]{3}|5[1-5][0-9]{2}|3[47][0-9]{2}|6011)(?:[ -]?\d{4}){3}\b"
)


@dataclass
class Finding:
    path: str
    reason: str
    snippet: Optional[str] = None
    age_days: Optional[int] = None
    line_number: Optional[int] = None


@dataclass
class ScanResult:
    files_scanned: int
    findings: List[Finding]


class ScanEngine:
    def __init__(self, config_store: ConfigStore) -> None:
        self.config_store = config_store

    def _is_file_too_old_or_new(self, path: pathlib.Path, max_age_days: int) -> bool:
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return True
        age_seconds = time.time() - mtime
        return age_seconds < (max_age_days * 86400)

    def _is_ignored(self, path: pathlib.Path, ignore_paths: List[str]) -> bool:
        normalized = str(path).lower()
        for ignore in ignore_paths:
            if ignore and ignore.lower() in normalized:
                return True
        return False

    def _filename_match(self, path: pathlib.Path) -> Optional[str]:
        name = path.name.lower()
        for token in CPR_FILENAME_KEYS:
            if token in name:
                return f"Filename contains keyword '{token}'"
        return None

    def _line_number_of(self, text: str, pos: int) -> int:
        """Return 1-based line number for character position pos in text."""
        return text[:pos].count("\n") + 1

    def _matches_cpr(self, text: str) -> Optional[tuple]:
        """Return (snippet, line_number) or None."""
        for match in CPR_PATTERN.finditer(text):
            d = match.group(1)
            day = int(d[0:2])
            month = int(d[2:4])
            if month < 1 or month > 12:
                continue
            if not (1 <= day <= 31 or 41 <= day <= 71):
                continue
            return match.group(0), self._line_number_of(text, match.start())
        return None

    def _matches_email(self, text: str) -> Optional[tuple]:
        """Return (snippet, line_number) or None."""
        m = EMAIL_PATTERN.search(text)
        if m:
            return m.group(0), self._line_number_of(text, m.start())
        return None

    def _matches_phone(self, text: str) -> Optional[tuple]:
        """Return (snippet, line_number) or None."""
        m = PHONE_INTERNATIONAL_PATTERN.search(text)
        if m:
            return m.group(0), self._line_number_of(text, m.start())
        m = PHONE_PATTERN.search(text)
        if m:
            return m.group(0), self._line_number_of(text, m.start())
        return None

    def _matches_iban(self, text: str) -> Optional[tuple]:
        """Return (snippet, line_number) or None for Danish IBAN."""
        m = IBAN_DK_PATTERN.search(text)
        if m:
            return m.group(0), self._line_number_of(text, m.start())
        return None

    def _matches_credit_card(self, text: str) -> Optional[tuple]:
        """Return (snippet, line_number) or None for credit card numbers."""
        m = CREDIT_CARD_PATTERN.search(text)
        if m:
            return m.group(0), self._line_number_of(text, m.start())
        return None

    def _matches_sensitive_keywords(self, text: str, enabled_ids: set) -> Optional[tuple]:
        """Return (category_name, keyword, line_number) or None.

        Only searches categories whose detection type ID is in enabled_ids.
        """
        text_lower = text.lower()
        for category, keywords in SENSITIVE_CATEGORY_KEYWORDS.items():
            if SENSITIVE_CATEGORY_ID_MAP.get(category) not in enabled_ids:
                continue
            for kw in keywords:
                idx = text_lower.find(kw)
                if idx != -1:
                    line_num = self._line_number_of(text, idx)
                    return category, kw, line_num
        return None

    def _header_match(self, header_row: List[str]) -> Optional[str]:
        for h in header_row:
            lower = h.strip().lower()
            if any(key in lower for key in HEADER_KEYS):
                return f"Spreadsheet header indicates PII: '{h.strip()}'"
        return None

    def _extract_text_from_txt(self, path: pathlib.Path) -> str:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    def _extract_text_from_csv(self, path: pathlib.Path) -> str:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    def _extract_headers_from_csv(self, path: pathlib.Path) -> Optional[List[str]]:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f)
            try:
                return next(reader)
            except StopIteration:
                return None

    def _extract_text_from_docx(self, path: pathlib.Path) -> str:
        if not zipfile.is_zipfile(path):
            raise ValueError("Malformed docx")
        with zipfile.ZipFile(path, "r") as zf:
            try:
                xml = zf.read("word/document.xml")
            except KeyError:
                return ""
            tree = ET.fromstring(xml)
            texts = []
            for node in tree.iter():
                if node.tag.endswith("}t"):
                    texts.append(node.text or "")
            return "\n".join(texts)

    def _extract_text_from_xlsx(self, path: pathlib.Path) -> str:
        if not zipfile.is_zipfile(path):
            raise ValueError("Malformed xlsx")
        text_segments = []
        with zipfile.ZipFile(path, "r") as zf:
            for fname in zf.namelist():
                if fname.startswith("xl/worksheets/") and fname.endswith(".xml"):
                    xml = zf.read(fname)
                    tree = ET.fromstring(xml)
                    for node in tree.iter():
                        if node.tag.endswith("}t"):
                            text_segments.append(node.text or "")
            if "xl/sharedStrings.xml" in zf.namelist():
                xml = zf.read("xl/sharedStrings.xml")
                tree = ET.fromstring(xml)
                for si in tree.iter():
                    if si.tag.endswith("}t"):
                        text_segments.append(si.text or "")

        return "\n".join(text_segments)

    def _extract_text_from_xls(self, path: pathlib.Path) -> str:
        text_segments = []
        try:
            workbook = xlrd.open_workbook(str(path))
            for sheet in workbook.sheets():
                for row in range(sheet.nrows):
                    for col in range(sheet.ncols):
                        cell_value = sheet.cell_value(row, col)
                        if isinstance(cell_value, str):
                            text_segments.append(cell_value)
        except Exception as e:
            raise ValueError(f"Failed to read .xls file: {e}")
        return "\n".join(text_segments)

    def _extract_headers_from_xlsx(self, path: pathlib.Path) -> Optional[List[str]]:
        # Attempt to read first row from any sheet.
        if not zipfile.is_zipfile(path):
            return None

        with zipfile.ZipFile(path, "r") as zf:
            sheet_files = [n for n in zf.namelist() if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")]
            shared = None
            if "xl/sharedStrings.xml" in zf.namelist():
                shared_data = zf.read("xl/sharedStrings.xml")
                shared = ET.fromstring(shared_data)

            def shared_text(idx: int) -> str:
                if shared is None:
                    return ""
                si = list(shared)[idx]
                t = si.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")
                return t.text if t is not None else ""

            for sheet in sheet_files:
                xml = zf.read(sheet)
                tree = ET.fromstring(xml)
                row = None
                for r in tree.iter():
                    if r.tag.endswith("}row"):
                        row = r
                        break
                if row is None:
                    continue
                header_values = []
                for c in row.iter():
                    if c.tag.endswith("}c"):
                        v = c.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v")
                        if v is None or v.text is None:
                            continue
                        cell_type = c.attrib.get("t")
                        if cell_type == "s":
                            try:
                                idx = int(v.text)
                                header_values.append(shared_text(idx))
                            except Exception:
                                header_values.append(v.text)
                        else:
                            header_values.append(v.text)
                if header_values:
                    return header_values
        return None

    def _extract_text_from_pdf(self, path: pathlib.Path) -> str:
        if path.stat().st_size > 20 * 1024 * 1024:
            raise ValueError("PDF too large")
        text_segments = []
        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_segments.append(page_text)
        return "\n".join(text_segments)

    def scan_file(self, path: pathlib.Path, config: Dict, age_days: int) -> List[Finding]:
        findings: List[Finding] = []

        file_type = path.suffix.lower()
        if file_type not in config.get("file_types", []):
            return findings

        # Resolve enabled detection types — default to all if not configured
        all_ids = {dt[0] for dt in ALL_DETECTION_TYPES}
        enabled: set = set(config.get("detection_types", list(all_ids)))

        if "filename_keywords" in enabled:
            filename_reason = self._filename_match(path)
            if filename_reason:
                findings.append(Finding(str(path), filename_reason, age_days=age_days))

        try:
            if file_type in [".txt", ".log"]:
                text = self._extract_text_from_txt(path)
            elif file_type == ".csv":
                text = self._extract_text_from_csv(path)
            elif file_type == ".docx":
                text = self._extract_text_from_docx(path)
            elif file_type == ".xlsx":
                text = self._extract_text_from_xlsx(path)
            elif file_type == ".xls":
                text = self._extract_text_from_xls(path)
            elif file_type == ".pdf":
                text = self._extract_text_from_pdf(path)
            else:
                text = ""

            if "spreadsheet_headers" in enabled and file_type == ".csv":
                headers = self._extract_headers_from_csv(path)
                if headers:
                    header_reason = self._header_match(headers)
                    if header_reason:
                        findings.append(Finding(str(path), header_reason, age_days=age_days))
            if "spreadsheet_headers" in enabled and file_type in [".xlsx", ".xls"]:
                headers = self._extract_headers_from_xlsx(path)
                if headers:
                    header_reason = self._header_match(headers)
                    if header_reason:
                        findings.append(Finding(str(path), header_reason, age_days=age_days))

            if "cpr" in enabled:
                cpr = self._matches_cpr(text)
                if cpr:
                    snippet, lnum = cpr
                    findings.append(Finding(str(path), "CPR match", snippet, age_days=age_days, line_number=lnum))

            if "email" in enabled:
                email = self._matches_email(text)
                if email:
                    snippet, lnum = email
                    findings.append(Finding(str(path), "Email match", snippet, age_days=age_days, line_number=lnum))

            if "phone" in enabled:
                phone = self._matches_phone(text)
                if phone:
                    snippet, lnum = phone
                    findings.append(Finding(str(path), "Phone match", snippet, age_days=age_days, line_number=lnum))

            if "iban" in enabled:
                iban = self._matches_iban(text)
                if iban:
                    snippet, lnum = iban
                    findings.append(Finding(str(path), "IBAN match", snippet, age_days=age_days, line_number=lnum))

            if "credit_card" in enabled:
                cc = self._matches_credit_card(text)
                if cc:
                    snippet, lnum = cc
                    findings.append(Finding(str(path), "Kreditkortnummer match", snippet, age_days=age_days, line_number=lnum))

            sensitive = self._matches_sensitive_keywords(text, enabled)
            if sensitive:
                category, kw, lnum = sensitive
                findings.append(Finding(str(path), f"Særlig kategori: {category}", kw, age_days=age_days, line_number=lnum))

        except Exception as exc:
            logging.warning("Skipping file '%s' due to extraction error: %s", path, exc)

        return findings

    def scan(self, progress_callback=None) -> "ScanResult":
        """Scan all configured folders.

        progress_callback(current: int, total: int, current_file: str) is
        called before each file is processed so callers can show progress.
        """
        config = self.config_store.get_config()
        roots = config.get("scan_folders", []) or []
        file_types = [ext.lower() for ext in config.get("file_types", [])]
        max_age_days = config.get("file_age_days", 30)
        ignore_paths = config.get("ignore_paths", [])

        logging.info(
            "Scan config: folders=%s, file_types=%s, max_age_days=%d, ignore_paths=%s",
            roots, file_types, max_age_days, ignore_paths,
        )

        if not roots:
            logging.warning("No scan folders configured in config[scan_folders]")

        # ------------------------------------------------------------------
        # Phase 1: collect all files that pass filters (so we know the total)
        # ------------------------------------------------------------------
        eligible: List[tuple] = []   # [(file_path, age_days), ...]
        age_filtered_out = 0

        for root in roots:
            root_path = pathlib.Path(root)
            if not root_path.exists() or not root_path.is_dir():
                logging.warning("Skipping missing or invalid folder: %s", root)
                continue
            logging.info("Walking scan folder: %s", root_path)

            for dirpath, _, filenames in os.walk(root_path):
                for filename in filenames:
                    file_path = pathlib.Path(dirpath) / filename
                    if file_path.suffix.lower() not in file_types:
                        continue
                    if self._is_ignored(file_path, ignore_paths):
                        logging.debug("File ignored: %s", file_path)
                        continue
                    try:
                        age_days = int((time.time() - file_path.stat().st_mtime) / 86400)
                    except OSError:
                        logging.warning("Skipping file '%s' due to stat error", file_path)
                        continue
                    if max_age_days > 0 and age_days < max_age_days:
                        age_filtered_out += 1
                        logging.debug("File too new: %s (age %d < %d)", file_path, age_days, max_age_days)
                        continue
                    eligible.append((file_path, age_days))

        total = len(eligible)

        # ------------------------------------------------------------------
        # Phase 2: scan each file, emitting progress before each one
        # ------------------------------------------------------------------
        findings: List[Finding] = []
        for idx, (file_path, age_days) in enumerate(eligible):
            if progress_callback is not None:
                progress_callback(idx + 1, total, str(file_path))
            findings.extend(self.scan_file(file_path, config, age_days=age_days))

        logging.info(
            "Scan complete: %d age-filtered out, %d scanned, %d findings",
            age_filtered_out, total, len(findings),
        )
        return ScanResult(files_scanned=total, findings=findings)
