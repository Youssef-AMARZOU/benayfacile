"""Convertisseur LaTeX → MathML des formules de la note."""
import pathlib
import sys
import xml.dom.minidom

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "services"))

from tex_mathml import mathml  # noqa: E402


def bien_forme(m: str):
    xml.dom.minidom.parseString(m)        # lève une erreur si le XML est mal formé
    return m


def test_fraction_indices_et_grec():
    m = bien_forme(mathml(r"\mu = \frac{M_u}{b\,d^2 f_{bu}}"))
    assert "<mi>μ</mi>" in m and "<mfrac>" in m
    assert "<msub><mi>M</mi><mi>u</mi></msub>" in m
    assert "<msup><mi>d</mi><mn>2</mn></msup>" in m


def test_formule_bael_poteau_complete():
    m = bien_forme(mathml(r"N_u \le N_{u,\lim} = \alpha \left[ \frac{B_r f_{c28}}{0{,}9\,\gamma_b} + \frac{A f_e}{\gamma_s} \right]", bloc=True))
    assert 'display="block"' in m and "<mn>0,9</mn>" in m and "<mo>≤</mo>" in m
    assert '<mo fence="true" stretchy="true">[</mo>' in m
    assert '<mi mathvariant="normal">lim</mi>' in m


def test_racine_texte_et_somme():
    m = bien_forme(mathml(r"\alpha = 1{,}25 \left(1 - \sqrt{1 - 2\mu}\right) \quad \text{et} \quad F_n = \frac{(F - F_t) W_n h_n}{\sum W_i h_i}"))
    assert "<msqrt>" in m and "<mtext>et</mtext>" in m and "∑" in m and "<mo>−</mo>" in m


def test_indice_et_exposant_ensemble():
    m = bien_forme(mathml(r"f_{c28}^{1/3}"))
    assert m.count("<msubsup>") == 1


@pytest.mark.parametrize("faux", [r"\inconnu{x}", r"\frac{a}", r"_x", r"\left( a"])
def test_erreurs_detectees(faux):
    with pytest.raises((ValueError, IndexError, AssertionError)):
        mathml(faux)


def test_valeur_limite_surlignee():
    m = bien_forme(mathml(r"\sigma \le \overline{\sigma}_{st}"))
    assert "<mover" in m and "¯" in m
