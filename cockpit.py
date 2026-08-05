
Claude hat die Antwort abgeschlossen
Welcher Anbieter für kann github nicht selber push-Nachrichten ans iphone schicken?

Doch – kann es, und das ist tatsächlich der eleganteste Weg für dich:

Die GitHub-App selbst sendet Push-Nachrichten aufs iPhone. Sie ist installiert, angemeldet, kostenlos, kein Fremdanbieter, kein Secret, nichts mitlesbar. Der Trick besteht darin, das Cockpit so umzubauen, dass es GitHubs eigene Benachrichtigungswege nutzt:

Variante A – Issue bei Alarm (mein Favorit). Bei Wechsel auf Rot oder Veto-Auslösung legt der Workflow automatisch ein Issue in deinem Repository an, z. B. „🔴 Veto: HY-Spread +112 bp in 4 Wochen". Da du der Eigentümer bist, schickt GitHub dir dafür eine Push-Nachricht auf iPhone (und eine E-Mail). Nebeneffekt: Du bekommst nebenbei ein dauerhaftes Alarm-Protokoll mit Datum – jedes Issue ist ein historischer Eintrag, den du abhaken kannst.

Variante B – Fehler-Push. GitHub pusht standardmäßig bei fehlgeschlagenen Workflow-Läufen. Man könnte den Workflow bei Rot absichtlich scheitern lassen – funktioniert, ist aber unsauber, weil man dann echte Fehler nicht mehr von Alarmen unterscheiden kann. Würde ich nicht machen.

Zur Aktivierung (einmalig): In der GitHub-App unter Profil → Einstellungen prüfen, dass Push-Nachrichten erlaubt sind; in den Web-Einstellungen unter „Notifications" sollte für „Participating" der Kanal Mobile/E-Mail aktiv sein.

Damit entfällt ntfy.sh samt Mitlese-Risiko komplett – ein Anbieter weniger in der Kette, und das passt besser zu deiner Sicherheitslinie.

Ergänzend zur Vollständigkeit: Rein technisch könnte man auch Apple Kurzbefehle die Cockpit-Seite abfragen lassen, aber das wäre wieder auf iOS-Hintergrundausführung angewiesen – genau das Problem, weshalb wir bei GitHub Actions gelandet sind.

Soll ich Variante A einbauen (Alarm-Issue bei Rot/Veto, mit Schutz gegen tägliche Wiederholung desselben Alarms)? Dann baue ich sie zusammen mit Historie, Diagramm, Delta-Anzeige und Pflege-Wecker in einem Rutsch.


excerpt_from_previous_claude_message.txt
1 Zeile

txt

ja bitte, und immer schön an die Sicherheit denken ,-)


Orchestrierte Workflow-Konfiguration mit Sicherheitsmaßnahmen und Token-Management
Orchestrierte Workflow-Konfiguration mit Sicherheitsmaßnahmen und Token-Management
Alle fünf Funktionen sind eingebaut und mit simulierten Daten getestet (inkl. erzwungenem Alarmfall):

Historie – history.csv wächst täglich um eine Zeile (Datum, Gesamtampel, Blockampeln, alle Indikatorwerte), ein Lauf pro Tag ersetzt den vorherigen, 400 Einträge Rollfenster. Die Datei liegt im Repository und ist jederzeit für eigene Auswertungen herunterladbar.

Kurvendiagramm – unter den Blöcken, letzte 90 Einträge, farbige Zonenbänder für Grün/Gelb/Rot. Bewusst als reines SVG ohne Diagrammbibliothek: kein externes Skript im Cockpit, nichts nachzuladen – das hält die Seite auch sicherheitsseitig sauber.

Delta-Anzeige – unter jedem Wert erscheint ▲/▼ mit der Veränderung zum Vorlauf.

