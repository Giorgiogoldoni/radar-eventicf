"""
scraper.py — Radar Eventi CF
Scrapa siti noti per eventi formativi CF italiani.
Conserva SEMPRE gli eventi con fonte=="fisso".
"""

import json, re, time, traceback
from datetime import datetime, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "it-IT,it;q=0.9",
}

MESI = {"gennaio":1,"febbraio":2,"marzo":3,"aprile":4,"maggio":5,"giugno":6,
        "luglio":7,"agosto":8,"settembre":9,"ottobre":10,"novembre":11,"dicembre":12}

def get_html(url, timeout=15):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"  [WARN] {url}: {e}")
        return ""

def parse_date(text):
    text = str(text).lower()
    m = re.search(r'(\d{1,2})\s+(' + '|'.join(MESI.keys()) + r')\s+(202\d)', text)
    if m:
        return f"{m.group(3)}-{MESI[m.group(2)]:02d}-{int(m.group(1)):02d}"
    m = re.search(r'(202\d)-(\d{2})-(\d{2})', text)
    if m: return m.group(0)
    m = re.search(r'(\d{1,2})[/\.](\d{1,2})[/\.](202\d)', text)
    if m: return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    return None

def make_ev(titolo, org, data, tipo, citta, gratuito, crediti, crediti_ore, desc, url, fonte):
    return {
        "titolo": titolo[:100], "org": org, "data": data,
        "tipo": tipo, "citta": citta, "gratuito": gratuito,
        "crediti": crediti, "crediti_ore": crediti_ore,
        "desc": desc[:150], "url": url, "fonte": fonte,
        "ricorrente": False, "aggiornato": str(datetime.now().date())
    }

# ── SCRAPERS ──────────────────────────────────────────────────────────────────

def scrape_acepi():
    events = []
    url = "https://acepi.it/it/node/48822"
    html = get_html(url)
    if not html: return events
    soup = BeautifulSoup(html, "lxml")
    testo = soup.get_text()
    righe = [r.strip() for r in testo.split("\n") if r.strip()]
    for i, riga in enumerate(righe):
        data = parse_date(riga)
        if data:
            titolo = righe[i-1] if i > 0 and len(righe[i-1]) > 5 else "Corso ACEPI"
            titolo = titolo[:80]
            events.append(make_ev(titolo, "ACEPI", data, "webinar", "Online",
                True, True, 2, "Formazione gratuita ACEPI con crediti EFPA/CFA.", url, "acepi.it"))
    print(f"  [ACEPI] {len(events)} eventi")
    return events

def scrape_investing():
    events = []
    for citta, u in [("Milano","https://www.investingmilano.it"),("Roma","https://www.investingroma.it")]:
        html = get_html(u)
        if not html:
            # fallback date note
            data = "2026-06-05" if citta=="Milano" else "2026-10-15"
        else:
            data = parse_date(BeautifulSoup(html,"lxml").get_text()) or ("2026-06-05" if citta=="Milano" else "2026-10-15")
        events.append(make_ev(f"Investing {citta} 2026", f"Investing {citta}", data,
            "presenza", citta, True, False, 0,
            f"Il più grande evento gratuito su trading e investimenti a {citta}.", u, u.replace("https://www.","")))
    print(f"  [Investing] {len(events)} eventi")
    return events

def scrape_consultique():
    events = []
    url = "https://www.consultique.com/it/eventi/"
    html = get_html(url)
    if not html: return events
    soup = BeautifulSoup(html, "lxml")
    items = soup.select("article, .evento, .event, li")
    for item in items[:20]:
        titolo_el = item.select_one("h2,h3,h4,a,.title")
        if not titolo_el: continue
        titolo = titolo_el.get_text(strip=True)
        data = parse_date(item.get_text())
        link_el = item.select_one("a[href]")
        link = link_el["href"] if link_el else url
        if not link.startswith("http"): link = "https://www.consultique.com" + link
        if data and len(titolo) > 5:
            events.append(make_ev(titolo, "Consultique", data, "webinar", "Online",
                True, True, 1, "Webinar Consultique su consulenza finanziaria indipendente.", link, "consultique.com"))
    print(f"  [Consultique] {len(events)} eventi")
    return events

