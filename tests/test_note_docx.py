"""Export Word de la note de calcul : le .docx reprend la note du projet, sans contenu ajouté ni perdu."""
import io
import pathlib
import re
import sys

import pytest
from docx import Document
from lxml import html as lhtml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "services"))

import engine_service as e  # noqa: E402
import note_docx as nd  # noqa: E402
import report_service as rs  # noqa: E402
import robot_ossature as ro  # noqa: E402


def _norm(t):
    return re.sub(r"\s+", " ", t or "").strip()


def _note(**kw):
    o = ro.ossature_simulation()
    lot = e.lot(e.LotInput(**{k: o[k] for k in ("poteaux", "poutres", "semelles", "voiles")}))
    pot = [dict(l["resultat"], nom=l["nom"], niveau=l["niveau"], nu_kn=l["entree"]["nu_kn"]) for l in lot["poteaux"][:4]]
    data = dict(projet="Immeuble R+4 — Casablanca", client="SARL Exemple", site="Casablanca", lot=lot, poteaux=pot,
                bureau={"nom": "BET Exemple", "ingenieur": "Ingénieur"})
    data.update(kw)
    return rs.build_note(rs.NoteInput(**data))


def _textes_docx(doc):
    t = [p.text for p in doc.paragraphs]
    for tb in doc.tables:
        for row in tb.rows:
            for c in row.cells:
                t.append(c.text)
    return _norm(" ".join(t))


def _sans_math(el):
    el = lhtml.fromstring(lhtml.tostring(el))
    for m in el.xpath(".//math"):
        m.drop_tree()
    return _norm(el.text_content())


@pytest.fixture(scope="module")
def note_et_docx():
    h = _note()
    octets, stats = nd.docx_depuis_html(h)
    return h, Document(io.BytesIO(octets)), stats


def test_tous_les_titres_et_cellules_de_la_note_sont_dans_le_docx(note_et_docx):
    h, doc, stats = note_et_docx
    arbre = lhtml.document_fromstring(h)
    texte = _textes_docx(doc)
    titres = arbre.xpath("//body//h1|//body//h2|//body//h3|//body//h4")
    assert stats["titres"] == len(titres)
    for el in titres + arbre.xpath("//body//td|//body//th|//body//caption|//body//p"):
        s = _sans_math(el)
        for morceau in filter(None, re.split(r"\s{2,}", s)):
            assert _norm(morceau).replace(" ", "") in texte.replace(" ", ""), morceau


def test_nombre_de_tableaux_et_d_equations(note_et_docx):
    h, doc, stats = note_et_docx
    arbre = lhtml.document_fromstring(h)
    assert stats["tableaux"] == len(arbre.xpath("//body//table"))
    assert stats["equations"] == len(arbre.xpath("//body//math"))


def test_rien_d_invente_les_sections_absentes_restent_absentes():
    """Projet sans dalles ni planchers : le .docx n'en parle pas plus que la note HTML."""
    h = _note(projet="Hangar — Fès", site="Fès")
    octets, _ = nd.docx_depuis_html(h)
    texte = _textes_docx(Document(io.BytesIO(octets)))
    assert "Hangar — Fès" in texte and "Immeuble R+4" not in texte
    for absent in ("Planchers à corps creux", "Dalles pleines"):
        assert (absent in texte) == (absent in h)


@pytest.mark.skipif(nd.transformeur() is None, reason="MML2OMML.XSL (Microsoft Office) absent de ce poste")
def test_equations_word_natives(note_et_docx):
    _, doc, stats = note_et_docx
    assert stats["equations_natives"] is True
    omaths = doc.element.body.xpath(".//m:oMath")
    assert len(omaths) == stats["equations"]


def test_sans_office_les_equations_restent_lisibles_et_c_est_signale(monkeypatch):
    monkeypatch.setitem(nd._XSLT, "t", None)
    h = '<html><body><h2>T</h2><div class="equation"><math><mi>N</mi><mo>≤</mo><mn>5</mn></math>' \
        '<span class="no">(1)</span></div></body></html>'
    octets, stats = nd.docx_depuis_html(h)
    doc = Document(io.BytesIO(octets))
    assert stats["equations"] == 1 and stats["equations_natives"] is False
    assert "N≤5" in _textes_docx(doc).replace(" ", "")


def test_endpoint_ecrit_le_fichier(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    monkeypatch.setattr(rs, "OUT", tmp_path)
    cl = TestClient(rs.app)
    r = cl.post("/note/docx", json={"projet": "Villa R+1 — Agadir", "bureau": {"nom": "BET"}})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["fichier"].endswith(".docx") and (tmp_path / j["fichier"]).is_file()
    g = cl.get("/note/docx/" + j["fichier"])
    assert g.status_code == 200 and g.content[:2] == b"PK"
    assert cl.get("/note/docx/..%5Cbureau.json").status_code in (400, 404)
