# Ontwerp: IEVR Commander-Mode Bot

**Datum:** 2026-06-21
**Status:** Goedgekeurd ontwerp (klaar voor implementatieplan)
**Locatie:** `C:\claude\IEVR`

## Doel

Een Python-bot die op deze Windows-pc draait en volledig zelfstandig potjes
speelt in *Inazuma Eleven: Victory Road* via de ingebouwde **Commander Mode**.
De gebruiker start de game tot het hoofdmenu; daarna neemt de bot alles over en
loopt eindeloos door tot de gebruiker hem handmatig stopt.

De bot speelt zélf geen voetbal — de game-AI doet dat in Commander Mode. De bot
is in de kern een **scherm-herkenner + input-automaat** die door alle schermen
navigeert en de loop eindeloos herhaalt.

## Vastgestelde keuzes (uit brainstorm)

| Onderwerp | Keuze |
|-----------|-------|
| Platform | PC (Steam), zelfde machine als de bot |
| Hoofddoel | Beide, gefaseerd: eerst betrouwbaar grinden, daarna slim spelen |
| Modus | PvE én Online Ranked ondersteunen via config; **start met PvE** |
| Autonomie | Start vanaf game al open in hoofdmenu; bot loopt eindeloos tot handmatige stop |
| Input | Virtuele Xbox-controller (`vgamepad` + ViGEmBus), met toetsenbord-fallback |
| GUI | PySide6 / Qt desktop-bedieningspaneel (dark theme) |

## Achtergrond: wat Commander Mode is

Commander Mode is een ingebouwde gamefunctie. Eenmaal aangezet (via prompt
linksonder tijdens een potje) neemt de game-AI over: beweging, passes, dribbels,
schoten, Focus Battle-keuzes en het inzetten van Tension/Special Moves.

De speler (= straks de bot) moet alleen nog:
- Door vaste schermen heen klikken: kickoff, rust, doelpunt-schermen, eindscherm,
  beloningen/level-up, en opnieuw in de wachtrij gaan.
- **Optioneel** ingrijpen op cruciale momenten — de game-AI verliest vaak Focus
  Battles en scoort slecht, zelfs met een sterker team. Handmatige controle kan
  op elk moment kort overgenomen worden (basis voor fase 2).

## Architectuur (modules)

- **`capture`** — snelle screenshots van het game-venster (`mss`).
- **`vision`** — herkent de huidige staat via OpenCV *template matching* tegen
  een bibliotheek referentie-screenshots. (Optioneel later: Tesseract OCR voor
  score/tekst.)
- **`controller`** — abstractie over input: virtuele Xbox-controller
  (`vgamepad` + ViGEmBus), met toetsenbord-fallback (`pydirectinput`).
- **`states`** — toestanden (enum) + per toestand een handler die bepaalt wat
  ingedrukt wordt.
- **`orchestrator`** — de hoofdloop: capture → herken staat → voer handler uit →
  herhaal.
- **`watchdog`** — zelfherstel: detecteert vastlopen/onbekende schermen en grijpt
  in.
- **`config`** — laadt een profiel (PvE/Ranked): paden naar templates, timings,
  knoppen-mapping, stopcondities, feature-toggles (bv. fase-2 intervention).
- **`logger`** — logt naar bestand + console, maakt screenshot bij fouten.
- **`tools/capture_templates`** — hulpscript om tijdens setup referentiebeelden
  vast te leggen.
- **`gui`** — PySide6/Qt-bedieningspaneel dat de bot aanstuurt (zie GUI-sectie).

## GUI (PySide6 / Qt)

Een desktop-bedieningspaneel met dark theme dat de bot bestuurt zonder de
terminal. De bot draait in een aparte worker-thread (`QThread`), zodat de GUI
responsief blijft; communicatie via Qt-signalen (staat-updates, logregels,
preview-frames).

Functies:
- **Start / Stop / Pauze** van de bot.
- **Profielkeuze** (PvE / Ranked) en **dry-run-schakelaar**.
- **Live status:** huidige staat, aantal gespeelde potjes, uptime, laatste actie.
- **Live log** (gekleurd op niveau) + knop "open logmap".
- **Screenshot-preview** van wat de bot ziet, met de herkende staat erop.
- **Setup-tab:** knop om `capture_templates` te starten en de knoppen-mapping te
  configureren.

De GUI is een dunne laag bovenop dezelfde `orchestrator`; de bot blijft ook
zonder GUI bruikbaar via `main.py` (headless), zodat logica en UI gescheiden
blijven en los testbaar zijn.