Pflege-Wecker – gelber Kasten oben, sobald ein manueller Wert seine Altersgrenze reißt, mit Quellenangabe. Die Grenzen stehen jetzt in der config (max_alter_tage) und sind pro Indikator einstellbar: SKEW 14 Tage, CAPE 20, Margin Debt/GPR 45, Zollsatz 60, Hyperscaler-FCF 100, Top-10 120.

Alarm-Push – bei Rot oder Veto legt der Lauf ein Issue mit Label „cockpit-alarm" an; die GitHub-App pusht es aufs iPhone. Wiederholungsschutz über eine Zustandssignatur: gleicher Zustand → kein neues Issue, erst bei Änderung (Test bestätigt: zweiter Lauf meldet „unverändert").

Zur Sicherheit, wie gewünscht: Kein Fremddienst und kein zusätzliches Secret – der Push läuft über GitHubs eigenen Lauf-Token, der automatisch existiert, nur für dieses Repository gilt und nach jedem Lauf verfällt. Die Berechtigungen im Workflow sind auf das Nötigste beschränkt (contents + issues). Neu ist außerdem eine Redaction-Funktion: Sollte ein API-Schlüssel je in einer Fehlermeldung auftauchen, wird er vor Log und HTML-Ausgabe durch *** ersetzt. Alle Texte werden HTML-escaped, Fremddaten ausschließlich als Zahlen geparst – nichts aus einer Antwort wird ausgeführt oder als Anweisung behandelt.

Einspielen: cockpit.py, config.json und .github/workflows/cockpit.yml durch die neuen Versionen ersetzen, dann „Run workflow". Beim ersten Lauf steht beim Diagramm noch der Hinweis, dass es ab dem zweiten Eintrag erscheint – ab morgen zeichnet es dann.


Cockpit
PY 

Cockpit workflow
YML 

Config
Code · JSON 





Claude ist eine KI und kann Fehler machen. Bitte überprüfe die Antworten.
Cockpit · PY
# -*- coding: utf-8 -*-
"""Risiko-Cockpit – automatischer Datenabruf, Ampeln, Historie, Alarm-Issues.
 
Laeuft in GitHub Actions, erzeugt index.html und schreibt history.csv fort.
Quellen: FRED-API (Makro/Kredit), Twelve Data (Kurse), config.json (manuelle Werte).
Sicherheit: Schluessel ausschliesslich aus Umgebungsvariablen (GitHub Secrets),
keine Ausgabe von Schluesseln, alle Fremddaten werden nur als Zahl geparst,
alle Texte vor der HTML-Ausgabe escaped. Keine Ausfuehrung von Fremdinhalten.
"""
import json, io, os, re, time, html, datetime as dt
import urllib.request
import pandas as pd
 
UA = {"User-Agent": "risiko-cockpit/1.0 (privates Monitoring-Skript)"}
HIST = "history.csv"
STATE = "alarm_state.json"
 
# ---------------- Abruf-Helfer ----------------
def _redact(msg):
    """Schluessel aus Fehlermeldungen entfernen, damit sie nie im Log/HTML landen."""
    s = str(msg)
    for k in ("FRED_API_KEY", "TD_API_KEY", "GITHUB_TOKEN"):
        v = os.environ.get(k)
        if v:
            s = s.replace(v, "***")
    return re.sub(r"(api_?key=)[^&\s]+", r"\1***", s, flags=re.I)
 
def get_json(url, tries=3, wait=5):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            last = e
            time.sleep(wait * (i + 1))
    raise RuntimeError(_redact(last))
 
def fred(series):
    key = os.environ["FRED_API_KEY"]
    j = get_json("https://api.stlouisfed.org/fred/series/observations"
                 f"?series_id={series}&api_key={key}&file_type=json"
                 "&observation_start=2024-01-01")
    rows = [(o["date"], o["value"]) for o in j["observations"] if o["value"] != "."]
    df = pd.DataFrame(rows, columns=["date", "v"])
    df["v"] = pd.to_numeric(df["v"], errors="coerce")
    return df.dropna().reset_index(drop=True)
 
