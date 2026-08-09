# Quellen für die manuell gepflegten Indikatoren

Diese sieben Werte holt das Skript **nicht** automatisch – sie werden in `config.json`
unter `manuell` eingetragen. Nach dem Eintragen immer auch `stand` aktualisieren
(Format `JJJJ-MM-TT`), sonst rechnet der Pflege-Wecker falsch.
Kein Wert auffindbar? → `"wert": null` setzen. Nie schätzen.

---

## 1. Shiller-KGV S&P 500 — `cape`
- **Wo:** multpl.com → Seite "Shiller PE Ratio"
- **Turnus:** monatlich (Wecker: 20 Tage)
- **Was eintragen:** aktueller Wert, z. B. 40.9
- **Schwellen:** ab 28 gelb, ab 34 rot
- ⚠️ multpl.com ist ein Aggregator; Alternative zur Gegenprüfung: Robert Shillers
  Originaldaten auf der Yale-Seite (Excel, aktualisiert seltener).

## 2. Top-10-Gewicht S&P 500, % — `top10`
- **Wo:** ssga.com → Fondsseite SPDR S&P 500 ETF (SPY) → "Holdings" / Factsheet;
  dort die Gewichte der zehn größten Positionen addieren
- **Turnus:** quartalsweise (Wecker: 120 Tage)
- **Schwellen:** ab 30 gelb, ab 36 rot
- ⚠️ Quellen weichen ab: FactSet-Erhebungen nannten für Ende 2025 rund 40,7 %,
  die SPY-Holdings im April 2026 rund 35,6 % (unterschiedliche Stichtage und
  Abgrenzungen). Immer notieren, welche Quelle verwendet wurde.

## 3. Margin Debt Δ12M, % — `margin`
- **Wo:** finra.org → "Margin Statistics" (Monatsreihe "Debit Balances in
  Customers' Securities Margin Accounts")
- **Turnus:** monatlich, Veröffentlichung ~3–4 Wochen verzögert (Wecker: 45 Tage)
- **Was eintragen:** prozentuale Veränderung gegenüber dem Vorjahresmonat, selbst
  berechnen: (aktueller Monat / gleicher Monat Vorjahr − 1) × 100
- **Schwellen:** ab 15 gelb, ab 30 rot

## 4. Hyperscaler-FCF nach Capex, Mrd $ — `hs_fcf`
- **Wo:** Investor-Relations-Seiten von Microsoft, Alphabet, Amazon, Meta
  (Quartalsbericht / Earnings Release, Cashflow-Rechnung)
- **Turnus:** quartalsweise, jeweils Ende Januar / April / Juli / Oktober (Wecker: 100 Tage)
- **Was eintragen:** Summe aus (operativer Cashflow − Investitionsausgaben) der vier
  Konzerne für das Quartal, in Mrd. USD
- **Schwellen:** unter 20 gelb, unter 0 rot (Richtung: kleiner = schlechter)
- 💡 Die PDFs/Berichte können im Claude-Chat hochgeladen werden, dann wird der Wert
  daraus extrahiert.

## 5. CBOE SKEW — `skew`
- **Wo:** cboe.com → "Indices" → SKEW Index Dashboard (Tageswert)
- **Alternativen für Historie/Download:** Yahoo Finance (Symbol `^SKEW`, Reiter
  "Historical Data") oder Barchart (`$SKEW`, Price History)
- **Turnus:** alle ein bis zwei Wochen (Wecker: 14 Tage)
- **Schwellen:** ab 140 gelb, ab 155 rot
- 💡 Kandidat für spätere Automatisierung – die Reihe ist maschinenlesbar abrufbar.

## 6. Effektiver US-Zollsatz, % — `tariff`
- **Wo:** Penn Wharton Budget Model (budgetmodel.wharton.upenn.edu) — realisierte
  Zolleinnahmen im Verhältnis zu Importen; alternativ The Budget Lab at Yale
  (budgetlab.yale.edu) — Schätzung des effektiven Satzes
- **Turnus:** quartalsweise bzw. bei Politikwechseln (Wecker: 60 Tage)
- **Schwellen:** ab 10 gelb, ab 20 rot
- ⚠️ Die beiden Quellen weichen systematisch ab: PWBM misst realisiert und rückwärts
  gewandt (Mai 2026: 7,2 %), Yale schätzt vorwärts gewandt (rund 9,7 % nach Auslauf
  der §122-Zölle). Im Feld `quelle` festhalten, welche verwendet wurde.

## 7. GPR-Perzentil — `gpr`
- **Wo:** matteoiacoviello.com/gpr.htm (Geopolitical Risk Index, Caldara/Iacoviello)
  → Datendatei herunterladen
- **Turnus:** monatlich (Wecker: 45 Tage)
- **Was eintragen:** nicht den Indexwert, sondern das **Perzentil** – also den Rang des
  aktuellen Monatswerts innerhalb der historischen Verteilung (0–100). Beispiel: 78
  bedeutet, der Wert liegt höher als in 78 % aller bisherigen Monate.
- **Schwellen:** ab 70 gelb, ab 90 rot
- 💡 Die heruntergeladene Datei kann im Claude-Chat hochgeladen werden, dann wird das
  Perzentil daraus berechnet.

---

## Automatisch abgerufene Indikatoren (nur zur Information, keine Pflege nötig)

| Indikator | Quelle |
|---|---|
| High-Yield-Spread (OAS) + Δ 4 Wochen | FRED-API, Reihe `BAMLH0A0HYM2` |
| Zinskurve 10J − 3M | FRED-API, Reihe `T10Y3M` |
| Korrelation Aktien/Anleihen | Twelve Data, SPY und TLT, 252 Handelstage |
| Ø Paarkorrelation (8 Titel) | Twelve Data, 8 große Indexmitglieder, 6-Monats-Fenster |
| 12M-Spread SPY vs. Equal Weight | Twelve Data, SPY und RSP |

Zugangsschlüssel liegen als GitHub Secrets (`FRED_API_KEY`, `TD_API_KEY`) und stehen
nicht im Code.

---

*Stand dieser Liste: August 2026. Adressen und Veröffentlichungsrhythmen können sich
ändern – bei Abweichung hier korrigieren.*
