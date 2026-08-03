# -*- coding: utf-8 -*-
"""Risiko-Cockpit – automatischer Datenabruf & Ampelberechnung.
Läuft in GitHub Actions, erzeugt index.html. Keine API-Schlüssel nötig.
Quellen: FRED (Makro/Kredit, CSV), Stooq (Kurse, CSV). Manuelle Werte: config.json.
"""
import json, io, time, datetime as dt
import urllib.request
import pandas as pd

UA = {"User-Agent": "risiko-cockpit/1.0 (privates Monitoring-Skript)"}

def get_csv(url, tries=3, wait=5):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                text = r.read().decode("utf-8", errors="replace")
            df = pd.read_csv(io.StringIO(text))
            if df.shape[1] < 2:
                raise RuntimeError("Unerwartete Antwort: " + text[:90].replace("\n", " "))
            return df
        except Exception as e:
            last = e
            time.sleep(wait * (i + 1))
    raise last

def fred(series):
    df = get_csv(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}")
    df.columns = ["date", "v"]
    df["v"] = pd.to_numeric(df["v"], errors="coerce")
    return df.dropna().reset_index(drop=True)

def stooq(sym, days=420):
    d2 = dt.date.today(); d1 = d2 - dt.timedelta(days=days)
    url = (f"https://stooq.com/q/d/l/?s={sym}&i=d"
           f"&d1={d1:%Y%m%d}&d2={d2:%Y%m%d}")
    time.sleep(1.5)  # Stooq nicht mit Anfragen fluten
    df = get_csv(url)
    if "Date" not in df.columns:
        raise RuntimeError("Stooq lieferte keine Kursdaten (Limit/Blockade?): "
                           + ",".join(map(str, df.columns))[:90])
    df["Date"] = pd.to_datetime(df["Date"])
    return df.set_index("Date")["Close"].astype(float)

# ---------- Indikatoren ----------
def calc():
    cfg = json.load(open("config.json", encoding="utf-8"))
    out = {"stand": dt.date.today().isoformat(), "inds": [], "fehler": []}

    def add(block, name, value, y, r, dir_, note, veto=None):
        s = None
        if value is not None:
            if dir_ == "up":   s = 2 if value >= r else 1 if value >= y else 0
            else:              s = 2 if value <= r else 1 if value <= y else 0
        out["inds"].append(dict(block=block, name=name, value=value,
                                y=y, r=r, dir=dir_, note=note, score=s, veto=veto))

    # --- Kredit: HY-Spread, Niveau + 4-Wochen-Delta (FRED) ---
    try:
        hy = fred("BAMLH0A0HYM2")
        lvl = hy.v.iloc[-1] * 100
        d4w = lvl - hy.v.iloc[-21] * 100          # ~20 Handelstage
        add("Kredit & Leverage", "High-Yield-Spread (OAS), bp", round(lvl), 450, 600, "up",
            f"FRED, {hy.date.iloc[-1]}")
        add("Kredit & Leverage", "Δ HY-Spread 4 Wochen, bp", round(d4w), 60, 100, "up",
            "berechnet aus FRED-Reihe", veto=("rot", 100))
    except Exception as e:
        out["fehler"].append(f"HY-Spread: {e}")

    # --- Makro: Zinskurve 10J-3M (FRED) ---
    try:
        c = fred("T10Y3M")
        cv = c.v.iloc[-1] * 100
        add("Makro & Politik", "Zinskurve 10J−3M, bp", round(cv), 50, 0, "down",
            f"FRED, {c.date.iloc[-1]}", veto=("gelb", 0))
    except Exception as e:
        out["fehler"].append(f"Zinskurve: {e}")

    # --- Marktstruktur: Aktien/Anleihen-Korrelation (SPY vs TLT, 1J Tagesrenditen) ---
    try:
        spy, tlt = stooq("spy.us"), stooq("tlt.us")
        r_ = pd.concat([spy.pct_change(), tlt.pct_change()], axis=1).dropna().tail(252)
        sb = r_.corr().iloc[0, 1]
        add("Marktstruktur & Liquidität", "Korrelation Aktien/Anleihen", round(sb, 2),
            0.10, 0.35, "up", "SPY/TLT, 252 Handelstage, Stooq")
    except Exception as e:
        out["fehler"].append(f"SPY/TLT-Korrelation: {e}")

    # --- Marktstruktur: Ø Paarkorrelation großer Indexmitglieder ---
    try:
        tickers = ["msft.us","aapl.us","nvda.us","amzn.us","googl.us","meta.us",
                   "avgo.us","brk-b.us","jpm.us","xom.us","unh.us","pg.us"]
        rets = pd.concat({t: stooq(t).pct_change() for t in tickers}, axis=1)\
                 .dropna().tail(126)                     # ~6 Monate
        cm = rets.corr().values
        n = cm.shape[0]
        pc = (cm.sum() - n) / (n * (n - 1))
        add("Marktstruktur & Liquidität", "Ø Paarkorrelation (12 Titel)", round(pc, 2),
            0.35, 0.55, "up", "6M-Fenster, Stooq")
    except Exception as e:
        out["fehler"].append(f"Paarkorrelation: {e}")

    # --- Bewertung: Zweiteilung — SPY vs. Equal-Weight-ETF RSP, 12M-Spread ---
    try:
        spy12 = stooq("spy.us"); rsp12 = stooq("rsp.us")
        gap = (spy12.iloc[-1]/spy12.iloc[-252] - rsp12.iloc[-1]/rsp12.iloc[-252]) * 100
        add("Bewertung & Konzentration", "12M-Spread SPY vs. Equal Weight, %-Pkt.",
            round(gap, 1), 12, 25, "up", "SPY/RSP, Stooq")
    except Exception as e:
        out["fehler"].append(f"SPY/RSP-Spread: {e}")

    # --- Manuelle Werte aus config.json ---
    m = cfg.get("manuell", {})
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
        add(block, name, e.get("wert"), y, r, d,
            f"manuell, Stand {e.get('stand','n. v.')}")
    return out

