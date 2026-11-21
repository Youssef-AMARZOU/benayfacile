"""Export Word (.docx) de la note de calcul.

La note Word est tirée du MÊME document que la note HTML (`note_calcul.construire`) : on ne réécrit
aucun contenu, on convertit la structure (titres, paragraphes, tableaux, listes, équations, images).
Rien n'est spécifique à un projet : tout ce qui est dans la note du projet passe dans le .docx.

Équations : la MathML de la note est convertie en équations Word natives (OMML) avec la feuille
MML2OMML.XSL fournie par Microsoft Office. Elle n'est pas redistribuée avec l'application ; si Office
n'est pas installé, l'équation est écrite en texte linéaire et le résultat le signale
(`equations_natives = False`), sans le masquer.
"""
from __future__ import annotations

import base64
import io
import os
import pathlib
import re
from typing import Optional

from docx import Document
from docx.enum.section import WD_ORIENT  # noqa: F401
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from lxml import etree, html as lhtml

MATHML_NS = "http://www.w3.org/1998/Math/MathML"
BLOCS = {"p", "div", "section", "table", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "header", "footer",
         "article", "main", "figure", "blockquote", "pre", "hr"}
IGNORES = {"style", "script", "head", "title", "meta", "link", "colgroup", "col", "button", "input", "noscript"}
TITRES = {"h1": 0, "h2": 1, "h3": 2, "h4": 3, "h5": 4, "h6": 5}
LARGEUR_UTILE_CM = 17.0      # A4 (21 cm) − 2 × 2 cm de marges


# ───────────── feuille MML2OMML (Office) ─────────────
def chemins_xsl() -> list[pathlib.Path]:
    """Emplacements usuels de MML2OMML.XSL (Office 2013 à 365, 32 ou 64 bits) ; BNAY_MML2OMML d'abord."""
    c = []
    if os.environ.get("BNAY_MML2OMML"):
        c.append(pathlib.Path(os.environ["BNAY_MML2OMML"]))
    for base in filter(None, {os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"),
                              os.environ.get("ProgramW6432")}):
        for sous in ("Microsoft Office/root/Office16", "Microsoft Office/Office16",
                     "Microsoft Office/root/Office15", "Microsoft Office/Office15"):
            c.append(pathlib.Path(base) / sous / "MML2OMML.XSL")
    return c


_XSLT: dict = {}


def transformeur() -> Optional[etree.XSLT]:
    if "t" not in _XSLT:
        _XSLT["t"] = None
        for p in chemins_xsl():
            if p.is_file():
                try:
                    _XSLT["t"] = etree.XSLT(etree.parse(str(p)))
                    break
                except Exception:   # feuille illisible : on essaie la suivante
                    continue
    return _XSLT["t"]


def _vers_mathml(el) -> etree._Element:
    """Élément <math> issu du parseur HTML → arbre MathML avec son espace de noms."""
    def copie(e):
        n = etree.Element(f"{{{MATHML_NS}}}{e.tag}", {k: v for k, v in e.attrib.items() if k != "xmlns"})
        n.text = e.text
        for f in e:
            if isinstance(f.tag, str):
                c = copie(f)
                c.tail = f.tail
                n.append(c)
        return n
    return copie(el)


def _texte_lineaire(el) -> str:
    return re.sub(r"\s+", " ", "".join(el.itertext())).strip()


