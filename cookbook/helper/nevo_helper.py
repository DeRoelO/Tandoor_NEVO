import csv
import os
import re
from functools import lru_cache
from typing import List, Dict, Any, Optional

NEVO_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'nevo', 'nevo.csv')

def parse_float(val: str) -> Optional[float]:
    if not val:
        return None
    val = val.strip().replace('"', '').replace("'", "")
    if not val or val == '-':
        return None
    val = val.replace(',', '.')
    try:
        return float(val)
    except ValueError:
        return None

# Meest voorkomende Nederlandse synoniemen & stopwoorden
STOPWORDS = {'verse', 'vers', 'gedroogde', 'gedroogd', 'geraspte', 'geraspt', 'fijngesneden', 'gesneden', 'gehakte', 'gehakt', 'stukjes', 'stuk', 'stuks', 'tenen', 'teen', 'teentjes', 'teentje', 'in', 'blik', 'blikjes', 'blikje', 'pot', 'glas', 'naar', 'smaak', 'rijpe', 'flinke', 'handen', 'handje', 'bosje', 'takje', 'takjes', 'snufje', 'mespuntje', 'milde', 'mild', 'halve', 'extra', 'vergine', 'koudgeperste', 'witte', 'wit', 'bruine', 'bruin', 'groene', 'groen', 'rode', 'rood'}

DUTCH_SYNONYMS = {
    'uien': 'ui',
    'eieren': 'ei kippen',
    'aardappels': 'aardappelen',
    'aardappelen': 'aardappel',
    'appels': 'appel',
    'peren': 'peer',
    'bananen': 'banaan',
    'tomaten': 'tomaat',
    'wortels': 'wortel',
    'champignons': 'champignon',
    'boontjes': 'bonen',
    'erwten': 'erwt',
    'paprika\'s': 'paprika',
    'courgettes': 'courgette',
    'knoflooktenen': 'knoflook',
    'knoflookteen': 'knoflook',
    'bosuien': 'ui sla',
    'bosui': 'ui sla',
    'lente-ui': 'ui sla',
    'lente-uien': 'ui sla',
    'rode ui': 'ui rode',
    'rode uien': 'ui rode',
    'olijfolie': 'olie olijf',
    'pijnboompitjes': 'pijnboompitten',
    'pijnboompit': 'pijnboompitten',
    'venkelknollen': 'venkel',
    'venkelknol': 'venkel',
    'krulpeterselie': 'peterselie vers',
    'bladpeterselie': 'peterselie vers',
    'cannellinibonen': 'bonen cannellini',
    'cannellini': 'bonen cannellini',
    'polpa': 'tomaat in blik',
    'platbroden': 'tarwebroodje',
    'platbrood': 'tarwebroodje',
    'platbroden': 'tarwebroodje',
    'libanese': 'tarwebroodje',
    'rucola': 'sla rucola',
    'tomaatjes': 'tomaat',
    'cherrytomaatjes': 'tomaat kers',
    'zongedroogde tomaten': 'tomaat',
    'tonijn': 'tonijn in water',
}

@lru_cache(maxsize=1)
def load_nevo_records() -> List[Dict[str, Any]]:
    records = []
    if not os.path.exists(NEVO_FILE):
        return records

    with open(NEVO_FILE, 'r', encoding='utf-8', errors='replace') as f:
        first_line = f.readline()
        f.seek(0)
        delimiter = '|' if '|' in first_line else ';'
        reader = csv.DictReader(f, delimiter=delimiter)
        for row in reader:
            code_str = row.get('NEVO-code') or row.get('NEVO-code/NEVO-code') or ''
            try:
                code = int(code_str.strip())
            except ValueError:
                continue

            name_nl = (row.get('Voedingsmiddelnaam/Dutch food name') or row.get('Dutch food name') or '').strip()
            name_en = (row.get('Engelse naam/Food name') or row.get('Food name') or '').strip()
            synonyms = (row.get('Synoniem') or row.get('Synonyms') or '').strip()

            kcal = parse_float(row.get('ENERCC (kcal)'))
            prot = parse_float(row.get('PROT (g)'))
            fat = parse_float(row.get('FAT (g)'))
            fasat = parse_float(row.get('FASAT (g)'))
            cho = parse_float(row.get('CHO (g)'))
            sugar = parse_float(row.get('SUGAR (g)'))
            fibt = parse_float(row.get('FIBT (g)'))
            na_mg = parse_float(row.get('NA (mg)'))
            salt_g = round(na_mg * 2.5 / 1000.0, 4) if na_mg is not None else None

            records.append({
                'code': code,
                'name': name_nl,
                'name_en': name_en,
                'synonyms': synonyms,
                'search_text': f"{name_nl} {name_en} {synonyms}".lower(),
                'nutrients': {
                    'calories': kcal,
                    'proteins': prot,
                    'fats': fat,
                    'saturated_fat': fasat,
                    'carbohydrates': cho,
                    'sugars': sugar,
                    'fibers': fibt,
                    'salt': salt_g,
                }
            })
    return records

def clean_query_text(query: str) -> str:
    # Verwijder leestekens en cijfers
    q = re.sub(r'[^\w\s-]', ' ', query.lower())
    q = re.sub(r'\b\d+\b', '', q)
    words = [w for w in q.split() if w not in STOPWORDS]
    cleaned = ' '.join(words)
    return cleaned if cleaned else query.lower()

def search_nevo(query: str, limit: int = 25) -> List[Dict[str, Any]]:
    records = load_nevo_records()
    if not query:
        return records[:limit]

    cleaned_query = clean_query_text(query)
    expanded_terms = [cleaned_query]

    # Map exact terms and synonyms
    for term, target in DUTCH_SYNONYMS.items():
        if term in cleaned_query:
            expanded_terms.append(cleaned_query.replace(term, target))
            expanded_terms.append(target)
        for w in cleaned_query.split():
            if w == term:
                expanded_terms.append(target)

    terms = cleaned_query.split()
    results = []

    for r in records:
        text = r['search_text']
        name_lower = r['name'].lower()
        score = 0

        # Exacte / begin-match krijgt hoogste prioriteit
        for exp in expanded_terms:
            if name_lower == exp:
                score += 300
            elif name_lower.startswith(exp + ' ') or name_lower.startswith(exp + '-'):
                score += 150
            elif name_lower.startswith(exp):
                score += 80

        # Match op losse woorden
        matched_words = 0
        for term in terms:
            if term in text:
                matched_words += 1
                score += 15
                if term in name_lower:
                    score += 25

        # Prefereer basisproducten (bijv 'Ui rauw', 'Knoflook rauw') boven bewerkte sauzen
        if 'rauw' in name_lower:
            score += 20
        if 'saus' in name_lower and 'saus' not in cleaned_query:
            score -= 30

        if matched_words >= 1 or score > 30:
            results.append((score, r))

    results.sort(key=lambda x: x[0], reverse=True)
    return [r for score, r in results[:limit]]

def get_nevo_by_code(code: int) -> Optional[Dict[str, Any]]:
    records = load_nevo_records()
    for r in records:
        if r['code'] == code:
            return r
    return None
