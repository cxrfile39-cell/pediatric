#!/usr/bin/env python3
"""Fetch the latest pediatric literature from PubMed, grouped by subspecialty.

Writes site/data.json (latest week), site/archive/YYYY-MM-DD.json and site/archive/index.json.
Standard library only. Optional env vars: NCBI_API_KEY, NCBI_EMAIL, DAYS_BACK, MAX_PER_SPECIALTY.
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
API_KEY = os.environ.get("NCBI_API_KEY", "").strip()
EMAIL = os.environ.get("NCBI_EMAIL", "").strip()
DAYS_BACK = int(os.environ.get("DAYS_BACK", "7"))
MAX_PER = int(os.environ.get("MAX_PER_SPECIALTY", "40"))
DELAY = 0.12 if API_KEY else 0.4

PEDS = ('("Child"[Mesh] OR "Infant"[Mesh] OR "Adolescent"[Mesh] OR "Pediatrics"[Mesh] '
        'OR pediatric*[tiab] OR paediatric*[tiab] OR child*[tiab] OR infant*[tiab] '
        'OR neonat*[tiab] OR newborn*[tiab] OR adolescen*[tiab])')

TYPES = ('("Journal Article"[pt] OR "Review"[pt] OR "Systematic Review"[pt] OR "Meta-Analysis"[pt] '
         'OR "Guideline"[pt] OR "Practice Guideline"[pt] OR "Consensus Development Conference"[pt]) '
         'NOT ("Comment"[pt] OR "Editorial"[pt] OR "Letter"[pt] OR "Erratum"[pt] OR "Case Reports"[pt] '
         'OR "Published Erratum"[pt] OR "Retracted Publication"[pt] OR "Preprint"[pt]) '
         'AND hasabstract AND english[la]')

SPECIALTIES = [
    ("Adolescent Medicine",
     '("Adolescent Medicine"[Mesh] OR "Adolescent Health"[Mesh] OR "adolescent medicine"[tiab] OR '
     '"adolescent health"[tiab] OR ((contracepti*[tiab] OR "eating disorder*"[tiab] OR "anorexia nervosa"[tiab] '
     'OR "risk behavio*"[tiab] OR "substance use"[tiab] OR vaping[tiab]) AND adolescen*[tiab]))'),
    ("Pediatric Allergy and Immunology",
     '("Hypersensitivity"[Mesh] OR "Food Hypersensitivity"[Mesh] OR "Immunologic Deficiency Syndromes"[Mesh] '
     'OR allerg*[tiab] OR anaphyla*[tiab] OR "atopic dermatitis"[tiab] OR "inborn errors of immunity"[tiab] '
     'OR immunodeficienc*[tiab] OR "oral immunotherapy"[tiab])'),
    ("Pediatric Cardiology",
     '("Heart Defects, Congenital"[Mesh] OR "Heart Diseases"[Mesh] OR "congenital heart"[tiab] OR '
     'cardiomyopath*[tiab] OR arrhythmi*[tiab] OR "Kawasaki"[tiab] OR myocarditis[tiab] OR "Fontan"[tiab] '
     'OR "pulmonary hypertension"[tiab])'),
    ("Child Abuse Pediatrics",
     '("Child Abuse"[Mesh] OR "child abuse"[tiab] OR "child maltreatment"[tiab] OR "abusive head trauma"[tiab] '
     'OR "child neglect"[tiab] OR "child sexual abuse"[tiab] OR "non-accidental"[tiab] OR "nonaccidental"[tiab] '
     'OR "physical abuse"[tiab] OR "sentinel injur*"[tiab])'),
    ("Pediatric Critical Care Medicine",
     '("Intensive Care Units, Pediatric"[Mesh] OR "Critical Care"[Mesh] OR "PICU"[tiab] OR '
     '"pediatric intensive care"[tiab] OR "paediatric intensive care"[tiab] OR "critically ill"[tiab] OR '
     '"septic shock"[tiab] OR "mechanical ventilation"[tiab] OR ECMO[tiab] OR "Phoenix sepsis"[tiab])'),
    ("Developmental-Behavioral Pediatrics",
     '("Neurodevelopmental Disorders"[Mesh] OR "Autism Spectrum Disorder"[Mesh] OR '
     '"Attention Deficit Disorder with Hyperactivity"[Mesh] OR "Developmental Disabilities"[Mesh] OR '
     'autism[tiab] OR ADHD[tiab] OR "developmental delay"[tiab] OR "neurodevelopment*"[tiab] OR '
     '"learning disabilit*"[tiab] OR "developmental-behavioral"[tiab])'),
    ("Pediatric Emergency Medicine",
     '("Emergency Service, Hospital"[Mesh] OR "Emergency Medicine"[Mesh] OR "emergency department*"[tiab] '
     'OR "pediatric emergency"[tiab] OR "paediatric emergency"[tiab] OR "PECARN"[tiab] OR triage[tiab] '
     'OR resuscitation[tiab])'),
    ("Pediatric Endocrinology",
     '("Endocrine System Diseases"[Mesh] OR "Diabetes Mellitus, Type 1"[Mesh] OR "type 1 diabetes"[tiab] '
     'OR "growth hormone"[tiab] OR "short stature"[tiab] OR thyroid*[tiab] OR "precocious puberty"[tiab] '
     'OR "adrenal insufficiency"[tiab] OR "congenital adrenal hyperplasia"[tiab] OR "pediatric obesity"[tiab] '
     'OR "childhood obesity"[tiab] OR "differences of sex development"[tiab])'),
    ("Pediatric Gastroenterology",
     '("Gastrointestinal Diseases"[Mesh] OR "Liver Diseases"[Mesh] OR "inflammatory bowel disease"[tiab] OR '
     'Crohn*[tiab] OR "ulcerative colitis"[tiab] OR "celiac"[tiab] OR "eosinophilic esophagitis"[tiab] OR '
     '"biliary atresia"[tiab] OR hepatolog*[tiab] OR "gastroesophageal reflux"[tiab] OR constipation[tiab] '
     'OR "MASLD"[tiab] OR "NAFLD"[tiab])'),
    ("Pediatric Hematology and Oncology",
     '("Neoplasms"[Mesh] OR "Hematologic Diseases"[Mesh] OR leukemi*[tiab] OR lymphoma*[tiab] OR '
     'neuroblastoma[tiab] OR "brain tumo*"[tiab] OR sarcoma*[tiab] OR "Wilms"[tiab] OR "sickle cell"[tiab] '
     'OR thalassemi*[tiab] OR hemophilia[tiab] OR "immune thrombocytopeni*"[tiab] OR "CAR-T"[tiab] OR '
     '"childhood cancer"[tiab])'),
    ("Pediatric Hospital Medicine",
     '("Hospitalists"[Mesh] OR "Hospitals, Pediatric"[Mesh] OR "hospital medicine"[tiab] OR '
     'hospitalist*[tiab] OR "hospitalized child*"[tiab] OR "length of stay"[tiab] OR bronchiolitis[tiab] '
     'OR "febrile infant*"[tiab] OR "readmission*"[tiab] OR "inpatient"[tiab])'),
    ("Pediatric Infectious Diseases",
     '("Infections"[Mesh] OR "Communicable Diseases"[Mesh] OR "Vaccines"[Mesh] OR infection*[tiab] OR '
     'vaccin*[tiab] OR sepsis[tiab] OR antimicrobial*[tiab] OR antibiotic*[tiab] OR "RSV"[tiab] OR '
     'influenza[tiab] OR "COVID-19"[tiab] OR "Mycoplasma"[tiab] OR "pertussis"[tiab] OR measles[tiab])'),
    ("Neonatal-Perinatal Medicine (Neonatology)",
     '("Infant, Newborn"[Mesh] OR "Intensive Care Units, Neonatal"[Mesh] OR "Infant, Premature"[Mesh] OR '
     'neonat*[tiab] OR preterm[tiab] OR NICU[tiab] OR "bronchopulmonary dysplasia"[tiab] OR '
     '"necrotizing enterocolitis"[tiab] OR "hypoxic-ischemic"[tiab] OR "very low birth weight"[tiab] OR '
     'perinatal[tiab])'),
    ("Pediatric Nephrology",
     '("Kidney Diseases"[Mesh] OR "Urinary Tract Infections"[Mesh] OR nephro*[tiab] OR "kidney"[tiab] OR '
     '"renal"[tiab] OR "acute kidney injury"[tiab] OR "chronic kidney disease"[tiab] OR "nephrotic syndrome"[tiab] '
     'OR dialysis[tiab] OR "vesicoureteral reflux"[tiab] OR hypertension[tiab])'),
    ("Pediatric Pulmonology",
     '("Lung Diseases"[Mesh] OR "Respiratory Tract Diseases"[Mesh] OR asthma[tiab] OR "cystic fibrosis"[tiab] '
     'OR "lung function"[tiab] OR pulmonar*[tiab] OR "interstitial lung"[tiab] OR "primary ciliary dyskinesia"[tiab] '
     'OR "chronic cough"[tiab] OR bronchiectasis[tiab] OR spirometry[tiab])'),
    ("Pediatric Rheumatology",
     '("Rheumatic Diseases"[Mesh] OR "Arthritis, Juvenile"[Mesh] OR "juvenile idiopathic arthritis"[tiab] OR '
     '"lupus"[tiab] OR "SLE"[tiab] OR vasculitis[tiab] OR "juvenile dermatomyositis"[tiab] OR "MIS-C"[tiab] '
     'OR autoinflammat*[tiab] OR "Kawasaki disease"[tiab] OR "macrophage activation syndrome"[tiab] OR uveitis[tiab])'),
    ("Pediatric Neurology",
     '("Nervous System Diseases"[Mesh] OR epilep*[tiab] OR seizure*[tiab] OR "cerebral palsy"[tiab] OR '
     'migraine*[tiab] OR headache*[tiab] OR "spinal muscular atrophy"[tiab] OR "muscular dystrophy"[tiab] '
     'OR "pediatric stroke"[tiab] OR encephalitis[tiab] OR "neuromuscular"[tiab] OR concussion[tiab])'),
    ("Pediatric Dermatology",
     '("Skin Diseases"[Mesh] OR dermatolog*[tiab] OR "atopic dermatitis"[tiab] OR eczema[tiab] OR '
     'psoriasis[tiab] OR "infantile hemangioma*"[tiab] OR "vascular malformation*"[tiab] OR acne[tiab] '
     'OR "epidermolysis bullosa"[tiab] OR "alopecia areata"[tiab] OR vitiligo[tiab])'),
    ("Pediatric Genetics and Metabolism",
     '("Genetic Diseases, Inborn"[Mesh] OR "Metabolism, Inborn Errors"[Mesh] OR "inborn error*"[tiab] OR '
     '"genetic testing"[tiab] OR "exome sequencing"[tiab] OR "genome sequencing"[tiab] OR "newborn screening"[tiab] '
     'OR "rare disease*"[tiab] OR "gene therapy"[tiab] OR syndrom*[tiab] OR "metabolic disorder*"[tiab])'),
    ("Pediatric Rehabilitation Medicine",
     '("Rehabilitation"[Mesh] OR "Physical Therapy Modalities"[Mesh] OR rehabilitat*[tiab] OR '
     '"physical therapy"[tiab] OR physiotherap*[tiab] OR "occupational therapy"[tiab] OR "spinal cord injur*"[tiab] '
     'OR "brain injur*"[tiab] OR "cerebral palsy"[tiab] OR "spasticity"[tiab] OR "motor function"[tiab])'),
    ("Pediatric Sleep Medicine",
     '("Sleep Wake Disorders"[Mesh] OR "Sleep"[Mesh] OR sleep*[tiab] OR "obstructive sleep apnea"[tiab] OR '
     'insomnia[tiab] OR narcolepsy[tiab] OR polysomnograph*[tiab] OR "restless legs"[tiab] OR melatonin[tiab])'),
    ("Pediatric Palliative Care",
     '("Palliative Care"[Mesh] OR "Terminal Care"[Mesh] OR "Hospice Care"[Mesh] OR palliative[tiab] OR '
     '"end-of-life"[tiab] OR "end of life"[tiab] OR hospice[tiab] OR bereavement[tiab] OR '
     '"advance care planning"[tiab] OR "life-limiting"[tiab] OR "goals of care"[tiab])'),
]


def eutils(endpoint, params, retries=4):
    params = dict(params, tool="peds-lit-weekly", db="pubmed")
    if API_KEY:
        params["api_key"] = API_KEY
    if EMAIL:
        params["email"] = EMAIL
    data = urllib.parse.urlencode(params).encode()
    for attempt in range(retries):
        try:
            time.sleep(DELAY)
            req = urllib.request.Request(EUTILS + endpoint, data=data,
                                         headers={"User-Agent": "peds-lit-weekly/1.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            wait = 2 ** attempt * 2
            print(f"  ! {endpoint} failed ({e}); retry in {wait}s", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"E-utilities {endpoint} failed after {retries} attempts")


def search(term):
    raw = eutils("esearch.fcgi", {"term": term, "retmode": "json", "retmax": MAX_PER,
                                  "sort": "pub_date", "datetype": "edat", "reldate": DAYS_BACK})
    res = json.loads(raw)["esearchresult"]
    return res.get("idlist", []), int(res.get("count", 0))


def text(el):
    return "".join(el.itertext()).strip() if el is not None else ""


MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def pub_date(art):
    """Return (display string, sortable ISO date)."""
    for path in ("Journal/JournalIssue/PubDate", "ArticleDate"):
        d = art.find(path)
        if d is None:
            continue
        y = d.findtext("Year")
        if not y:
            md = d.findtext("MedlineDate") or ""
            if md[:4].isdigit():
                return md, f"{md[:4]}-01-01"
            continue
        m = d.findtext("Month") or "1"
        m = int(m) if m.isdigit() else MONTHS.get(m[:3].lower(), 1)
        day = d.findtext("Day") or "1"
        day = int(day) if day.isdigit() else 1
        return f"{y}-{m:02d}" + (f"-{day:02d}" if d.findtext("Day") else ""), f"{y}-{m:02d}-{day:02d}"
    return "", ""


GUIDE_RE = re.compile(r"\b(guidelines?|consensus statement|consensus recommendations?|expert consensus|"
                      r"position statement|position paper|clinical practice recommendations?)\b", re.I)


def classify(pts, title=""):
    """Original / Review / Meta / Guideline (same rules as the web page)."""
    s = {p.lower() for p in pts}
    t = title.lower()
    if any("guideline" in p or "consensus" in p for p in s) or GUIDE_RE.search(t):
        return "Guideline"
    if s & {"meta-analysis", "systematic review", "network meta-analysis"} or re.search(
            r"meta-analys|systematic review|umbrella review", t):
        return "Meta"
    if "review" in s or re.search(r"\b(narrative|scoping|literature|state-of-the-art) review\b", t):
        return "Review"
    return "Original"


def parse_articles(xml_bytes):
    out = {}
    root = ET.fromstring(xml_bytes)
    for pa in root.iter("PubmedArticle"):
        mc = pa.find("MedlineCitation")
        pmid = mc.findtext("PMID")
        art = mc.find("Article")
        if art is None or not pmid:
            continue
        pts = [text(p) for p in art.findall("PublicationTypeList/PublicationType")]
        authors = []
        for a in art.findall("AuthorList/Author"):
            if a.findtext("CollectiveName"):
                authors.append(a.findtext("CollectiveName"))
            elif a.findtext("LastName"):
                authors.append(f"{a.findtext('LastName')} {a.findtext('Initials') or ''}".strip())
        abs_parts = []
        for at in art.findall("Abstract/AbstractText"):
            label = at.get("Label")
            t = text(at)
            if t:
                abs_parts.append(f"{label}: {t}" if label else t)
        doi = ""
        for aid in pa.findall("PubmedData/ArticleIdList/ArticleId"):
            if aid.get("IdType") == "doi":
                doi = (aid.text or "").strip()
        if not doi:
            for el in art.findall("ELocationID"):
                if el.get("EIdType") == "doi":
                    doi = (el.text or "").strip()
        disp, sort_date = pub_date(art)
        out[pmid] = {
            "pmid": pmid,
            "title": text(art.find("ArticleTitle")),
            "journal": art.findtext("Journal/ISOAbbreviation") or art.findtext("Journal/Title") or "",
            "date": disp,
            "sortDate": sort_date,
            "authors": authors[:6] + (["et al."] if len(authors) > 6 else []),
            "abstract": "\n".join(abs_parts),
            "type": classify(pts, text(art.find("ArticleTitle"))),
            "pubTypes": pts,
            "doi": doi,
            "specialties": [],
        }
    return out


def fetch_details(pmids):
    result = {}
    for i in range(0, len(pmids), 100):
        chunk = pmids[i:i + 100]
        result.update(parse_articles(eutils("efetch.fcgi", {"id": ",".join(chunk), "retmode": "xml"})))
    return result


def write_index(arch):
    """Rebuild site/archive/index.json: list of weeks, newest first."""
    weeks = []
    for f in sorted(arch.glob("????-??-??.json"), reverse=True):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        weeks.append({"week": f.stem, "from": d.get("from", ""), "count": len(d.get("articles", [])),
                      "file": f"archive/{f.name}"})
    (arch / "index.json").write_text(json.dumps(weeks, ensure_ascii=False, indent=1), encoding="utf-8")


def main():
    articles = {}
    counts = {}
    for name, q in SPECIALTIES:
        term = f"{q} AND {PEDS} AND {TYPES}"
        ids, total = search(term)
        print(f"{name}: {len(ids)} / {total}")
        counts[name] = total
        need = [i for i in ids if i not in articles]
        if need:
            articles.update(fetch_details(need))
        for i in ids:
            if i in articles and name not in articles[i]["specialties"]:
                articles[i]["specialties"].append(name)

    items = sorted(articles.values(), key=lambda a: (a["sortDate"], a["pmid"]), reverse=True)
    now = datetime.now(timezone(timedelta(hours=8)))
    payload = {
        "updated": now.strftime("%Y-%m-%d %H:%M (UTC+8)"),
        "daysBack": DAYS_BACK,
        "specialties": [n for n, _ in SPECIALTIES],
        "totals": counts,
        "articles": items,
    }
    payload["week"] = now.strftime("%Y-%m-%d")
    payload["from"] = (now - timedelta(days=DAYS_BACK)).strftime("%Y-%m-%d")
    site = ROOT / "site"
    arch = site / "archive"
    arch.mkdir(parents=True, exist_ok=True)
    dumped = json.dumps(payload, ensure_ascii=False)
    (site / "data.json").write_text(dumped, encoding="utf-8")
    (arch / f"{payload['week']}.json").write_text(dumped, encoding="utf-8")
    write_index(arch)
    print(f"Saved {len(items)} unique articles.")
    if not items:
        print("Warning: no articles found.", file=sys.stderr)


if __name__ == "__main__":
    main()
