"""Windows Security-inspired visual theme for GDPR Scanner."""
import tkinter as tk
import tkinter.ttk as ttk

# ---------------------------------------------------------------------------
# Colour palette — Windows 11 / Windows Security look
# ---------------------------------------------------------------------------
BG = "#FFFFFF"          # Main background
BG2 = "#F3F3F3"         # Secondary background (sidebar, log area)
BG3 = "#EBEBEB"         # Hover / pressed state
BLUE = "#0078D4"        # Primary accent (Windows 11 blue)
BLUE_HOVER = "#106EBE"
BLUE_PRESSED = "#005A9E"
BLUE_LIGHT = "#CCE4F7"  # Selection highlight
TEXT = "#1A1A1A"        # Primary text
TEXT2 = "#5C5C5C"       # Secondary / caption text
BORDER = "#D1D1D1"      # Border and separator

# Severity colours
SEV_HIGH = "#D13438"        # CPR, health data
SEV_HIGH_BG = "#FDE7E9"
SEV_MED = "#CA5010"         # Financial (IBAN, credit card)
SEV_MED_BG = "#FEF0E6"
SEV_SPECIAL = "#881798"     # GDPR art. 9 special categories
SEV_SPECIAL_BG = "#F5E6F8"
SEV_INFO = "#0078D4"        # Email, phone
SEV_INFO_BG = "#EBF3FB"
SEV_LOW = "#5C5C5C"         # Filename keywords
SEV_LOW_BG = "#F3F3F3"


def severity_colors(reason: str) -> tuple[str, str]:
    """Return (accent_color, background_color) for a finding reason."""
    if "CPR" in reason or "Helbredd" in reason:
        return SEV_HIGH, SEV_HIGH_BG
    if "IBAN" in reason or "Kreditkort" in reason:
        return SEV_MED, SEV_MED_BG
    if reason.startswith("Særlig kategori:"):
        return SEV_SPECIAL, SEV_SPECIAL_BG
    if "Email" in reason or "Phone" in reason:
        return SEV_INFO, SEV_INFO_BG
    return SEV_LOW, SEV_LOW_BG


def apply_theme(root: tk.Tk) -> None:
    """Apply Windows Security-inspired theme to the Tk root.

    Call once after creating the root Tk window.  All ttk widgets on the
    same root (including Toplevel children) inherit these styles.
    """
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    # ----- Base -----
    style.configure(".", background=BG, foreground=TEXT, font=("Segoe UI", 9),
                    relief="flat")

    # ----- Frames -----
    style.configure("TFrame", background=BG)
    style.configure("Secondary.TFrame", background=BG2)

    # ----- Labels -----
    style.configure("TLabel", background=BG, foreground=TEXT,
                    font=("Segoe UI", 9))
    style.configure("Heading.TLabel", background=BG, foreground=TEXT,
                    font=("Segoe UI", 12, "bold"))
    style.configure("SectionHeading.TLabel", background=BG, foreground=TEXT,
                    font=("Segoe UI", 10, "bold"))
    style.configure("Caption.TLabel", background=BG, foreground=TEXT2,
                    font=("Segoe UI", 9))
    style.configure("Link.TLabel", background=BG, foreground=BLUE,
                    font=("Segoe UI", 9))

    # ----- Notebook / Tabs -----
    style.configure("TNotebook", background=BG2, borderwidth=0,
                    tabmargins=[0, 0, 0, 0])
    # Inactive tabs: small font, muted
    style.configure("TNotebook.Tab", background=BG2, foreground=TEXT2,
                    padding=[16, 6], font=("Segoe UI", 8), borderwidth=0)
    # Selected tab: larger font, accent colour, white bg
    style.map("TNotebook.Tab",
              background=[("selected", BG), ("active", BG3)],
              foreground=[("selected", BLUE), ("active", TEXT)],
              font=[("selected", ("Segoe UI", 10, "bold"))],
              padding=[("selected", [20, 10])])

    # ----- Buttons -----
    style.configure("TButton", background=BG, foreground=TEXT,
                    bordercolor=BORDER, relief="solid", borderwidth=1,
                    padding=[14, 6], font=("Segoe UI", 9), focusthickness=0)
    style.map("TButton",
              background=[("active", BG2), ("pressed", BG3)],
              bordercolor=[("active", "#8A8A8A")])

    style.configure("Primary.TButton", background=BLUE, foreground="white",
                    bordercolor=BLUE, relief="flat", borderwidth=0,
                    padding=[14, 6], font=("Segoe UI", 9), focusthickness=0)
    style.map("Primary.TButton",
              background=[("active", BLUE_HOVER), ("pressed", BLUE_PRESSED)],
              bordercolor=[("active", BLUE_HOVER)])

    style.configure("Danger.TButton", background=BG, foreground=SEV_HIGH,
                    bordercolor=SEV_HIGH, relief="solid", borderwidth=1,
                    padding=[14, 6], font=("Segoe UI", 9), focusthickness=0)
    style.map("Danger.TButton",
              background=[("active", SEV_HIGH_BG), ("pressed", "#F9D0D2")],
              foreground=[("active", SEV_HIGH)])

    # ----- Checkbutton -----
    style.configure("TCheckbutton", background=BG, foreground=TEXT,
                    font=("Segoe UI", 9))
    style.map("TCheckbutton", background=[("active", BG)])

    # ----- Combobox -----
    style.configure("TCombobox", fieldbackground=BG, background=BG,
                    foreground=TEXT, selectbackground=BLUE_LIGHT,
                    selectforeground=TEXT, bordercolor=BORDER, padding=[4, 4])
    style.map("TCombobox",
              bordercolor=[("focus", BLUE)],
              fieldbackground=[("readonly", BG), ("disabled", BG2)],
              foreground=[("readonly", TEXT), ("disabled", TEXT2)],
              selectforeground=[("readonly", TEXT)],
              selectbackground=[("readonly", BLUE_LIGHT)])

    # ----- Spinbox -----
    style.configure("TSpinbox", fieldbackground=BG, background=BG,
                    bordercolor=BORDER, padding=[4, 4])
    style.map("TSpinbox", bordercolor=[("focus", BLUE)])

    # ----- Scrollbar -----
    style.configure("TScrollbar", background=BG2, troughcolor=BG,
                    bordercolor=BG, arrowcolor=TEXT2, relief="flat",
                    width=10, arrowsize=10)
    style.map("TScrollbar", background=[("active", "#ABABAB")])

    # ----- LabelFrame -----
    style.configure("TLabelframe", background=BG, bordercolor=BORDER,
                    relief="solid", borderwidth=1)
    style.configure("TLabelframe.Label", background=BG, foreground=TEXT2,
                    font=("Segoe UI", 8))

    # ----- Separator -----
    style.configure("TSeparator", background=BORDER)

    root.configure(background=BG)