def scrape_fundspeople():
    events = []
    url = "https://fundspeople.com/it/evento/"
    html = get_html(url)
    if not html: return events
    soup = BeautifulSoup(html, "lxml")
    cards = soup.select("article, .event-item, [class*='event']")
    for card in cards[:20]:
        titolo_el = card.select_one("h2,h3,h4,.title,a")
        data_el = card.select_one("time,[class*='date']")
        link_el = card.select_one("a[href]")
        if not titolo_el: continue
        titolo = titolo_el.get_text(strip=True)
        data = parse_date(data_el.get_text() if data_el else card.get_text())
        link = link_el["href"] if link_el else url
        if not link.startswith("http"): link = "https://fundspeople.com" + link
        if data and len(titolo) > 5:
            events.append(make_ev(titolo, "FundsPeople", data, "webinar", "Online",
                True, False, 0, "Evento FundsPeople Italia.", link, "fundspeople.com/it"))
    print(f"  [FundsPeople] {len(events)} eventi")
    return events

def scrape_bnpparibas():
    events = []
    url = "https://investimenti.bnpparibas.it/news-e-formazione/calendario-eventi-webinar-investimenti-e-trading/"
    html = get_html(url)
    if not html: return events
    soup = BeautifulSoup(html, "lxml")
    items = soup.select("[class*='event'], article, .card, li")
    for item in items[:20]:
        titolo_el = item.select_one("h2,h3,h4,.title,a")
        if not titolo_el: continue
        titolo = titolo_el.get_text(strip=True)
        data = parse_date(item.get_text())
        link_el = item.select_one("a[href]")
        link = link_el["href"] if link_el else url
        if not link.startswith("http"): link = "https://investimenti.bnpparibas.it" + link
        if data and len(titolo) > 5:
            events.append(make_ev(titolo, "BNP Paribas", data, "webinar", "Online",
                True, False, 0, "Webinar BNP Paribas su certificates e trading.", link, "bnpparibas.it"))
    print(f"  [BNP Paribas] {len(events)} eventi")
    return events

def scrape_consob():
    events = []
    url = "https://www.consob.it/web/area-pubblica/seminari-e-convegni"
    html = get_html(url)
    if not html: return events
    soup = BeautifulSoup(html, "lxml")
    testo = soup.get_text()
    data = parse_date(testo)
    if data:
        events.append(make_ev("CONSOB Incontro annuale mercato finanziario", "CONSOB",
            data, "presenza", "Milano", True, False, 0,
            "Incontro annuale CONSOB. Streaming gratuito su YouTube.", url, "consob.it"))
    print(f"  [CONSOB] {len(events)} eventi")
    return events

def scrape_amundi():
    events = []
    url = "https://www.amundi.com/ita_advisor"
    html = get_html(url)
    if not html: return events
    soup = BeautifulSoup(html, "lxml")
    items = soup.select("[class*='event'],[class*='webinar'],article,.card")
    for item in items[:10]:
        titolo_el = item.select_one("h2,h3,h4,[class*='title'],a")
        if not titolo_el: continue
        titolo = titolo_el.get_text(strip=True)
        data = parse_date(item.get_text())
        link_el = item.select_one("a[href]")
        link = link_el["href"] if link_el else url
        if not link.startswith("http"): link = "https://www.amundi.com" + link
        if data and len(titolo) > 5:
            events.append(make_ev(titolo, "Amundi", data, "webinar", "Online",
                True, False, 0, "Webinar Amundi per advisor italiani.", link, "amundi.com"))
    print(f"  [Amundi] {len(events)} eventi")
    return events

# ── MAIN ──────────────────────────────────────────────────────────────────────

SCRAPERS = [
    scrape_acepi,
    scrape_investing,
    scrape_consultique,
    scrape_fundspeople,
    scrape_bnpparibas,
    scrape_consob,
    scrape_amundi,
]

def main():
    p = Path("eventi.json")

    # Carica eventi esistenti — CONSERVA SEMPRE I FISSI
    fissi = []
    scraped_old = []
    if p.exists():
        try:
            existing = json.loads(p.read_text()).get("eventi", [])
            fissi = [e for e in existing if e.get("fonte") == "fisso"]
            scraped_old = [e for e in existing if e.get("fonte") != "fisso"]
            print(f"[INFO] Eventi fissi conservati: {len(fissi)}")
        except Exception as e:
            print(f"[WARN] Errore lettura eventi.json: {e}")

    # Scraping
    nuovi = []
    for fn in SCRAPERS:
        try:
            nuovi.extend(fn())
            time.sleep(1)
        except Exception as e:
            print(f"[ERROR] {fn.__name__}: {e}")

    print(f"[INFO] Nuovi eventi trovati dallo scraping: {len(nuovi)}")

    # Filtra per periodo (oggi - 30gg → +8 mesi)
    oggi = datetime.now().date()
    limite = oggi + timedelta(days=240)
    nuovi_filtrati = []
    for ev in nuovi:
        try:
            d = datetime.strptime(ev["data"], "%Y-%m-%d").date()
            if d >= oggi - timedelta(days=30) and d <= limite:
                nuovi_filtrati.append(ev)
        except:
            pass

    # Unisci: fissi + nuovi (deduplicati per titolo+data)
    combined = fissi + nuovi_filtrati
    seen = set()
    final = []
    for ev in combined:
        key = (ev["titolo"][:30].lower().strip(), ev["data"])
        if key not in seen:
            seen.add(key)
            final.append(ev)

    final.sort(key=lambda x: x["data"])

    output = {
        "aggiornato": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "totale": len(final),
        "errori": [],
        "eventi": final
    }

    p.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"\n✅ eventi.json: {len(fissi)} fissi + {len(nuovi_filtrati)} nuovi = {len(final)} totali")