# ---------- Ampeln & HTML ----------
def lamp(mean): return 3 if mean is None else 2 if mean >= 1.34 else 1 if mean >= 0.67 else 0

def render(d):
    COL = {0: "#1F7A4D", 1: "#B8860B", 2: "#B3362B", 3: "#9AA5AE"}
    LBL = {0: "GRÜN", 1: "GELB", 2: "ROT", 3: "KEINE DATEN"}
    blocks = {}
    for i in d["inds"]:
        blocks.setdefault(i["block"], []).append(i)

    vetotxt, vmax = [], 0
    for i in d["inds"]:
        if i["veto"] and i["value"] is not None:
            lv = 1 if i["veto"][0] == "gelb" else 2
            hit = (i["value"] <= i["veto"][1]) if i["dir"] == "down" else (i["value"] >= i["veto"][1])
            if hit:
                vetotxt.append(f"VETO: {i['name']} → mind. {LBL[lv]}"); vmax = max(vmax, lv)

    bl, means = [], []
    for name, inds in blocks.items():
        sc = [i["score"] for i in inds if i["score"] is not None]
        mean = sum(sc)/len(sc) if sc else None
        if mean is not None: means.append(mean)
        rows = "".join(
            f"<tr><td><span class='dot' style='background:{COL[i['score'] if i['score'] is not None else 3]}'></span></td>"
            f"<td>{i['name']}<br><small>{i['note']}</small></td>"
            f"<td class='v'>{'n. v.' if i['value'] is None else i['value']}</td></tr>"
            for i in inds)
        bl.append(f"<div class='card'><h2><span class='dot big' style='background:{COL[lamp(mean)]}'></span>"
                  f"{name} <small>{len(sc)}/{len(inds)} belegt</small></h2><table>{rows}</table></div>")

    overall = lamp(sum(means)/len(means)) if means else 3
    overall = max(overall, vmax) if overall != 3 else (vmax or 3)
    vh = "".join(f"<div class='veto'>{t}</div>" for t in vetotxt)
    eh = ("<div class='err'>Abruf-Fehler: " + " · ".join(d["fehler"]) + "</div>") if d["fehler"] else ""
    html = f"""<!doctype html><html lang='de'><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Risiko-Cockpit</title><style>
body{{font-family:-apple-system,sans-serif;background:#E7EAED;color:#182430;margin:0;padding:16px}}
.card{{background:#FBFCFD;border:1px solid #C9D1D8;margin:12px auto;max-width:640px;padding:12px 16px}}
h1{{font-size:22px;margin:4px 0}} h2{{font-size:15px;display:flex;align-items:center;gap:8px}}
h2 small{{margin-left:auto;color:#46617A;font-weight:400}}
.dot{{display:inline-block;width:11px;height:11px;border-radius:50%}}
.dot.big{{width:16px;height:16px}}
table{{width:100%;border-collapse:collapse;font-size:13.5px}}
td{{padding:6px 4px;border-top:1px solid #E2E7EB;vertical-align:top}}
td.v{{text-align:right;font-variant-numeric:tabular-nums;font-weight:600;white-space:nowrap}}
small{{color:#46617A;font-size:11px}}
.veto{{background:{COL[max(vmax,1)]};color:#fff;padding:8px 12px;font-weight:600;margin:8px auto;max-width:640px}}
.err{{color:#B3362B;font-size:12px;max-width:640px;margin:8px auto}}
.head{{max-width:640px;margin:0 auto}}
.overall{{font-size:19px;font-weight:700;display:flex;gap:10px;align-items:center;margin:10px 0}}
footer{{max-width:640px;margin:14px auto;font-size:11px;color:#46617A}}</style>
<div class='head'><h1>Risiko-Cockpit</h1>
<div class='overall'><span class='dot big' style='background:{COL[overall]}'></span>Gesamt: {LBL[overall]}
<small style='margin-left:auto'>Stand {d['stand']}</small></div></div>{vh}{eh}
{''.join(bl)}
<footer>Gleichgewichtung der belegten Indikatoren; Vetos: Zinskurve invertiert → mind. Gelb,
HY-Sprung ≥100 bp/4W → Rot. Quellen: FRED, Stooq, manuelle Konfiguration.
Kein Prognoseinstrument, keine Anlageberatung.</footer></html>"""
    open("index.html", "w", encoding="utf-8").write(html)

if __name__ == "__main__":
    render(calc())
    print("index.html erzeugt.")