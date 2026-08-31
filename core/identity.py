"""The identity key a typed name resolves to (backlog B13, I8).

A pure decision: plain string in, plain string out, no database and no Django machinery
(specs/testing.md). What the rule deliberately refuses to fold is decided in
``specs/adr/0006-submitter-identity.md``.
"""

import unicodedata


def normalize_person_name(raw: str) -> str:
    """The key ``raw`` resolves a submitter by: accents, case and spacing folded away (I8).

    Returns an empty string for a name made of nothing the rule keeps, which the form turns into
    a validation error rather than a row.
    """
    decomposed = unicodedata.normalize("NFKD", raw)
    unaccented = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(unaccented.casefold().split())
