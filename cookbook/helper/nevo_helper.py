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

# Bekende meervoud/synoniem mappings voor Nederlandse ingrediënten
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

def search_nevo(query: str, limit: int = 25) -> List[Dict[str, Any]]:
    records = load_nevo_records()
    if not query:
        return records[:limit]

    cleaned_query = query.strip().lower()
    expanded_terms = [cleaned_query]

    # Check mapping
    for term, target in DUTCH_SYNONYMS.items():
        if term in cleaned_query:
            expanded_terms.append(cleaned_query.replace(term, target))

    terms = cleaned_query.split()
    results = []

    for r in records:
        text = r['search_text']
        name_lower = r['name'].lower()
        score = 0

        # Directe match
        for exp in expanded_terms:
            if name_lower == exp:
                score += 200
            elif name_lower.startswith(exp + ' ') or name_lower.startswith(exp + '-'):
                score += 100
            elif name_lower.startswith(exp):
                score += 60

        # Term matching
        all_terms_found = True
        for term in terms:
            if term in text:
                score += 10
                if term in name_lower:
                    score += 15
            else:
                all_terms_found = False

        if all_terms_found or score > 40:
            results.append((score, r))

    results.sort(key=lambda x: x[0], reverse=True)
    return [r for score, r in results[:limit]]

def get_nevo_by_code(code: int) -> Optional[Dict[str, Any]]:
    records = load_nevo_records()
    for r in records:
        if r['code'] == code:
            return r
    return None
