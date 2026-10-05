"""
Measures how accurately the AI reads the sample invoices, by comparing its output
with the known-correct answers in sample_invoices/ground_truth.json.

Run (needs LLM_API_KEY in .env):   python evaluate.py

Put the resulting accuracy number in your README — judges score "correctness".
Running this also fills cache/ so the deployed demo loads the samples instantly.

How lines are paired: each expected line is matched to the AI line with the most
similar product name (not an exact match). The AI sometimes copies an extra word
from a neighbouring column, e.g. "Jasmine Rice 25kg bag", or drops "(per kg)".
That doesn't affect any numbers, and the product-matching step handles it, so it is
reported separately instead of counting every field on that line as wrong.
"""
import json
from difflib import SequenceMatcher
from pathlib import Path

from extract import extract_invoice
from llm import load_env

ROOT = Path(__file__).parent
FIELDS = ["quantity", "unit_price", "line_total", "pack_size", "pack_unit"]


def close(a, b):
    if isinstance(a, str) or isinstance(b, str):
        return str(a) == str(b)
    return abs(float(a) - float(b)) <= 0.011


def similarity(a, b):
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def pair_lines(expected, got):
    """Greedy best-name pairing. Returns list of (expected_line, got_line_or_None)."""
    remaining = list(got)
    pairs = []
    for exp in expected:
        best = max(remaining, key=lambda g: similarity(exp["description"], g["description"]), default=None)
        if best is not None and similarity(exp["description"], best["description"]) >= 0.6:
            remaining.remove(best)
            pairs.append((exp, best))
        else:
            pairs.append((exp, None))
    return pairs, remaining


def main():
    load_env()
    truth = json.loads((ROOT / "sample_invoices/ground_truth.json").read_text())
    total = correct = inv_ok = 0
    header_total = header_ok = 0
    lines_total = names_exact = 0
    for t in truth:
        try:
            inv, warns = extract_invoice(ROOT / "sample_invoices" / t["file"], t["file"])
        except Exception as e:
            print(f"FAIL  {t['file']}: {e}")
            total += len(t["line_items"]) * len(FIELDS)
            lines_total += len(t["line_items"])
            continue
        got = [li.model_dump() for li in inv.line_items]
        file_ok = True
        for checks in [(inv.invoice_date.isoformat(), t["invoice_date"]), (inv.invoice_number, t["invoice_number"])]:
            header_total += 1
            header_ok += checks[0] == checks[1]
            file_ok &= checks[0] == checks[1]

        pairs, extra = pair_lines(t["line_items"], got)
        for exp, g in pairs:
            lines_total += 1
            if g is not None and g["description"].strip().lower() == exp["description"].lower():
                names_exact += 1
            for f in FIELDS:
                total += 1
                if g is not None and close(g[f], exp[f]):
                    correct += 1
                else:
                    file_ok = False
                    print(f"  miss {t['file']}: '{exp['description']}' {f}: "
                          f"expected {exp[f]}, got {g[f] if g else 'MISSING'}")
        for g in extra:
            file_ok = False
            print(f"  extra line in {t['file']}: '{g['description']}' (not a real product line)")
        inv_ok += file_ok
        print(f"{'OK  ' if file_ok else 'DIFF'}  {t['file']}" + (f"  ({len(warns)} warning)" if warns else ""))

    print(f"\nLine-item fields correct (qty, price, total, pack size, unit): {correct}/{total} = {correct / total:.1%}")
    print(f"Invoice dates & numbers correct: {header_ok}/{header_total}")
    print(f"Invoices with every number correct: {inv_ok}/{len(truth)}")
    print(f"Product names copied word-for-word: {names_exact}/{lines_total} "
          f"(small wording differences are handled by the product-matching step)")


if __name__ == "__main__":
    main()
