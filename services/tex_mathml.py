"""Petit convertisseur LaTeX → MathML pour les formules de la note de calcul.

Les formules sont écrites en syntaxe LaTeX (ce qu'un ingénieur écrirait dans sa note)
et converties en MathML, que Chromium / Edge / WebView2 composent comme LaTeX avec la
police Latin Modern Math. Sous-ensemble pris en charge, suffisant pour le BAEL / RPS :

  \\frac{a}{b}  \\sqrt{x}  x_i  x^2  x_{u,\\lim}  \\left( … \\right)  \\left[ … \\right]
  lettres grecques  \\le \\ge \\pm \\times \\cdot \\approx \\Rightarrow \\sum \\min \\max \\lim
  \\text{…}  \\mathrm{…}  espaces \\, \\; \\quad  virgule décimale française {,}

Toute commande inconnue lève ValueError : une formule mal écrite se voit aux tests,
pas dans la note du client.
"""
from __future__ import annotations

import html
from typing import List, Tuple

GRECS = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "varepsilon": "ε", "epsilon": "ϵ", "eta": "η",
    "theta": "θ", "lambda": "λ", "mu": "μ", "nu": "ν", "pi": "π", "rho": "ρ", "sigma": "σ", "tau": "τ",
    "upsilon": "υ", "phi": "φ", "varphi": "φ", "psi": "ψ", "omega": "ω", "Delta": "Δ", "Sigma": "Σ",
    "Phi": "Φ", "Omega": "Ω",
}
OPERATEURS = {
    "le": "≤", "leq": "≤", "ge": "≥", "geq": "≥", "pm": "±", "times": "×", "cdot": "·", "approx": "≈",
    "Rightarrow": "⇒", "to": "→", "neq": "≠", "infty": "∞",
}
FONCTIONS = {"lim", "min", "max", "sin", "cos", "tan", "log", "ln", "exp"}
GRANDS = {"sum": "∑"}
ESPACES = {",": "0.1667em", ";": "0.2778em", ":": "0.2222em", "quad": "1em", "qquad": "2em", " ": "0.25em"}
OUVRANTS = {"(": "(", "[": "[", "\\{": "{", "|": "|", ".": ""}
FERMANTS = {")": ")", "]": "]", "\\}": "}", "|": "|", ".": ""}


def _e(t: str) -> str:
    return html.escape(t, quote=False)


class _Lecteur:
    def __init__(self, src: str):
        self.s, self.i = src, 0

    def fin(self) -> bool:
        return self.i >= len(self.s)

    def voir(self) -> str:
        return self.s[self.i] if not self.fin() else ""

    def commande(self) -> str:
        """Lit « \\nom » (ou un caractère après « \\ ») et renvoie le nom."""
        assert self.s[self.i] == "\\"
        self.i += 1
        j = self.i
        if j < len(self.s) and self.s[j].isalpha():
            while j < len(self.s) and self.s[j].isalpha():
                j += 1
        else:
            j += 1
        nom, self.i = self.s[self.i:j], j
        return nom

    def sauter_espaces(self):
        while not self.fin() and self.s[self.i] == " ":
            self.i += 1


def _groupe(lec: _Lecteur) -> str:
    """Argument : {…} ou un seul atome."""
    lec.sauter_espaces()
    if lec.fin():
        raise ValueError("argument manquant en fin de formule")
    if lec.voir() == "{":
        lec.i += 1
        contenu = _liste(lec, fin="}")
        lec.i += 1
        return f"<mrow>{contenu}</mrow>"
    return _atome(lec)


def _texte_brut(lec: _Lecteur) -> str:
    lec.sauter_espaces()
    if lec.voir() != "{":
        raise ValueError("argument entre accolades attendu")
    prof, j = 0, lec.i
    while j < len(lec.s):
        if lec.s[j] == "{":
            prof += 1
        elif lec.s[j] == "}":
            prof -= 1
            if prof == 0:
                break
        j += 1
    t = lec.s[lec.i + 1:j]
    lec.i = j + 1
    return t


def _delimiteur(lec: _Lecteur, table: dict) -> str:
    lec.sauter_espaces()
    if lec.voir() == "\\":
        nom = "\\" + lec.commande()
    else:
        nom = lec.voir()
        lec.i += 1
    if nom not in table:
        raise ValueError(f"délimiteur inconnu : {nom}")
    return table[nom]


