"""
scraper.py — Radar Eventi CF
Aggiorna eventi.json con eventi formativi per consulenti finanziari italiani.
Usa Playwright per siti JS-heavy, requests+BS4 per siti statici.
"""

import json, re, time, traceback
from datetime import datetime, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# ── Utilità ──────────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

def get_html(url: str, timeout=15) -> str:
    """Scarica HTML con requests."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"[WARN] requests fallito per {url}: {e}")
        return ""

def get_html_js(url: str, wait=3000) -> str:
    """Scarica HTML dopo rendering JS con Playwright."""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=30000)
            page.wait_for_timeout(wait)
            html = page.content()
            browser.close()
            return html
    except Exception as e:
        print(f"[WARN] Playwright fallito per {url}: {e}")
        return ""

def make_event(titolo, org, data, tipo, citta, gratuito, crediti, crediti_ore, desc, url, fonte, ricorrente=False):
    return {
        "titolo": titolo,
        "org": org,
        "data": data,
        "tipo": tipo,
        "citta": citta,
        "gratuito": gratuito,
        "crediti": crediti,
        "crediti_ore": crediti_ore,
        "desc": desc,
        "url": url,
        "fonte": fonte,
        "ricorrente": ricorrente,
        "aggiornato": datetime.now().strftime("%Y-%m-%d")
    }

def parse_italian_date(text: str):
    """Prova a estrarre una data da testo italiano."""
    mesi = {"gennaio":1,"febbraio":2,"marzo":3,"aprile":4,"maggio":5,"giugno":6,
            "luglio":7,"agosto":8,"settembre":9,"ottobre":10,"novembre":11,"dicembre":12}
    text = text.lower().strip()
    # Formato: "5 giugno 2026" o "05/06/2026" o "2026-06-05"
    m = re.search(r'(\d{1,2})\s+(' + '|'.join(mesi.keys()) + r')\s+(\d{4})', text)
    if m:
        return f"{m.group(3)}-{mesi[m.group(2)]:02d}-{int(m.group(1)):02d}"
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})', text)
    if m:
        return m.group(0)
    m = re.search(r'(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})', text)
    if m:
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    return None

# ── Scrapers ──────────────────────────────────────────────────────────────────

def scrape_fundspeople():
    """FundsPeople Italia — eventi e webinar."""
    events = []
    url = "https://fundspeople.com/it/eventos/"
    html = get_html(url)
    if not html:
        html = get_html_js(url)
    soup = BeautifulSoup(html, "lxml")
    
    # FundsPeople usa card con classe event o articolo
    cards = soup.select("article, .event-card, .event-item, [class*='event']")
    for card in cards[:30]:
        titolo = card.select_one("h2, h3, h4, .title, [class*='title']")
        data_el = card.select_one("time, [class*='date'], [class*='data']")
        link_el = card.select_one("a[href]")
        if not titolo:
            continue
        titolo_txt = titolo.get_text(strip=True)
        data_txt = data_el.get_text(strip=True) if data_el else ""
        data = parse_italian_date(data_txt) or parse_italian_date(card.get_text())
        link = link_el["href"] if link_el else url
        if not link.startswith("http"):
            link = "https://fundspeople.com" + link
        if data and titolo_txt:
            events.append(make_event(
                titolo=titolo_txt, org="FundsPeople", data=data,
                tipo="webinar", citta="Online", gratuito=True,
                crediti=False, crediti_ore=0,
                desc=f"Evento FundsPeople Italia.", url=link, fonte="fundspeople.com/it/eventos/"
            ))
    print(f"[FundsPeople] {len(events)} eventi trovati")
    return events


def scrape_anasf():
    """ANASF — seminari e ConsulenTia."""
    events = []
    url = "https://anasf.it/seminari"
    html = get_html(url)
    if not html:
        html = get_html_js(url)
    soup = BeautifulSoup(html, "lxml")
    
    items = soup.select(".views-row, article, .event, li[class*='event'], .node")
    for item in items[:20]:
        titolo = item.select_one("h2, h3, h4, .title, a")
        data_el = item.select_one("time, [class*='date'], .field-date")
        link_el = item.select_one("a[href]")
        if not titolo:
            continue
        titolo_txt = titolo.get_text(strip=True)
        data_txt = data_el.get_text(strip=True) if data_el else ""
        data = parse_italian_date(data_txt) or parse_italian_date(item.get_text())
        link = link_el["href"] if link_el else url
        if link.startswith("/"):
            link = "https://anasf.it" + link
        if data and titolo_txt and len(titolo_txt) > 5:
            events.append(make_event(
                titolo=titolo_txt, org="ANASF", data=data,
                tipo="presenza", citta="Varie città", gratuito=True,
                crediti=True, crediti_ore=4,
                desc="Seminario ANASF con crediti EFPA.", url=link, fonte="anasf.it/seminari"
            ))
    print(f"[ANASF] {len(events)} eventi trovati")
    return events


def scrape_acepi():
    """ACEPI — formazione gratuita certificates."""
    events = []
    url = "https://acepi.it/it/node/48822"
    html = get_html(url)
    if not html:
        html = get_html_js(url)
    soup = BeautifulSoup(html, "lxml")
    
    # Cerca date nel testo della pagina
    testo = soup.get_text()
    righe = [r.strip() for r in testo.split("\n") if r.strip()]
    
    for i, riga in enumerate(righe):
        data = parse_italian_date(riga)
        if data:
            titolo = righe[i-1] if i > 0 else "Corso ACEPI"
            titolo = titolo[:80] if len(titolo) > 5 else "Corso ACEPI — Certificates"
            events.append(make_event(
                titolo=titolo, org="ACEPI", data=data,
                tipo="webinar", citta="Online", gratuito=True,
                crediti=True, crediti_ore=2,
                desc="Formazione gratuita ACEPI con crediti EFPA/CFA su certificates e prodotti strutturati.",
                url=url, fonte="acepi.it"
            ))
    print(f"[ACEPI] {len(events)} eventi trovati")
    return events


def scrape_investing_milano():
    """Investing Milano — evento annuale gratuito trading."""
    events = []
    urls = [
        "https://www.investingmilano.it",
        "https://www.investingroma.it",
    ]
    for url in urls:
        html = get_html_js(url, wait=4000)
        if not html:
            continue
        soup = BeautifulSoup(html, "lxml")
        testo = soup.get_text()
        data = parse_italian_date(testo)
        
        # Estrai città dal dominio
        citta = "Milano" if "milano" in url else "Roma"
        titolo = f"Investing {citta} 2026"
        
        if data:
            events.append(make_event(
                titolo=titolo, org=f"Investing {citta}",
                data=data, tipo="presenza", citta=citta,
                gratuito=True, crediti=False, crediti_ore=0,
                desc=f"Il più grande evento gratuito su trading e investimenti a {citta}.",
                url=url, fonte=url.replace("https://www.", ""), ricorrente=True
            ))
        else:
            # Fallback con data nota
            fallback_data = "2026-06-05" if citta == "Milano" else "2026-10-01"
            events.append(make_event(
                titolo=titolo, org=f"Investing {citta}",
                data=fallback_data, tipo="presenza", citta=citta,
                gratuito=True, crediti=False, crediti_ore=0,
                desc=f"Il più grande evento gratuito su trading e investimenti a {citta}.",
                url=url, fonte=url.replace("https://www.", ""), ricorrente=True
            ))
    print(f"[Investing] {len(events)} eventi trovati")
    return events


def scrape_salone_risparmio():
    """Salone del Risparmio."""
    events = []
    url = "https://www.salonedelrisparmio.com"
    html = get_html_js(url, wait=3000)
    soup = BeautifulSoup(html, "lxml")
    testo = soup.get_text()
    data = parse_italian_date(testo)
    if not data:
        data = "2027-04-08"  # Salone si tiene tipicamente ad aprile
    events.append(make_event(
        titolo="Salone del Risparmio 2027", org="Assogestioni",
        data=data, tipo="presenza", citta="Milano",
        gratuito=True, crediti=True, crediti_ore=10,
        desc="Il principale evento italiano del risparmio gestito. Centinaia di seminari gratuiti accreditati EFPA.",
        url=url, fonte="salonedelrisparmio.com", ricorrente=True
    ))
    print(f"[Salone] 1 evento trovato")
    return events


def scrape_fee_only_summit():
    """Fee-Only Summit — evento gratuito CF indipendenti."""
    events = []
    url = "https://www.feeonlysummit.com"
    html = get_html_js(url, wait=3000)
    soup = BeautifulSoup(html, "lxml")
    testo = soup.get_text()
    data = parse_italian_date(testo)
    if not data:
        data = "2026-06-20"
    events.append(make_event(
        titolo="Fee-Only Summit 2026", org="Consultique",
        data=data, tipo="presenza", citta="Verona",
        gratuito=True, crediti=True, crediti_ore=6,
        desc="Il più grande evento gratuito per CF indipendenti in Italia. 2.000+ partecipanti.",
        url=url, fonte="feeonlysummit.com", ricorrente=True
    ))
    print(f"[Fee-Only] 1 evento trovato")
    return events


def scrape_efpa():
    """EFPA Italia — formazione e certificazioni."""
    events = []
    url = "https://www.efpa-italia.it/formazione/"
    html = get_html(url)
    if not html:
        html = get_html_js(url)
    soup = BeautifulSoup(html, "lxml")
    
    items = soup.select("article, .corso, .evento, tr, li")
    for item in items[:20]:
        titolo = item.select_one("h2, h3, h4, td, a, .title")
        data_el = item.select_one("time, [class*='date'], td")
        if not titolo:
            continue
        titolo_txt = titolo.get_text(strip=True)
        data = parse_italian_date(data_el.get_text() if data_el else item.get_text())
        link_el = item.select_one("a[href]")
        link = link_el["href"] if link_el else url
        if link.startswith("/"):
            link = "https://www.efpa-italia.it" + link
        if data and len(titolo_txt) > 5:
            events.append(make_event(
                titolo=titolo_txt, org="EFPA Italia",
                data=data, tipo="webinar", citta="Online",
                gratuito=False, crediti=True, crediti_ore=0,
                desc="Formazione EFPA Italia per certificazioni EFA, EFP, EIP, ESG Advisor.",
                url=link, fonte="efpa-italia.it/formazione/"
            ))
    print(f"[EFPA] {len(events)} eventi trovati")
    return events


def scrape_advisoronline():
    """AdvisorOnline — eventi CF italiani."""
    events = []
    url = "https://www.advisoronline.it/consulenti-finanziari/eventi.action"
    html = get_html(url)
    if not html:
        html = get_html_js(url)
    soup = BeautifulSoup(html, "lxml")
    
    items = soup.select("article, .event, .news-item, li.event")
    for item in items[:20]:
        titolo = item.select_one("h2, h3, .title, a")
        data_el = item.select_one("time, [class*='date'], .data")
        link_el = item.select_one("a[href]")
        if not titolo:
            continue
        titolo_txt = titolo.get_text(strip=True)
        data = parse_italian_date(data_el.get_text() if data_el else item.get_text())
        link = link_el["href"] if link_el else url
        if link.startswith("/"):
            link = "https://www.advisoronline.it" + link
        if data and len(titolo_txt) > 5:
            events.append(make_event(
                titolo=titolo_txt, org="AdvisorOnline",
                data=data, tipo="webinar", citta="Online",
                gratuito=True, crediti=False, crediti_ore=0,
                desc="Evento segnalato da AdvisorOnline.",
                url=link, fonte="advisoronline.it"
            ))
    print(f"[AdvisorOnline] {len(events)} eventi trovati")
    return events


def scrape_quellocheconta():
    """Mese educazione finanziaria — ottobre."""
    events = []
    url = "https://quellocheconta.gov.it"
    html = get_html(url)
    soup = BeautifulSoup(html, "lxml")
    anno = datetime.now().year
    if datetime.now().month > 10:
        anno += 1
    events.append(make_event(
        titolo=f"Mese Educazione Finanziaria {anno}", org="MEF / vari enti",
        data=f"{anno}-10-01", tipo="presenza", citta="Tutta Italia",
        gratuito=True, crediti=False, crediti_ore=0,
        desc="Ottobre: mese nazionale dell'educazione finanziaria. Decine di eventi locali gratuiti.",
        url=url, fonte="quellocheconta.gov.it", ricorrente=True
    ))
    print(f"[QuelloCheConta] 1 evento trovato")
    return events


def scrape_pictet():
    """Pictet AM — eventi advisor (JS-heavy)."""
    events = []
    url = "https://am.pictet.com/it/it/advisors/events"
    html = get_html_js(url, wait=5000)
    soup = BeautifulSoup(html, "lxml")
    
    items = soup.select("[class*='event'], article, .card, [class*='card']")
    for item in items[:15]:
        titolo = item.select_one("h2, h3, h4, [class*='title'], [class*='heading']")
        data_el = item.select_one("time, [class*='date'], [class*='when']")
        link_el = item.select_one("a[href]")
        if not titolo:
            continue
        titolo_txt = titolo.get_text(strip=True)
        data = parse_italian_date(data_el.get_text() if data_el else item.get_text())
        link = link_el["href"] if link_el else url
        if link.startswith("/"):
            link = "https://am.pictet.com" + link
        if data and len(titolo_txt) > 5:
            events.append(make_event(
                titolo=titolo_txt, org="Pictet",
                data=data, tipo="webinar", citta="Online",
                gratuito=True, crediti=True, crediti_ore=1,
                desc="Appuntamento digitale Pictet AM per advisor.",
                url=link, fonte="am.pictet.com/it/it/advisors/events", ricorrente=True
            ))
    print(f"[Pictet] {len(events)} eventi trovati")
    return events


def scrape_schroders():
    """Schroders Italia — webinar e roadshow (JS-heavy)."""
    events = []
    url = "https://www.schrodersportal.it"
    html = get_html_js(url, wait=5000)
    soup = BeautifulSoup(html, "lxml")
    
    items = soup.select("[class*='event'], article, .card, [class*='card'], [class*='webinar']")
    for item in items[:15]:
        titolo = item.select_one("h2, h3, h4, [class*='title']")
        data_el = item.select_one("time, [class*='date']")
        link_el = item.select_one("a[href]")
        if not titolo:
            continue
        titolo_txt = titolo.get_text(strip=True)
        data = parse_italian_date(data_el.get_text() if data_el else item.get_text())
        link = link_el["href"] if link_el else url
        if not link.startswith("http"):
            link = "https://www.schrodersportal.it" + link
        if data and len(titolo_txt) > 5:
            events.append(make_event(
                titolo=titolo_txt, org="Schroders",
                data=data, tipo="webinar", citta="Online",
                gratuito=True, crediti=True, crediti_ore=1,
                desc="Webinar o roadshow Schroders per advisor.",
                url=link, fonte="schrodersportal.it", ricorrente=True
            ))
    print(f"[Schroders] {len(events)} eventi trovati")
    return events


def scrape_blackrock():
    """BlackRock Italia — webinar (JS-heavy)."""
    events = []
    url = "https://www.blackrock.com/it/consulenti-finanziari"
    html = get_html_js(url, wait=5000)
    soup = BeautifulSoup(html, "lxml")
    
    items = soup.select("[class*='event'], [class*='webinar'], article")
    for item in items[:10]:
        titolo = item.select_one("h2, h3, h4, [class*='title']")
        data_el = item.select_one("time, [class*='date']")
        link_el = item.select_one("a[href]")
        if not titolo:
            continue
        titolo_txt = titolo.get_text(strip=True)
        data = parse_italian_date(data_el.get_text() if data_el else item.get_text())
        link = link_el["href"] if link_el else url
        if not link.startswith("http"):
            link = "https://www.blackrock.com" + link
        if data and len(titolo_txt) > 5:
            events.append(make_event(
                titolo=titolo_txt, org="BlackRock",
                data=data, tipo="webinar", citta="Online",
                gratuito=True, crediti=False, crediti_ore=0,
                desc="Webinar BlackRock per consulenti finanziari.",
                url=link, fonte="blackrock.com/it"
            ))
    print(f"[BlackRock] {len(events)} eventi trovati")
    return events


def scrape_jpmorgan():
    """JP Morgan AM — eventi (JS-heavy)."""
    events = []
    url = "https://am.jpmorgan.com/it/it/asset-management/adv/"
    html = get_html_js(url, wait=5000)
    soup = BeautifulSoup(html, "lxml")
    
    items = soup.select("[class*='event'], [class*='webinar'], article, .card")
    for item in items[:10]:
        titolo = item.select_one("h2, h3, h4, [class*='title']")
        data_el = item.select_one("time, [class*='date']")
        link_el = item.select_one("a[href]")
        if not titolo:
            continue
        titolo_txt = titolo.get_text(strip=True)
        data = parse_italian_date(data_el.get_text() if data_el else item.get_text())
        link = link_el["href"] if link_el else url
        if not link.startswith("http"):
            link = "https://am.jpmorgan.com" + link
        if data and len(titolo_txt) > 5:
            events.append(make_event(
                titolo=titolo_txt, org="JP Morgan AM",
                data=data, tipo="webinar", citta="Online",
                gratuito=True, crediti=True, crediti_ore=1,
                desc="Evento JP Morgan AM per advisor italiani.",
                url=link, fonte="am.jpmorgan.com/it"
            ))
    print(f"[JPMorgan] {len(events)} eventi trovati")
    return events


def scrape_fidelity():
    """Fidelity International Italia."""
    events = []
    url = "https://www.fidelity.it/intermediaries"
    html = get_html_js(url, wait=4000)
    soup = BeautifulSoup(html, "lxml")
    
    items = soup.select("[class*='event'], [class*='webinar'], article, .card")
    for item in items[:10]:
        titolo = item.select_one("h2, h3, h4, [class*='title']")
        data_el = item.select_one("time, [class*='date']")
        link_el = item.select_one("a[href]")
        if not titolo:
            continue
        titolo_txt = titolo.get_text(strip=True)
        data = parse_italian_date(data_el.get_text() if data_el else item.get_text())
        link = link_el["href"] if link_el else url
        if not link.startswith("http"):
            link = "https://www.fidelity.it" + link
        if data and len(titolo_txt) > 5:
            events.append(make_event(
                titolo=titolo_txt, org="Fidelity",
                data=data, tipo="webinar", citta="Online",
                gratuito=True, crediti=False, crediti_ore=0,
                desc="Evento Fidelity International per intermediari.",
                url=link, fonte="fidelity.it"
            ))
    print(f"[Fidelity] {len(events)} eventi trovati")
    return events


def scrape_amundi():
    """Amundi Italia — webinar e ETF Academy."""
    events = []
    urls = [
        "https://www.amundi.com/ita_advisor",
        "https://www.amundietf.it/professional/academy",
    ]
    for url in urls:
        html = get_html_js(url, wait=4000)
        soup = BeautifulSoup(html, "lxml")
        items = soup.select("[class*='event'], [class*='webinar'], article, .card")
        for item in items[:8]:
            titolo = item.select_one("h2, h3, h4, [class*='title']")
            data_el = item.select_one("time, [class*='date']")
            link_el = item.select_one("a[href]")
            if not titolo:
                continue
            titolo_txt = titolo.get_text(strip=True)
            data = parse_italian_date(data_el.get_text() if data_el else item.get_text())
            link = link_el["href"] if link_el else url
            if not link.startswith("http"):
                link = "https://www.amundi.com" + link
            if data and len(titolo_txt) > 5:
                events.append(make_event(
                    titolo=titolo_txt, org="Amundi",
                    data=data, tipo="webinar", citta="Online",
                    gratuito=True, crediti=False, crediti_ore=0,
                    desc="Webinar Amundi per advisor o ETF Academy.",
                    url=link, fonte="amundi.com/ita_advisor"
                ))
    print(f"[Amundi] {len(events)} eventi trovati")
    return events


# ── Deduplicazione ────────────────────────────────────────────────────────────

def dedup(events):
    """Rimuove duplicati per (titolo normalizzato, data)."""
    seen = set()
    out = []
    for ev in events:
        key = (re.sub(r'\s+', ' ', ev['titolo'].lower().strip()[:40]), ev['data'])
        if key not in seen:
            seen.add(key)
            out.append(ev)
    return out


def filtra_futuri(events, mesi=8):
    """Mantieni solo eventi entro N mesi da oggi + eventi senza data valida."""
    oggi = datetime.now().date()
    limite = oggi + timedelta(days=mesi*30)
    out = []
    for ev in events:
        try:
            d = datetime.strptime(ev['data'], "%Y-%m-%d").date()
            if d >= oggi - timedelta(days=30) and d <= limite:
                out.append(ev)
        except Exception:
            pass
    return out


# ── Main ──────────────────────────────────────────────────────────────────────

SCRAPERS = [
    ("FundsPeople",     scrape_fundspeople),
    ("ANASF",           scrape_anasf),
    ("ACEPI",           scrape_acepi),
    ("InvestingMilano", scrape_investing_milano),
    ("Salone",          scrape_salone_risparmio),
    ("FeeOnly",         scrape_fee_only_summit),
    ("EFPA",            scrape_efpa),
    ("AdvisorOnline",   scrape_advisoronline),
    ("QuelloCheConta",  scrape_quellocheconta),
    ("Pictet",          scrape_pictet),
    ("Schroders",       scrape_schroders),
    ("BlackRock",       scrape_blackrock),
    ("JPMorgan",        scrape_jpmorgan),
    ("Fidelity",        scrape_fidelity),
    ("Amundi",          scrape_amundi),
]

def main():
    # Carica eventi esistenti come fallback
    existing = []
    p = Path("eventi.json")
    if p.exists():
        try:
            data = json.loads(p.read_text())
            existing = data.get("eventi", [])
            print(f"[INFO] Caricati {len(existing)} eventi esistenti come fallback")
        except Exception:
            pass

    all_events = []
    errors = []

    for nome, fn in SCRAPERS:
        try:
            evs = fn()
            all_events.extend(evs)
            time.sleep(1)  # pausa gentile tra richieste
        except Exception as e:
            errors.append(nome)
            print(f"[ERROR] {nome}: {e}")
            traceback.print_exc()

    print(f"\n[INFO] Totale grezzo: {len(all_events)} eventi")

    # Deduplicazione e filtro temporale
    all_events = dedup(all_events)
    all_events = filtra_futuri(all_events, mesi=8)
    all_events.sort(key=lambda x: x['data'])

    print(f"[INFO] Dopo dedup+filtro: {len(all_events)} eventi")

    # Se scraping ha prodotto troppo poco, integra con esistenti
    if len(all_events) < 5 and existing:
        print("[WARN] Pochi eventi trovati, uso fallback da eventi.json esistente")
        all_events = existing

    output = {
        "aggiornato": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "totale": len(all_events),
        "errori": errors,
        "eventi": all_events
    }

    p.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"\n✅ eventi.json aggiornato con {len(all_events)} eventi")
    if errors:
        print(f"⚠️  Siti con errori: {', '.join(errors)}")

if __name__ == "__main__":
    main()