def kurs(sym):
    """Tagesschlusskurse via Twelve Data. 'spy.us' -> 'SPY'."""
    ticker = sym.split(".")[0].upper().replace("-", ".")
    key = os.environ["TD_API_KEY"]
    time.sleep(8.5)                      # Gratis-Limit: 8 Abrufe/Minute
    j = get_json("https://api.twelvedata.com/time_series"
                 f"?symbol={ticker}&interval=1day&outputsize=300&apikey={key}")
    if "values" not in j:
        raise RuntimeError(f"TwelveData {ticker}: " + _redact(j.get("message", j))[:90])
    df = pd.DataFrame(j["values"])
    df["Date"] = pd.to_datetime(df["datetime"])
    return df.set_index("Date")["close"].astype(float).sort_index()
 
# ---------------- Konfig-Pflege-Wecker ----------------
def alter_tage(stand):
    """Alter eines manuellen Wertes in Tagen; None wenn nicht auswertbar."""
    if not stand:
        return None
    m = re.match(r"(\d{4})-(\d{2})(?:-(\d{2}))?", str(stand))
    if not m:
        return None
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3) or 1)
    try:
        return (dt.date.today() - dt.date(y, mo, d)).days
    except ValueError:
        return None
 
# ---------------- Indikatoren ----------------
def calc():
    cfg = json.load(open("config.json", encoding="utf-8"))
    out = {"stand": dt.date.today().isoformat(), "inds": [], "fehler": [], "pflege": []}
 
    def add(block, name, value, y, r, dir_, note, veto=None, key=None):
        s = None
        if value is not None:
            s = (2 if value >= r else 1 if value >= y else 0) if dir_ == "up" \
                else (2 if value <= r else 1 if value <= y else 0)
        out["inds"].append(dict(block=block, name=name, value=value, key=key or name,
                                y=y, r=r, dir=dir_, note=note, score=s, veto=veto))
 
    # --- Kredit: HY-Spread, Niveau + 4-Wochen-Delta (FRED) ---
    try:
        hy = fred("BAMLH0A0HYM2")
        lvl = hy.v.iloc[-1] * 100
        d4w = lvl - hy.v.iloc[-21] * 100
        add("Kredit & Leverage", "High-Yield-Spread (OAS), bp", round(lvl), 450, 600, "up",
            f"FRED-API, {hy.date.iloc[-1]}", key="hy")
        add("Kredit & Leverage", "Δ HY-Spread 4 Wochen, bp", round(d4w), 60, 100, "up",
            "berechnet aus FRED-Reihe", veto=("rot", 100), key="hy_d4w")
    except Exception as e:
        out["fehler"].append(f"HY-Spread: {_redact(e)}")
 
    # --- Makro: Zinskurve 10J-3M (FRED) ---
    try:
        c = fred("T10Y3M")
        add("Makro & Politik", "Zinskurve 10J−3M, bp", round(c.v.iloc[-1] * 100), 50, 0, "down",
            f"FRED-API, {c.date.iloc[-1]}", veto=("gelb", 0), key="curve")
    except Exception as e:
        out["fehler"].append(f"Zinskurve: {_redact(e)}")
 
    # --- Marktstruktur: Aktien/Anleihen-Korrelation ---
    try:
        spy, tlt = kurs("spy.us"), kurs("tlt.us")
        r_ = pd.concat([spy.pct_change(), tlt.pct_change()], axis=1).dropna().tail(252)
        add("Marktstruktur & Liquidität", "Korrelation Aktien/Anleihen",
            round(r_.corr().iloc[0, 1], 2), 0.10, 0.35, "up",
            "SPY/TLT, 252 Handelstage, Twelve Data", key="corr_sb")
    except Exception as e:
        out["fehler"].append(f"SPY/TLT-Korrelation: {_redact(e)}")
 
    # --- Marktstruktur: Ø Paarkorrelation ---
    try:
        tickers = ["msft.us", "aapl.us", "nvda.us", "amzn.us",
                   "googl.us", "jpm.us", "xom.us", "pg.us"]
        rets = pd.concat({t: kurs(t).pct_change() for t in tickers}, axis=1).dropna().tail(126)
        cm = rets.corr().values
        n = cm.shape[0]
        add("Marktstruktur & Liquidität", "Ø Paarkorrelation (8 Titel)",
            round((cm.sum() - n) / (n * (n - 1)), 2), 0.35, 0.55, "up",
            "6M-Fenster, Twelve Data", key="corr_pair")
    except Exception as e:
        out["fehler"].append(f"Paarkorrelation: {_redact(e)}")
 
    # --- Bewertung: SPY vs. Equal Weight (RSP), 12M ---
    try:
        s12, r12 = kurs("spy.us"), kurs("rsp.us")
        gap = (s12.iloc[-1] / s12.iloc[-252] - r12.iloc[-1] / r12.iloc[-252]) * 100
        add("Bewertung & Konzentration", "12M-Spread SPY vs. Equal Weight, %-Pkt.",
            round(gap, 1), 12, 25, "up", "SPY/RSP, Twelve Data", key="ew_gap")
    except Exception as e:
        out["fehler"].append(f"SPY/RSP-Spread: {_redact(e)}")
 
    # --- Manuelle Werte + Pflege-Wecker ---
    m = cfg.get("manuell", {})
    maxalter = cfg.get("max_alter_tage", {})
    man = [
        ("Bewertung & Konzentration", "Shiller-KGV S&P 500", "cape", 28, 34, "up"),
        ("Bewertung & Konzentration", "Top-10-Gewicht S&P 500, %", "top10", 30, 36, "up"),
        ("Kredit & Leverage", "Margin Debt Δ12M, %", "margin", 15, 30, "up"),
        ("Kredit & Leverage", "Hyperscaler-FCF nach Capex, Mrd$", "hs_fcf", 20, 0, "down"),
        ("Marktstruktur & Liquidität", "CBOE SKEW", "skew", 140, 155, "up"),
        ("Makro & Politik", "Effektiver US-Zollsatz, %", "tariff", 10, 20, "up"),
        ("Makro & Politik", "GPR-Perzentil", "gpr", 70, 90, "up"),
    ]
    for block, name, key, y, r, d in man:
        e = m.get(key) or {}
        stand = e.get("stand", "n. v.")
        tage = alter_tage(stand)
        grenze = maxalter.get(key, 45)
        note = f"manuell, Stand {stand}"
        if tage is not None and tage > grenze:
            note += f" · ⏰ {tage} Tage alt"
            out["pflege"].append(f"{name}: {tage} Tage alt (Grenze {grenze}) – {e.get('quelle','Quelle s. config')}")
        elif tage is None and e.get("wert") is None:
            out["pflege"].append(f"{name}: kein Wert hinterlegt – {e.get('quelle','Quelle s. config')}")
        add(block, name, e.get("wert"), y, r, d, note, key=key)
    return out
 