def _atome(lec: _Lecteur) -> str:
    c = lec.voir()
    if c == "\\":
        nom = lec.commande()
        if nom == "frac":
            num, den = _groupe(lec), _groupe(lec)
            return f"<mfrac>{num}{den}</mfrac>"
        if nom == "sqrt":
            return f"<msqrt>{_groupe(lec)}</msqrt>"
        if nom == "overline":     # valeur limite : σ̄
            return f'<mover accent="true">{_groupe(lec)}<mo stretchy="true">¯</mo></mover>'
        if nom in ("text", "mathrm"):
            t = _texte_brut(lec)
            return f'<mtext>{_e(t)}</mtext>' if nom == "text" else f'<mi mathvariant="normal">{_e(t)}</mi>'
        if nom == "left":
            g = _delimiteur(lec, OUVRANTS)
            contenu = _liste(lec, fin="\\right")
            lec.commande()                      # « right »
            d = _delimiteur(lec, FERMANTS)
            mo_g = f'<mo fence="true" stretchy="true">{_e(g)}</mo>' if g else ""
            mo_d = f'<mo fence="true" stretchy="true">{_e(d)}</mo>' if d else ""
            return f"<mrow>{mo_g}{contenu}{mo_d}</mrow>"
        if nom in GRECS:
            return f"<mi>{GRECS[nom]}</mi>"
        if nom in OPERATEURS:
            return f"<mo>{OPERATEURS[nom]}</mo>"
        if nom in FONCTIONS:
            return f'<mi mathvariant="normal">{nom}</mi>'
        if nom in GRANDS:
            return f'<mo largeop="true">{GRANDS[nom]}</mo>'
        if nom in ESPACES:
            return f'<mspace width="{ESPACES[nom]}"></mspace>'
        if nom in ("{", "}", "%", "_"):
            return f"<mo>{_e(nom)}</mo>"
        raise ValueError(f"commande LaTeX non prise en charge : \\{nom}")
    if c == "{":
        lec.i += 1
        contenu = _liste(lec, fin="}")
        lec.i += 1
        return f"<mrow>{contenu}</mrow>"
    if c.isdigit():
        j = lec.i
        while j < len(lec.s) and (lec.s[j].isdigit() or lec.s[j] == "." or lec.s.startswith("{,}", j)):
            j += 3 if lec.s.startswith("{,}", j) else 1
        nombre = lec.s[lec.i:j].replace("{,}", ",")
        lec.i = j
        return f"<mn>{_e(nombre)}</mn>"
    lec.i += 1
    if c.isalpha():
        return f"<mi>{_e(c)}</mi>"
    if c in "+-=<>/()[]|,;:!'":
        return f"<mo>{_e('−' if c == '-' else c)}</mo>"
    if c == "~":
        return '<mspace width="0.25em"></mspace>'
    return f"<mo>{_e(c)}</mo>"


def _liste(lec: _Lecteur, fin: str = "") -> str:
    morceaux: List[str] = []
    while not lec.fin():
        lec.sauter_espaces()
        if lec.fin():
            break
        if fin and lec.s.startswith(fin, lec.i):
            break
        if lec.voir() in "_^":
            if not morceaux:
                raise ValueError("indice ou exposant sans base")
            base = morceaux.pop()
            sub = sup = None
            for _ in range(2):
                if lec.voir() == "_" and sub is None:
                    lec.i += 1
                    sub = _groupe(lec)
                elif lec.voir() == "^" and sup is None:
                    lec.i += 1
                    sup = _groupe(lec)
                lec.sauter_espaces()
            if sub and sup:
                morceaux.append(f"<msubsup>{base}{sub}{sup}</msubsup>")
            elif sub:
                morceaux.append(f"<msub>{base}{sub}</msub>")
            else:
                morceaux.append(f"<msup>{base}{sup}</msup>")
            continue
        morceaux.append(_atome(lec))
    if fin and lec.fin():
        raise ValueError(f"« {fin} » attendu")
    return "".join(morceaux)


def mathml(tex: str, bloc: bool = False) -> str:
    """Formule LaTeX → élément <math>. bloc=True : formule centrée en display."""
    lec = _Lecteur(tex.strip())
    corps = _liste(lec)
    attr = ' display="block"' if bloc else ""
    return f'<math xmlns="http://www.w3.org/1998/Math/MathML"{attr}><mrow>{corps}</mrow></math>'


def caracteres_utilises(textes: List[str]) -> str:
    """Caractères à conserver lors du sous-ensemble de la police mathématique."""
    return "".join(sorted(set("".join(textes))))
