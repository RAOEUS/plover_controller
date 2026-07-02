"""Plover system for the Mussel Power layout used with plover-controller.

Mussel Power is a 28-key layout that is completely different from the standard
23-key Ward Stone Ireland (WSI) English layout. Each hand has eight numbered
steno keys plus small (``l``/``r``) and large (``L``/``R``) rotation keys, and
the two hands share only the ``A O E U`` vowel band.

    left            vowels        right
    1- .. 8-        A- O-         -1 .. -8
    l- r- L- R-     -E -U         -l -r -L -R

Selecting this system in Plover (Configure -> System) rebinds the controller
to these keys via ``KEYMAPS["Controller"]`` below, so no separate machine is
needed -- the same "Controller" machine emits both WSI and Mussel keys, and the
active system decides which ones are meaningful.

NOTE: the theory-specific bits (``UNDO_STROKE_STENO``, orthography, and the
bundled dictionary) are a working scaffold. Drop in the authoritative Mussel
Power definitions from your own system module where they differ.
"""

# fmt: off
KEYS = (
    "1-", "2-", "3-", "4-", "5-", "6-", "7-", "8-",
    "l-", "r-", "L-", "R-",
    "A-", "O-",
    "-E", "-U",
    "-1", "-2", "-3", "-4", "-5", "-6", "-7", "-8",
    "-l", "-r", "-L", "-R",
)
# fmt: on

# The vowel band sits between the banks, so the hyphen is implicit there.
IMPLICIT_HYPHEN_KEYS = ("A-", "O-", "-E", "-U")

SUFFIX_KEYS = ()

# Mussel's 1-8 are consonant keys, not a number bar, so there is no number key.
NUMBER_KEY = None
NUMBERS = {}

# Placeholder undo stroke -- replace with the real one for the theory.
UNDO_STROKE_STENO = "-8"

ORTHOGRAPHY_RULES = []
ORTHOGRAPHY_RULES_ALIASES = {}
ORTHOGRAPHY_WORDLIST = None

# Identity keymap: the controller profile emits Mussel key names directly, so
# each system action binds to the machine key of the same name.
KEYMAPS = {
    "Controller": {key: key for key in KEYS},
}

DICTIONARIES_ROOT = "asset:plover:assets"
DEFAULT_DICTIONARIES = ()