# ---------------- Ampeln ----------------
def lamp(mean):
    return 3 if mean is None else 2 if mean >= 1.34 else 1 if mean >= 0.67 else 0
 
def bewerte(d):
    blocks = {}
    for i in d["inds"]:
        blocks.setdefault(i["block"], []).append(i)
    binfo, means = {}, []
    for name, inds in blocks.items():
        sc = [i["score"] for i in inds if i["score"] is not None]
        mean = sum(sc) / len(sc) if sc else None
        if mean is not None:
            means.append(mean)
        binfo[name] = dict(inds=inds, mean=mean, lamp=lamp(mean), n=len(sc), total=len(inds))
    vetos, vmax = [], 0
    for i in d["inds"]:
        if i["veto"] and i["value"] is not None:
            lv = 1 if i["veto"][0] == "gelb" else 2
            hit = (i["value"] <= i["veto"][1]) if i["dir"] == "down" else (i["value"] >= i["veto"][1])
            if hit:
                vetos.append(f"{i['name']} = {i['value']} → mindestens {'GELB' if lv==1 else 'ROT'}")
                vmax = max(vmax, lv)
    overall = lamp(sum(means) / len(means)) if means else 3
    overall = max(overall, vmax) if overall != 3 else (vmax or 3)
    return binfo, vetos, overall
 
