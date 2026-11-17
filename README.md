# BÉNAYFACILE

**Le bureau d'études structure marocain, automatisé.**

Bénayfacile calcule vos poteaux, poutres, semelles et voiles selon le
**BAEL 91 révisées 99** et le **RPS 2000 — version 2011**, depuis votre modèle
**Autodesk Robot Structural Analysis**, et génère la **note de calcul** et le
**plan DXF** en quelques clics.

![Plan de fondation généré par Bénayfacile](docs/images/plan_fondation.png)

## Ce que BÉNAYFACILE fait pour vous

| Module | Ce que vous obtenez |
|---|---|
| **Poteau** | λ, α (BAEL B.8.4,1), Nu,lim, armatures (min constructif 4 cm²/m), ferraillage, vérification en flexion composée |
| **Vérification sismique** | F = υ·S·D·I·W/K (RPS 2000 v2011, eq. 6.1), période fondamentale, D (Tableau 5.3), répartition verticale Fn |
| **Semelles Isolées / Filantes** | A, B, H (méthode des bielles, h ≥ (A−a)/4), poinçonnement vérifié et H augmenté si besoin, ferraillage (bielles), poids |
| **Poutre** | ELU (diagramme 0,8 yu, μlim 0,392/0,372), non-fragilité, ELS (n = 15, limites A.4.5,33/34), tranchant |
| **Voiles de Contreventement** | σ max/min, armatures de rive si section partiellement comprimée, τu |
| **Synthèse de Calcul** | Note de calcul HTML/PDF A4 : page de garde, références normatives, hypothèses, calculs, **audit arithmétique ligne à ligne** |
| **Données de votre bureau** | Vos coordonnées/ICE/RC reprises dans la page de garde et le cartouche DXF |
| **Modèle Robot** | Extraction via COM (Robot ouvert) ou **mode simulation R+4** pour essayer l'outil sans Robot |

## Qualité et traçabilité

- **Aucune valeur inventée** : chaque constante normative provient des textes
  officiels (tables + articles cités, voir `referentiels/bael.json` et
  `referentiels/rps.json` avec leur `_source`).
- **Audit arithmétique automatique** : chaque ligne de la note est recalculée
  et marquée OK / `ALERTE ECART ARITHMETIQUE`.
- **Données auditées avant émission** : écart = signalé, jamais masqué.
- **100 % local** : écoute sur `127.0.0.1` uniquement — vos données ne sortent
  pas du poste.

## Démarrage rapide

### Sous Windows (poste BET, sans Python)

Lancer `Benayfacile.exe` (voir `build_exe.bat` pour la construction) :
les 5 services démarrent dans un seul processus, le navigateur s'ouvre sur
`http://127.0.0.1:8090`.

### Depuis les sources (développeur)

```bat
pip install -r requirements.txt
run_services.bat          :: lance Robot(8001) Engine(8002) DXF(8003) Rapport(8004) Gateway(8090)
python -m pytest tests/   :: 15 tests
stop_services.bat         :: arrêt propre
```

### Docker (le service Robot y tourne en mode simulation)

```sh
docker compose up --build
```

## Architecture

```
bnayfacile_app.py      → lanceur (1 processus, 5 serveurs threads)
launcher/               → AppPaths (Value Object), DataBootstrapper (Strategy),
                          ManagedServer (Adapter), BenayfacileApp (Facade)
services/               → robot_service / engine_service (BAEL+RPS) / dxf_service / report_service
gateway/                → passerelle + tableau de bord web (8 modules)
referentiels/           → bael.json, rps.json (tables officielles) + bureau.json (vos données)
docs/ARCHITECTURE_LANCEUR.md → UML complet, design patterns, cycle de vie
```

### Diagramme de composants

```mermaid
flowchart LR
    U[Ingénieur BET<br/>navigateur] -->|http://127.0.0.1:8090| GW
    subgraph EXE["Benayfacile.exe — 1 processus"]
        L[BenayfacileApp<br/>Facade] --> GW[Passerelle :8090<br/>tableau de bord + proxy]
        L --> R[robot_service :8001]
        L --> E[engine_service :8002]
        L --> D[dxf_service :8003]
        L --> N[report_service :8004]
        GW --> R & E & D & N
    end
    E -. "lit" .-> REF[(Benayfacile_donnees/<br/>referentiels/)]
    D -. "écrit" .-> OUT[(Benayfacile_donnees/<br/>output/)]
    N -. "écrit" .-> OUT
    GW -. "lit / écrit bureau.json" .-> REF
```

### Diagramme de classes UML