if __name__ == "__main__":
    main()


# ── SCRAPERS ETF (aggiunti) ────────────────────────────────────────────────────

def scrape_directa_summit():
    events = []
    url = "https://www.directa.it/directa-summit-2026"
    html = get_html(url)
    if not html: return events
    soup = BeautifulSoup(html, "lxml")
    testo = soup.get_text()
    data = parse_date(testo) or "2026-06-18"
    events.append(make_ev(
        "Directa Summit 2026", "Directa SIM", data, "presenza", "Milano",
        True, False, 0,
        "Il più grande evento gratuito per investitori italiani. iShares, Xtrackers, Vanguard, Amundi, L&G. 3.000 persone.",
        url, "directa.it"
    ))
    print(f"  [Directa Summit] {len(events)} eventi")
    return events

def scrape_vanguard():
    events = []
    url = "https://www.it.vanguard/professional/eventi"
    html = get_html(url)
    if not html: return events
    soup = BeautifulSoup(html, "lxml")
    items = soup.select("[class*='event'], article, .card, li")
    for item in items[:10]:
        titolo_el = item.select_one("h2,h3,h4,a,.title")
        if not titolo_el: continue
        titolo = titolo_el.get_text(strip=True)
        data = parse_date(item.get_text())
        link_el = item.select_one("a[href]")
        link = link_el["href"] if link_el else url
        if not link.startswith("http"): link = "https://www.it.vanguard" + link
        if data and len(titolo) > 5:
            events.append(make_ev(titolo, "Vanguard", data, "webinar", "Online",
                True, False, 0, "Webinar Vanguard per investitori professionali.", link, "it.vanguard/professional/eventi"))
    print(f"  [Vanguard] {len(events)} eventi")
    return events

def scrape_wisdomtree():
    events = []
    url = "https://www.wisdomtree.eu/it-it/events"
    html = get_html(url)
    if not html: return events
    soup = BeautifulSoup(html, "lxml")
    items = soup.select("[class*='event'], article, .card")
    for item in items[:10]:
        titolo_el = item.select_one("h2,h3,h4,a")
        if not titolo_el: continue
        titolo = titolo_el.get_text(strip=True)
        data = parse_date(item.get_text())
        link_el = item.select_one("a[href]")
        link = link_el["href"] if link_el else url
        if not link.startswith("http"): link = "https://www.wisdomtree.eu" + link
        if data and len(titolo) > 5:
            events.append(make_ev(titolo, "WisdomTree", data, "webinar", "Online",
                True, False, 0, "Webinar WisdomTree su ETC, oro e asset reali.", link, "wisdomtree.eu"))
    print(f"  [WisdomTree] {len(events)} eventi")
    return events

def scrape_vaneck():
    events = []
    url = "https://www.vaneck.com/it/it/events/"
    html = get_html(url)
    if not html: return events
    soup = BeautifulSoup(html, "lxml")
    items = soup.select("[class*='event'], article, .card")
    for item in items[:10]:
        titolo_el = item.select_one("h2,h3,h4,a")
        if not titolo_el: continue
        titolo = titolo_el.get_text(strip=True)
        data = parse_date(item.get_text())
        link_el = item.select_one("a[href]")
        link = link_el["href"] if link_el else url
        if not link.startswith("http"): link = "https://www.vaneck.com" + link
        if data and len(titolo) > 5:
            events.append(make_ev(titolo, "VanEck", data, "webinar", "Online",
                True, False, 0, "Webinar VanEck su ETF tematici e moat investing.", link, "vaneck.com/it"))
    print(f"  [VanEck] {len(events)} eventi")
    return events

# Aggiungi i nuovi scrapers ETF alla lista principale
SCRAPERS.extend([scrape_directa_summit, scrape_vanguard, scrape_wisdomtree, scrape_vaneck])
