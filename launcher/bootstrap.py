"""Pattern : Strategy — politique de copie des référentiels au démarrage.

Les fichiers normatifs (bael.json, rps.json) doivent TOUJOURS refléter la
version livrée avec l'exécutable (traçabilité : les constantes viennent des
textes officiels, pas d'une copie locale modifiée). Les données du bureau
(bureau.json) appartiennent à l'utilisateur : on ne les écrase JAMAIS.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from typing import Callable, Dict

from .paths import AppPaths

# Une stratégie = une fonction (source existe, destination existe) -> copier ?
CopyPolicy = Callable[[bool], bool]

TOUJOURS_RAFRAICHIR: CopyPolicy = lambda dest_existe: True
SI_ABSENT: CopyPolicy = lambda dest_existe: not dest_existe


@dataclass
class DataBootstrapper:
    paths: AppPaths
    politiques: Dict[str, CopyPolicy]

    @classmethod
    def par_defaut(cls, paths: AppPaths) -> "DataBootstrapper":
        return cls(paths, {
            "bael.json": TOUJOURS_RAFRAICHIR,   # normatif : version livrée fait foi
            "rps.json": TOUJOURS_RAFRAICHIR,    # normatif : version livrée fait foi
            "bureau.json": SI_ABSENT,           # données utilisateur : jamais écrasées
        })

    def preparer(self) -> list[str]:
        """Crée les dossiers et applique les politiques. Renvoie le journal."""
        journal = []
        self.paths.referentiels.mkdir(parents=True, exist_ok=True)
        self.paths.output.mkdir(parents=True, exist_ok=True)
        src_dir = self.paths.bundle / "referentiels"
        if src_dir.resolve() == self.paths.referentiels.resolve():
            return ["mode sources : référentiels utilisés sur place"]
        for nom, politique in self.politiques.items():
            src, dst = src_dir / nom, self.paths.referentiels / nom
            if not src.exists():
                journal.append(f"ABSENT DU PAQUET : {nom}")
                continue
            if politique(dst.exists()):
                shutil.copy2(src, dst)
                journal.append(f"copié : {nom}")
            else:
                journal.append(f"conservé : {nom}")
        return journal