```mermaid
classDiagram
    direction LR
    class AppPaths {
        <<ValueObject, frozen>>
        +bundle: Path
        +data: Path
        +referentiels: Path
        +output: Path
        +detect()$ AppPaths
    }
    class DataBootstrapper {
        +paths: AppPaths
        +politiques: Dict~str, CopyPolicy~
        +par_defaut(paths)$ DataBootstrapper
        +preparer() list~str~
    }
    class CopyPolicy {
        <<Strategy>>
        +__call__(dest_existe: bool) bool
    }
    class TOUJOURS_RAFRAICHIR {
        <<ConcreteStrategy>>
    }
    class SI_ABSENT {
        <<ConcreteStrategy>>
    }
    class ServiceSpec {
        <<ValueObject, frozen>>
        +nom: str
        +module: str
        +port: int
    }
    class SERVICE_REGISTRY {
        <<Registry>>
        tuple~ServiceSpec~
    }
    class ManagedServer {
        <<Adapter>>
        -_server: uvicorn.Server
        -_thread: Thread
        +start()
        +wait_ready(timeout_s) bool
        +vivant: bool
        +stop()
    }
    class uvicorn_Server {
        <<Adaptee>>
        +run()
        +started: bool
        +should_exit: bool
    }
    class BenayfacileApp {
        <<Facade>>
        +paths: AppPaths
        +notifier: Notifier
        +serveurs: List~ManagedServer~
        +url: str
        +demarrer(ouvrir_navigateur)
        +attendre()
        +arreter()
    }
    class Notifier {
        <<Observer callback>>
        +__call__(message: str)
    }

    CopyPolicy <|.. TOUJOURS_RAFRAICHIR
    CopyPolicy <|.. SI_ABSENT
    DataBootstrapper --> AppPaths
    DataBootstrapper o-- CopyPolicy
    SERVICE_REGISTRY o-- ServiceSpec
    ManagedServer --> ServiceSpec
    ManagedServer *-- uvicorn_Server : adapte
    BenayfacileApp --> AppPaths
    BenayfacileApp ..> DataBootstrapper : utilise
    BenayfacileApp ..> SERVICE_REGISTRY : parcourt
    BenayfacileApp *-- ManagedServer : 5
    BenayfacileApp --> Notifier : notifie
```

### Séquence de démarrage (UML)

```mermaid
sequenceDiagram
    actor U as Ingénieur
    participant M as main()
    participant F as BenayfacileApp
    participant P as AppPaths
    participant B as DataBootstrapper
    participant S as ManagedServer (×5)
    participant W as Navigateur

    U->>M: double-clic Benayfacile.exe
    M->>P: detect()
    P-->>M: bundle=_MEIPASS, data=…/Benayfacile_donnees
    M->>F: demarrer()
    F->>F: os.environ["BNAY_DATA"] = data
    Note over F: AVANT tout import des services,<br/>qui lisent BNAY_DATA à l'import
    F->>B: par_defaut(paths).preparer()
    B-->>F: bael/rps copiés, bureau.json conservé
    F->>F: garde : 8001-8004 + 8090 libres ?
    alt un port est occupé
        F-->>M: DemarrageImpossible
        M-->>U: message clair + « Entrée pour fermer »
    else tous libres
        loop pour chaque ServiceSpec du registre
            F->>S: start()
            F->>S: wait_ready(30 s)
            S-->>F: started = True
        end
        F->>W: webbrowser.open(127.0.0.1:8090)
        F->>F: attendre() jusqu'à Ctrl+C / fermeture
        F->>S: stop() en ordre inverse
    end
```

### Design patterns (lanceur)

Chaque pattern règle un problème concret, pas la forme :

| Pattern | Élément | Problème réglé |
|---|---|---|
| **Value Object** | `AppPaths`, `ServiceSpec` | Où sont les fichiers ? Réponse unique, immuable, testée une fois |
| **Factory Method** | `AppPaths.detect()` | Choisit la résolution selon le mode d'exécution sans disperser `sys.frozen` |
| **Strategy** | `CopyPolicy` (`TOUJOURS_RAFRAICHIR` / `SI_ABSENT`) | bael/rps = version livrée fait foi ; bureau.json = jamais écrasé |
| **Registry** | `SERVICE_REGISTRY` | Table nom/module/port unique : garde des ports, démarrage, arrêt ; passerelle en dernier |
| **Adapter** | `ManagedServer` | `uvicorn.Server.run()` bloquant → `start()` / `wait_ready()` / `stop()` |
| **Facade** | `BenayfacileApp` | 6 étapes strictes cachées derrière `demarrer()` / `attendre()` / `arreter()` |
| **Observer (léger)** | `Notifier` | Démarrage indépendant de la console (future icône barre des tâches) |
| **Guard Clause** | vérification des ports | Ports vérifiés avant tout démarrage ; sinon aucun serveur lancé |
| **API Gateway + Proxy** | `gateway/app.py` | Point d'entrée unique `:8090`, relaie `/api/{service}/*` vers les microservices |

Au premier lancement, `Benayfacile_donnees/` est créé à côté de l'exe :
`referentiels/bael.json` et `referentiels/rps.json` (rafraîchis à chaque
lancement — version livrée fait foi), `referentiels/bureau.json` (vos données,
créé une fois, jamais écrasé), `output/` (notes HTML et plans DXF).

Pilotage Robot : `pywin32` embarqué dans `Benayfacile.exe`. Sans Robot
installé, le mode simulation R+4 (zone 3, site S2, classe II, K = 2,0) permet
de tester toute la chaîne.
## Normes et sources

- **BAEL 91 révisées 99** — Règles techniques de conception et de calcul des
  ouvrages en béton armé (Fascicule 62, titre Iᵉʳ du CCTG, DTU P18-702).
- **RPS 2000 — version 2011** — Règlement de Construction Parasismique
  (Ministère de l'Habitat, Royaume du Maroc).

En cas de divergence entre cet outil et les textes officiels, **les textes
officiels font foi**. Les approximations BET usuelles (méthode des bielles
pour les semelles, armatures minimales des voiles) sont indiquées comme
telles dans la note de calcul et restent sous la responsabilité de
l'ingénieur chargé du projet.

## Auteur

Youssef-AMARZOU — Bénayfacile, bureau d'études structure (Maroc).
https://github.com/Youssef-AMARZOU

© 2026 Bénayfacile. Tous droits réservés. Le code est publié à titre de
présentation commerciale ; il n'est pas librement réutilisable.