# ───────────── convertisseur ─────────────
class Convertisseur:
    def __init__(self):
        self.doc = Document()
        self.xslt = transformeur()
        self.stats = {"titres": 0, "tableaux": 0, "equations": 0, "equations_natives": 0, "images": 0,
                      "paragraphes": 0}
        self._mise_en_page()

    def _mise_en_page(self):
        s = self.doc.sections[0]
        s.page_width, s.page_height = Cm(21), Cm(29.7)
        for m in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
            setattr(s, m, Cm(2))
        st = self.doc.styles["Normal"]
        st.font.name = "Calibri"
        st.font.size = Pt(10)
        st.paragraph_format.space_after = Pt(4)
        pied = s.footer.paragraphs[0]
        pied.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        self._champ(pied, "PAGE")

    @staticmethod
    def _champ(par, code):
        r = par.add_run()
        for typ, txt in (("begin", None), (None, code), ("end", None)):
            if typ:
                e = OxmlElement("w:fldChar")
                e.set(qn("w:fldCharType"), typ)
            else:
                e = OxmlElement("w:instrText")
                e.set(qn("xml:space"), "preserve")
                e.text = f" {txt} "
            r._r.append(e)

    # — inline —
    def inline(self, par, el, fmt=None):
        fmt = dict(fmt or {})
        tag = el.tag if isinstance(el.tag, str) else ""
        if tag in IGNORES:
            return
        if tag == "math":
            self.equation(par, el)
            return
        if tag == "br":
            par.add_run().add_break()
            return
        if tag == "img":
            self.image(par, el)
            return
        cl = set((el.get("class") or "").split())
        if tag in ("b", "strong", "th"):
            fmt["gras"] = True
        if tag in ("i", "em"):
            fmt["italique"] = True
        if tag == "sub":
            fmt["indice"] = True
        if tag == "sup":
            fmt["exposant"] = True
        if el.text:
            self._run(par, el.text, fmt)
        for f in el:
            self.inline(par, f, fmt)
            if f.tail:
                self._run(par, f.tail, fmt)
        if cl & {"sn", "num"} and par.runs:   # numéro de chapitre / sommaire : séparé du titre
            par.runs[-1].text += " " if tag != "span" or "sn" not in cl else "	"

    def _run(self, par, texte, fmt):
        texte = re.sub(r"\s+", " ", texte)
        if not texte or (texte == " " and not par.runs):
            return
        r = par.add_run(texte)
        r.bold = fmt.get("gras") or None
        r.italic = fmt.get("italique") or None
        r.font.subscript = fmt.get("indice") or None
        r.font.superscript = fmt.get("exposant") or None

    def equation(self, par, el):
        self.stats["equations"] += 1
        if self.xslt is not None:
            try:
                omml = self.xslt(etree.ElementTree(_vers_mathml(el))).getroot()
                if omml is not None:
                    par._p.append(etree.fromstring(etree.tostring(omml)))
                    self.stats["equations_natives"] += 1
                    return
            except Exception:
                pass
        r = par.add_run(_texte_lineaire(el))
        r.font.name = "Cambria Math"
        r.italic = True

    def image(self, par, el):
        src = el.get("src") or ""
        m = re.match(r"data:image/[a-z+]+;base64,(.*)", src, re.S)
        if not m:
            return
        try:
            par.add_run().add_picture(io.BytesIO(base64.b64decode(m.group(1))), height=Cm(2.2))
            self.stats["images"] += 1
        except Exception:     # image illisible : ignorée plutôt que de bloquer l'export
            pass

    # — blocs —
    def saut_de_page(self):
        """Saut de page, sauf si le document vient d'en recevoir un (pas de page blanche)."""
        corps = self.doc.element.body
        dernier = corps[-2] if len(corps) > 1 else None     # le dernier enfant est sectPr
        if dernier is not None and dernier.xpath('.//w:br[@w:type="page"]') and not "".join(dernier.itertext()).strip():
            return
        self.doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    def _a_des_blocs(self, el):
        return any(isinstance(f.tag, str) and f.tag in BLOCS for f in el)

    def _classes(self, el):
        return set((el.get("class") or "").split())

    def bloc(self, el, conteneur=None, niveau_liste=0):
        tag = el.tag if isinstance(el.tag, str) else ""
        if tag in IGNORES or not tag:
            return
        cl = self._classes(el)
        cont = conteneur or self.doc
        if tag in TITRES:
            if "saut" in cl and conteneur is None and self.stats["paragraphes"]:
                self.saut_de_page()
            p = cont.add_heading(level=TITRES[tag])
            self.inline(p, el)
            self.stats["titres"] += 1
            return
        if tag == "table":
            self.tableau(el, cont)
            return
        if tag in ("ul", "ol"):
            for li in el:
                if isinstance(li.tag, str) and li.tag == "li":
                    self.item(li, cont, tag, niveau_liste)
            return
        if tag == "hr":
            return
        if tag == "section" and "garde" in cl:
            self._enfants(el, cont, niveau_liste)
            self.saut_de_page()
            return
        if tag in ("div", "section", "header", "footer", "article", "main", "figure", "blockquote") \
                and self._a_des_blocs(el):
            self._enfants(el, cont, niveau_liste)
            return
        # bloc « feuille » : un paragraphe
        if not _texte_lineaire(el) and not el.xpath(".//img|.//math"):
            return
        if "equation" in cl:
            self.equation_numerotee(el, cont)
            return
        p = cont.add_paragraph()
        self.stats["paragraphes"] += 1
        if "t1" in cl:
            p.style = self.doc.styles["Title"]
        elif cl & {"sur-titre", "objet", "bet-nom"}:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        self.inline(p, el)
        if cl & {"objet", "bet-nom"}:
            for r in p.runs:
                r.bold = True
                r.font.size = Pt(14)

    def equation_numerotee(self, el, cont):
        t = cont.add_table(rows=1, cols=2)
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        largeurs = (Cm(LARGEUR_UTILE_CM - 1.5), Cm(1.5))
        p_eq, p_no = t.cell(0, 0).paragraphs[0], t.cell(0, 1).paragraphs[0]
        p_eq.alignment, p_no.alignment = WD_ALIGN_PARAGRAPH.CENTER, WD_ALIGN_PARAGRAPH.RIGHT
        for j, w in enumerate(largeurs):
            t.cell(0, j).width = w
            t.cell(0, j).vertical_alignment = 1     # centré verticalement
        for f in el:
            if not isinstance(f.tag, str):
                continue
            if "no" in self._classes(f):
                self.inline(p_no, f)
            else:
                self.inline(p_eq, f)
        self.stats["paragraphes"] += 1

    def _enfants(self, el, cont, niveau_liste):
        """Enfants d'un conteneur : le texte « libre » entre les blocs devient un paragraphe."""
        tampon = []

        def vider():
            if any(isinstance(t, str) and t.strip() or not isinstance(t, str) for t in tampon):
                p = cont.add_paragraph()
                self.stats["paragraphes"] += 1
                for t in tampon:
                    if isinstance(t, str):
                        self._run(p, t, {})
                    else:
                        self.inline(p, t)
                        if t.tail:
                            self._run(p, t.tail, {})
            tampon.clear()

        if el.text and el.text.strip():
            tampon.append(el.text)
        for f in el:
            if isinstance(f.tag, str) and f.tag in BLOCS:
                vider()
                self.bloc(f, cont if cont is not self.doc else None, niveau_liste)
                if f.tail and f.tail.strip():
                    tampon.append(f.tail)
            elif isinstance(f.tag, str):
                f_tail, f.tail = f.tail, None
                tampon.append(f)
                if f_tail:
                    tampon.append(f_tail)
        vider()

    def item(self, li, cont, type_liste, niveau):
        deja_numerote = li.find("span") is not None and "sn" in self._classes(li.find("span"))             or li.find("a/span") is not None and "sn" in self._classes(li.find("a/span"))
        if deja_numerote:
            p = cont.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.8 * niveau)
            p.paragraph_format.space_after = Pt(1)
            p.paragraph_format.tab_stops.add_tab_stop(Cm(0.8 * niveau + 1.0))
        else:
            style = "List Number" if type_liste == "ol" else "List Bullet"
            if niveau:
                style += f" {min(niveau + 1, 3)}"
            p = cont.add_paragraph(style=self.doc.styles[style])
        self.stats["paragraphes"] += 1
        for f in [li]:
            if f.text:
                self._run(p, f.text, {})
        for f in li:
            if isinstance(f.tag, str) and f.tag in ("ul", "ol"):
                self.bloc(f, None if cont is self.doc else cont, niveau + 1)
            else:
                self.inline(p, f)
            if f.tail:
                self._run(p, f.tail, {})

    def tableau(self, el, cont):
        lignes = [tr for tr in el.iter("tr")]
        if not lignes:
            return
        cap = el.find("caption")
        if cap is not None:
            pc = cont.add_paragraph(style=self.doc.styles["Caption"])
            self.inline(pc, cap)
            pc.paragraph_format.keep_with_next = True
        ncol = max(sum(int(c.get("colspan") or 1) for c in tr if isinstance(c.tag, str) and c.tag in ("td", "th"))
                   for tr in lignes)
        t = cont.add_table(rows=len(lignes), cols=ncol)
        t.style = self.doc.styles["Table Grid"]
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        self.stats["tableaux"] += 1
        largeurs = self._largeurs(el, ncol)
        occupe = set()
        for i, tr in enumerate(lignes):
            entete = tr.getparent() is not None and tr.getparent().tag == "thead"
            j = 0
            for c in tr:
                if not (isinstance(c.tag, str) and c.tag in ("td", "th")):
                    continue
                while (i, j) in occupe:
                    j += 1
                if j >= ncol:
                    break
                cs, rs = int(c.get("colspan") or 1), int(c.get("rowspan") or 1)
                cel = t.cell(i, j)
                if cs > 1 or rs > 1:
                    cel = cel.merge(t.cell(min(i + rs - 1, len(lignes) - 1), min(j + cs - 1, ncol - 1)))
                for a in range(i, i + rs):
                    for b in range(j, j + cs):
                        occupe.add((a, b))
                p = cel.paragraphs[0]
                if p.text:      # cellule fusionnée déjà remplie
                    p = cel.add_paragraph()
                cl = self._classes(c)
                if cl & {"n", "num"}:
                    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                elif cl & {"c"} or entete:
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                self.inline(p, c, {"gras": entete or c.tag == "th"})
                for r in p.runs:
                    r.font.size = Pt(8.5)
                if entete:
                    self._ombre(cel, "D9E2EA")
                elif cl & {"ok"}:
                    self._couleur(p, "1E6B3A")
                elif cl & {"ko"}:
                    self._couleur(p, "B3301D")
                j += cs
            if entete:
                self._repeter_entete(t.rows[i])
        if largeurs:
            for j, w in enumerate(largeurs):
                for row in t.rows:
                    row.cells[j].width = Cm(w)
        cont.add_paragraph()

    @staticmethod
    def _largeurs(el, ncol):
        cols = el.findall(".//colgroup/col")
        pc = []
        for c in cols:
            m = re.search(r"width:\s*([\d.]+)%", c.get("style") or "")
            pc.append(float(m.group(1)) if m else None)
        if len(pc) != ncol or None in pc:
            return None
        tot = sum(pc) or 1
        return [LARGEUR_UTILE_CM * v / tot for v in pc]

    @staticmethod
    def _ombre(cel, hexa):
        tc = cel._tc.get_or_add_tcPr()
        sh = OxmlElement("w:shd")
        sh.set(qn("w:val"), "clear")
        sh.set(qn("w:color"), "auto")
        sh.set(qn("w:fill"), hexa)
        tc.append(sh)

    @staticmethod
    def _couleur(p, hexa):
        for r in p.runs:
            r.font.color.rgb = RGBColor.from_string(hexa)

    @staticmethod
    def _repeter_entete(row):
        trpr = row._tr.get_or_add_trPr()
        e = OxmlElement("w:tblHeader")
        e.set(qn("w:val"), "true")
        trpr.append(e)


def docx_depuis_html(source: str, titre: str = "Note de calcul") -> tuple[bytes, dict]:
    """HTML de la note → (octets .docx, statistiques). Le contenu est celui de la note, sans ajout."""
    racine = lhtml.document_fromstring(source)
    corps = racine.find("body")
    if corps is None:
        corps = racine
    cv = Convertisseur()
    cv.doc.core_properties.title = titre
    cv._enfants(corps, cv.doc, 0)
    flux = io.BytesIO()
    cv.doc.save(flux)
    st = dict(cv.stats)
    st["equations_natives"] = st["equations_natives"] == st["equations"]
    st["equations_converties"] = cv.stats["equations_natives"]
    return flux.getvalue(), st
