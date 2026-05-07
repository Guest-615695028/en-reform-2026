#!/usr/bin/env python3
"""
Script to apply the repository's oxford/non-oxford reforms to Examples/longman9000.reformed.csv
Reads Examples/oxford.yaml and Examples/non-oxford.yaml and updates the fourth column (reformed)
"""
import re
import csv
from pathlib import Path

ROOT = Path('.')
OX_PATH = ROOT / 'Examples' / 'oxford.yaml'
NON_OX_PATH = ROOT / 'Examples' / 'non-oxford.yaml'
INPUT_CSV = ROOT / 'Examples' / 'longman9000.csv'
OUTPUT_CSV = ROOT / 'Examples' / 'longman9000.reformed.csv'


def parse_simple_yaml_like(path):
    """Parse a simple YAML-like file into ordered (key, value) pairs.
    This parser is tolerant: it ignores comments and blank lines and splits on first colon.
    It supports keys that are bracketed lists like [a,b] and values that are inline maps like {n: reccord}.
    """
    pairs = []
    text = path.read_text(encoding='utf-8')
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        # require a colon
        if ':' not in line:
            continue
        key, val = line.split(':', 1)
        key = key.strip()
        # remove inline comment in val
        val = re.split(r"\s+#", val)[0].strip()
        if not val:
            # empty mapping (treat as directive to remove?) skip
            continue
        pairs.append((key, val))
    return pairs


def build_mappings():
    pairs = parse_simple_yaml_like(OX_PATH)
    mapping = {}  # exact mapping: lower_key -> replacement or dict(pos->replacement)

    for key, val in pairs:
        # handle keys that are lists: [a,b]
        keys = []
        if key.startswith('[') and key.endswith(']'):
            inner = key[1:-1]
            keys = [k.strip().strip("\'\"") for k in inner.split(',')]
        else:
            keys = [key.strip().strip("\'\"")]

        # handle values that are inline maps {n: reccord}
        if val.startswith('{') and val.endswith('}'):
            inner = val[1:-1]
            # parse like n: reccord  (may contain commas, but usually simple)
            pos_map = {}
            for part in inner.split(','):
                if ':' in part:
                    pk, pv = part.split(':', 1)
                    pos_map[pk.strip()] = pv.strip()
            # store pos_map for all keys
            for k in keys:
                mapping[k.lower()] = {'pos_map': pos_map}
            continue

        # otherwise val is simple string (may start with -)
        replacement = val.strip()
        # if replacement starts with a leading hyphen as proscription, strip it
        if replacement.startswith('-'):
            replacement = replacement.lstrip('-').strip()
        # remove surrounding braces if any left
        replacement = replacement.strip()
        for k in keys:
            mapping[k.lower()] = {'value': replacement}

    # non-oxford (suffixes and small list)
    non_pairs = parse_simple_yaml_like(NON_OX_PATH)
    suffix_rules = []  # list of (suffix, replacement)
    for key, val in non_pairs:
        k = key.strip()
        v = val.strip()
        if k.startswith('-'):
            suffix = k.lstrip('-')
            # v may start with -
            rep = v.lstrip('-').strip()
            suffix_rules.append((suffix, rep))
        else:
            # exact word mapping
            mapping[k.lower()] = {'value': v}

    return mapping, suffix_rules


def pos_matches(pos_field, pos_key):
    """Check if pos_field (CSV) matches the pos_key from YAML like 'n' or 'noun'"""
    if not pos_field:
        return False
    pf = pos_field.lower()
    pk = pos_key.lower()
    # Normalize common abbreviations
    abbrev = {
        'n': 'noun', 'v': 'verb', 'adj': 'adjective', 'adv': 'adverb',
        'prep': 'preposition', 'conj': 'conjunction'
    }
    if pk in abbrev:
        pk = abbrev[pk]
    return pk in pf


def apply_rules_to_word(word, pos, mapping, suffix_rules):
    w = word.strip()
    lw = w.lower()
    # exact match
    if lw in mapping:
        entry = mapping[lw]
        if 'value' in entry:
            return entry['value']
        if 'pos_map' in entry:
            pos_map = entry['pos_map']
            # try to find a matching pos key
            for pk, rep in pos_map.items():
                if pos_matches(pos, pk):
                    return rep
            # no pos matched -> fallback to original
            return w
    # try suffix rules
    for suf, rep in suffix_rules:
        if lw.endswith(suf):
            base = w[:len(w) - len(suf)]
            return base + rep
    # fallback: return original
    return w


def main():
    mapping, suffix_rules = build_mappings()
    # Read input CSV (original longman9000.csv)
    # We will read the original Examples/longman9000.csv source file to preserve original data
    if not INPUT_CSV.exists():
        print('Input CSV not found:', INPUT_CSV)
        return 1

    # Read original csv rows (skip initial comment lines beginning with '#')
    rows = []
    with INPUT_CSV.open(encoding='utf-8') as fh:
        for raw in fh:
            if raw.strip().startswith('#'):
                rows.append(raw.rstrip('\n'))
            else:
                rows.append(raw.rstrip('\n'))

    # Parse CSV rows into data rows, but be tolerant: the file uses comma-separated values sometimes with spaces
    data = []
    header_seen = False
    output_lines = []
    # We'll write a header and then process lines that look like data
    output_lines.append('# word,quad,pos,reformed')
    output_lines.append('# Reformed by script using Examples/oxford.yaml and Examples/non-oxford.yaml')
    output_lines.append('')
    output_lines.append('word,quad,pos,reformed')

    for line in rows:
        if not line or line.strip().startswith('#'):
            # ignore comments beyond header
            continue
        # Split into three columns: word, quad, pos (pos may contain commas) - using maxsplit=2
        parts = [p.strip() for p in line.split(',', 2)]
        if len(parts) < 3:
            # keep unchanged
            output_lines.append(line)
            continue
        word = parts[0]
        quad = parts[1]
        pos = parts[2]
        reformed = apply_rules_to_word(word, pos, mapping, suffix_rules)
        output_lines.append(','.join([word, quad, pos, reformed]))

    OUTPUT_CSV.write_text('\n'.join(output_lines) + '\n', encoding='utf-8')
    print('Wrote', OUTPUT_CSV)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