# ---------------- Historie ----------------
def historie_fortschreiben(d, binfo, overall):
    row = {"datum": d["stand"], "gesamt": overall}
    for name, b in binfo.items():
        row["b_" + name.split(" ")[0].lower()] = b["lamp"]
    for i in d["inds"]:
        if i["value"] is not None:
            row["i_" + i["key"]] = i["value"]
    try:
        hist = pd.read_csv(HIST)
        hist = hist[hist["datum"] != row["datum"]]          # heutigen Lauf ersetzen
        hist = pd.concat([hist, pd.DataFrame([row])], ignore_index=True)
    except Exception:
        hist = pd.DataFrame([row])
    hist = hist.sort_values("datum").tail(400)
    hist.to_csv(HIST, index=False)
    return hist
 
def deltas(hist, d):
    """Veraenderung je Indikator gegenueber dem vorherigen Eintrag."""
    out = {}
    if len(hist) < 2:
        return out
    prev = hist.iloc[-2]
    for i in d["inds"]:
        col = "i_" + i["key"]
        if i["value"] is None or col not in hist.columns:
            continue
        pv = prev.get(col)
        if pd.isna(pv):
            continue
        diff = round(float(i["value"]) - float(pv), 2)
        if diff != 0:
            out[i["key"]] = (diff, str(prev["datum"]))
    return out
 
# ---------------- Diagramm (reines SVG, keine Fremdbibliothek) ----------------
def chart(hist):
    h = hist.tail(90)
    if len(h) < 2:
        return "<div class='card'><small>Verlaufsdiagramm erscheint ab dem zweiten Lauf.</small></div>"
    W, H, PAD = 620, 150, 26
    n = len(h)
    xs = [PAD + (W - 2 * PAD) * k / (n - 1) for k in range(n)]
    def ypos(v):   # 0 (gruen) unten, 2 (rot) oben
        return H - PAD - (H - 2 * PAD) * (float(v) / 2.0)
    pts = " ".join(f"{x:.1f},{ypos(v):.1f}" for x, v in zip(xs, h["gesamt"]))
    dots = "".join(
        f"<circle cx='{x:.1f}' cy='{ypos(v):.1f}' r='2.6' fill='{ {0:'#1F7A4D',1:'#B8860B',2:'#B3362B'}[int(v)] }'/>"
        for x, v in zip(xs, h["gesamt"]))
    bands = (f"<rect x='{PAD}' y='{ypos(2)}' width='{W-2*PAD}' height='{ypos(1.34)-ypos(2):.1f}' fill='#B3362B' opacity='.07'/>"
             f"<rect x='{PAD}' y='{ypos(1.34)}' width='{W-2*PAD}' height='{ypos(0.67)-ypos(1.34):.1f}' fill='#B8860B' opacity='.07'/>"
             f"<rect x='{PAD}' y='{ypos(0.67)}' width='{W-2*PAD}' height='{ypos(0)-ypos(0.67):.1f}' fill='#1F7A4D' opacity='.07'/>")
    lab = (f"<text x='4' y='{ypos(2)+4:.1f}' font-size='9' fill='#46617A'>ROT</text>"
           f"<text x='4' y='{ypos(1)+4:.1f}' font-size='9' fill='#46617A'>GELB</text>"
           f"<text x='4' y='{ypos(0)+4:.1f}' font-size='9' fill='#46617A'>GRÜN</text>"
           f"<text x='{PAD}' y='{H-6}' font-size='9' fill='#46617A'>{html.escape(str(h['datum'].iloc[0]))}</text>"
           f"<text x='{W-PAD}' y='{H-6}' font-size='9' fill='#46617A' text-anchor='end'>{html.escape(str(h['datum'].iloc[-1]))}</text>")
    return (f"<div class='card'><h2>Verlauf Gesamtampel <small>{n} Einträge</small></h2>"
            f"<svg viewBox='0 0 {W} {H}' width='100%' role='img' aria-label='Verlauf der Gesamtampel'>"
            f"{bands}<polyline points='{pts}' fill='none' stroke='#46617A' stroke-width='1.6'/>{dots}{lab}</svg></div>")
 