## Toestandsmachine (kernloop)

```
HOOFDMENU
  → start potje / wachtrij
LADEN / MATCHMAKING
  → wachten
KICKOFF
  → Commander Mode aanzetten
IN_WEDSTRIJD (alleen monitoren; game-AI speelt)
  → onderschept pop-ups:
       RUST              → doorklikken
       DOELPUNT/CUTSCENE → skippen
       EINDE             → doorklikken
       BELONINGEN/LEVELUP→ doorklikken
NA-WEDSTRIJD
  → opnieuw potje  ──► loop terug naar start
```

Fase-2 voegt een tussenstaat toe: `FOCUS_BATTLE` → bot pakt kort de controle om
te winnen (config-toggle).

## Datastroom

Elke ~0,3–0,5 s: frame pakken → `vision` bepaalt de staat → `orchestrator` zoekt
de bijbehorende handler → handler stuurt input via `controller`. De `watchdog`
houdt bij wanneer de staat voor het laatst veranderde.

## Zelfherstel (cruciaal — onbewaakt draaien)

- **Onbekend scherm** te lang → herstelroutine: cancel/terug indrukken,
  screenshot + log.
- **Vast in dezelfde staat** te lang → input "porren", daarna escaleren.
- **Disconnect-/foutdialogen** → herkend via templates → wegklikken en opnieuw in
  de wachtrij.
- **Exponentiële backoff** bij herhaalde fouten i.p.v. blind doorrammen; alles
  wordt gelogd.

## Fasering

- **Fase 1 (werkend):** volledige loop; Commander-AI speelt, bot navigeert alle
  schermen. Levert de werkende grinder op. Start met PvE-profiel.
- **Fase 2 (slim, optioneel via config):** bot pakt zelf kort de controle tijdens
  Focus Battles / schoten om die te winnen. Aan/uit per profiel.

## Projectstructuur

```
IEVR/
  ievr_bot/
    __init__.py
    capture.py        # screenshots van game-venster
    vision.py         # staat-detectie via template matching
    controller.py     # input-abstractie (vgamepad + keyboard fallback)
    states.py         # staat-enum + handlers
    orchestrator.py   # hoofdloop
    watchdog.py       # zelfherstel
    config.py         # profiel-laden
    logger.py
  gui/
    __init__.py
    app.py            # PySide6 hoofdvenster
    worker.py         # QThread-wrapper rond de orchestrator
    widgets.py        # status-, log- en previewpanelen
  templates/
    pve/              # referentie-screenshots PvE
    ranked/           # referentie-screenshots Ranked
  profiles/
    pve.yaml
    ranked.yaml
  tools/
    capture_templates.py
  tests/
  logs/
  main.py               # headless entrypoint
  run_gui.py            # GUI-entrypoint
  requirements.txt
  README.md
```

## Teststrategie

- **Unit-tests** voor `vision` tegen opgeslagen screenshots (golden images) —
  testbaar zónder dat de game draait.
- **Transitietests** voor de toestandsmachine met een nep-detector.
- **Dry-run-modus:** staten detecteren en loggen zónder input te sturen (veilig
  observeren).
- Handmatige integratietest met de echte game.

## Eenmalige setup (begeleid)

1. Python + dependencies installeren (`mss`, `opencv-python`, `numpy`,
   `vgamepad`, optioneel `pydirectinput`, `pytesseract`).
2. ViGEmBus-driver installeren (voor virtuele controller).
3. Game op vaste resolutie/venstermodus zetten — template matching is
   resolutie-gevoelig.
4. Referentie-screenshots vastleggen met `tools/capture_templates.py`.
5. Knoppen-mapping en profiel configureren.

## Kanttekening (risico)

Het automatiseren van een **online** modus (Ranked) kan tegen de
gebruiksvoorwaarden van de game ingaan en accountrisico geven. Voor PvE/offline
is dat risico veel kleiner. Daarom: **standaard met PvE beginnen**; Ranked alleen
bewust inschakelen.

## Niet in scope (YAGNI, voorlopig)

- Koude start (game zelf opstarten vanuit Steam) — gebruiker opent de game tot
  het menu.
- Auto-stop op tijd/aantal — bot loopt tot handmatige stop (kan later toegevoegd).
- Machine-learning/objectdetectie — template matching volstaat.
- OCR — alleen nodig als latere features score-uitlezing vereisen.