# ---------------- Alarm-Issue (GitHub-eigener Push) ----------------
def alarm(overall, vetos, d):
    """Legt bei NEUEM Rot-Zustand oder NEUEM Veto ein Issue an -> Push via GitHub-App.
    Kein Fremddienst, kein zusaetzliches Secret: nutzt den Lauf-Token."""
    sig = json.dumps({"overall": overall, "vetos": sorted(vetos)}, ensure_ascii=False)
    try:
        alt = json.load(open(STATE, encoding="utf-8")).get("sig")
    except Exception:
        alt = None
    if sig == alt:
        return "unveraendert"
    json.dump({"sig": sig, "datum": d["stand"]}, open(STATE, "w", encoding="utf-8"),
              ensure_ascii=False)
    if overall != 2 and not vetos:
        return "kein Alarm"
    token, repo = os.environ.get("GITHUB_TOKEN"), os.environ.get("GITHUB_REPOSITORY")
    if not (token and repo):
        return "kein Token"
    titel = ("🔴 Cockpit ROT" if overall == 2 else "⚠️ Cockpit-Veto") + f" – {d['stand']}"
    zeilen = [f"**Gesamtampel:** {['GRÜN','GELB','ROT','KEINE DATEN'][overall]}", ""]
    if vetos:
        zeilen += ["**Ausgelöste Vetos:**"] + [f"- {v}" for v in vetos] + [""]
    zeilen += ["**Auslösende Indikatoren (rot):**"]
    zeilen += [f"- {i['name']}: {i['value']}" for i in d["inds"] if i["score"] == 2] or ["- (keine)"]
    zeilen += ["", "Automatisch erzeugt vom Risiko-Cockpit. Kein Prognoseinstrument, keine Anlageberatung."]
    body = json.dumps({"title": titel, "body": "\n".join(zeilen),
                       "labels": ["cockpit-alarm"]}).encode("utf-8")
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}/issues", data=body,
                                 headers={**UA, "Authorization": f"Bearer {token}",
                                          "Accept": "application/vnd.github+json",
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return f"Issue angelegt ({r.status})"
    except Exception as e:
        return "Issue fehlgeschlagen: " + _redact(e)[:80]
 
# ---------------- HTML ----------------
COL = {0: "#1F7A4D", 1: "#B8860B", 2: "#B3362B", 3: "#9AA5AE"}
LBL = {0: "GRÜN", 1: "GELB", 2: "ROT", 3: "KEINE DATEN"}
 
def render(d, binfo, vetos, overall, hist, dlt):
    E = html.escape
    karten = []
    for name, b in binfo.items():
        rows = []
        for i in b["inds"]:
            s = i["score"] if i["score"] is not None else 3
            dtxt = ""
            if i["key"] in dlt:
                diff, seit = dlt[i["key"]]
                pfeil = "▲" if diff > 0 else "▼"
                dtxt = f"<span class='d'>{pfeil} {abs(diff):g}</span>"
            rows.append(
                f"<tr><td><span class='dot' style='background:{COL[s]}'></span></td>"
                f"<td>{E(i['name'])}<br><small>{E(i['note'])}</small></td>"
                f"<td class='v'>{'n. v.' if i['value'] is None else E(str(i['value']))}{dtxt}</td></tr>")
        karten.append(
            f"<div class='card'><h2><span class='dot big' style='background:{COL[b['lamp']]}'></span>"
            f"{E(name)} <small>{b['n']}/{b['total']} belegt</small></h2>"
            f"<table>{''.join(rows)}</table></div>")
 
    vh = "".join(f"<div class='veto'>VETO · {E(v)}</div>" for v in vetos)
    ph = ("<div class='pflege'><b>⏰ Pflege fällig:</b><ul>"
          + "".join(f"<li>{E(p)}</li>" for p in d["pflege"]) + "</ul></div>") if d["pflege"] else ""
    eh = ("<div class='err'>Abruf-Fehler: " + E(" · ".join(d["fehler"])) + "</div>") if d["fehler"] else ""
 
    html_out = f"""<!doctype html><html lang='de'><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Risiko-Cockpit</title><style>
body{{font-family:-apple-system,sans-serif;background:#E7EAED;color:#182430;margin:0;padding:16px}}
.card{{background:#FBFCFD;border:1px solid #C9D1D8;margin:12px auto;max-width:640px;padding:12px 16px}}
h1{{font-size:22px;margin:4px 0}} h2{{font-size:15px;display:flex;align-items:center;gap:8px;margin:2px 0 8px}}
h2 small{{margin-left:auto;color:#46617A;font-weight:400}}
.dot{{display:inline-block;width:11px;height:11px;border-radius:50%}}
.dot.big{{width:16px;height:16px}}
table{{width:100%;border-collapse:collapse;font-size:13.5px}}
td{{padding:6px 4px;border-top:1px solid #E2E7EB;vertical-align:top}}
td.v{{text-align:right;font-variant-numeric:tabular-nums;font-weight:600;white-space:nowrap}}
.d{{display:block;font-size:10.5px;font-weight:500;color:#46617A}}
small{{color:#46617A;font-size:11px}}
.veto{{background:{COL[2]};color:#fff;padding:8px 12px;font-weight:600;margin:8px auto;max-width:640px}}
.pflege{{background:#FFF8E1;border:1px solid #E8D9A0;color:#6B5312;font-size:12px;
 max-width:640px;margin:8px auto;padding:8px 12px}}
.pflege ul{{margin:6px 0 0;padding-left:18px}}
.err{{color:#B3362B;font-size:12px;max-width:640px;margin:8px auto}}
.head{{max-width:640px;margin:0 auto}}
.overall{{font-size:19px;font-weight:700;display:flex;gap:10px;align-items:center;margin:10px 0}}
footer{{max-width:640px;margin:14px auto;font-size:11px;color:#46617A}}</style>
<div class='head'><h1>Risiko-Cockpit</h1>
<div class='overall'><span class='dot big' style='background:{COL[overall]}'></span>Gesamt: {LBL[overall]}
<small style='margin-left:auto'>Stand {E(d['stand'])}</small></div></div>{vh}{ph}{eh}
{''.join(karten)}
{chart(hist)}
<footer>Gleichgewichtung der belegten Indikatoren; Vetos: Zinskurve invertiert → mind. Gelb,
HY-Sprung ≥100 bp/4W → Rot. Δ-Werte zeigen die Veränderung zum vorherigen Lauf.
Quellen: FRED-API, Twelve Data, manuelle Konfiguration (config.json).
Kein Prognoseinstrument, keine Anlageberatung.</footer></html>"""
    open("index.html", "w", encoding="utf-8").write(html_out)
 
if __name__ == "__main__":
    d = calc()
    binfo, vetos, overall = bewerte(d)
    hist = historie_fortschreiben(d, binfo, overall)
    render(d, binfo, vetos, overall, hist, deltas(hist, d))
    print("index.html erzeugt. Alarm:", alarm(overall, vetos, d))
 







