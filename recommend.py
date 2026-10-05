"""
Step 4 — Recommendations: the LLM turns the computed findings into a plain-English
action plan and drafts a negotiation email to the supplier.

The LLM only explains and advises. Every dollar figure shown to the user comes from
analyze.py, not from the model, so the AI can't invent numbers.
"""
import json

from analyze import fmt_unit_price
from llm import LLMError, chat_json

PROMPT_VERSION = "recommend-v3"

SYSTEM = """You advise the owner of a small food business (café/restaurant) on supplier costs.
You get findings that were already calculated by software. Do NOT do any maths and do NOT
invent numbers; refer to findings by id. Be specific, practical and brief. Plain English,
no jargon. The owner is busy and has little negotiating power, so suggest realistic moves:
asking for the old price, requesting a quote from the other supplier, buying a different
pack size, changing order size, or adjusting a menu price.

Rules about suppliers:
- Each finding lists "other_suppliers_that_sell_this". Only suggest moving an item to a supplier
  named in that list. Never suggest switching to the supplier the item already comes from.
- In the email you may quote the old and new prices exactly as given in the findings.

Make the advice fit each finding. Do NOT give the same advice for every item. Choose from:
- Biggest increases: ask the current supplier to return to the old price, AND get one competing quote.
- Hidden increase (smaller pack): point out the pack shrank, ask for the old pack size or a lower price.
- Small increases on everyday items: consider a small menu price change, or a larger order for a discount.
- Cheaper at another supplier: move the item to the named cheaper supplier, or ask the current one to match.
- Staples bought in bulk: consider a different pack size or ordering less often.
Each title should name the action (e.g. "Ask Harbourline to restore oil price"), not just the item.

Reply with ONE JSON object only:
{
  "actions": [                             // one per finding id you are given, most urgent first
    {"finding_id": string, "title": string (max 8 words), "advice": string (1-2 sentences)}
  ],
  "email": {                               // to the supplier with the biggest total increase
    "supplier": string,
    "subject": string,
    "body": string                         // polite, firm, under 150 words, signed "[Your name], [Your business]"
  }
}"""

TYPE_LABEL = {"price_increase": "price increase", "shrinkflation": "hidden increase (smaller pack, same price)",
              "supplier_gap": "cheaper at another supplier", "price_decrease": "price decrease"}


def _findings_for_prompt(findings, sold_by):
    out = []
    for f in findings:
        out.append({
            "id": f.id, "type": TYPE_LABEL[f.type], "item": f.item, "supplier": f.supplier,
            "was" if f.type != "supplier_gap" else "other_supplier_price": fmt_unit_price(f.baseline_price, f.base_unit),
            "now" if f.type != "supplier_gap" else "this_supplier_price": fmt_unit_price(f.current_price, f.base_unit),
            "change": f"{f.pct_change:+.1%}",
            ("extra_cost_per_year" if f.type != "supplier_gap" else "possible_saving_per_year"): f"${abs(f.annual_impact):,.0f}",
            "since": f.change_date, "note": f.detail,
            "other_suppliers_that_sell_this": sorted(sold_by.get(f.item, set()) - {f.supplier}),
        })
    return out


def _fallback(findings):
    """Template advice when no LLM is available."""
    actions = []
    for f in findings:
        if f.type == "supplier_gap":
            title, advice = f"Compare {f.item.lower()} suppliers", f"{f.detail} Ask {f.supplier} to match it or move this order."
        elif f.type == "shrinkflation":
            title, advice = f"Check {f.item.lower()} pack size", f"{f.detail} Ask for the original pack or a lower price."
        elif f.type == "price_increase":
            title, advice = f"Query {f.item.lower()} increase", f"Ask {f.supplier} to explain the {f.pct_change:+.0%} rise and get a competing quote."
        else:
            title, advice = f"{f.item} got cheaper", "Consider stocking up while the price is low."
        actions.append({"finding_id": f.id, "title": title, "advice": advice})
    return {"headline": "", "actions": actions, "email": None}


def headline(findings, summary):
    """Built in code (not by the AI) so the numbers are always exact."""
    increases = [f for f in findings if f.type in ("price_increase", "shrinkflation")]
    if not increases:
        return "No meaningful price increases found. Your supplier prices look stable."
    top = max(increases, key=lambda f: f.annual_impact)
    n = len(increases)
    return (f"{n} price rise{'s' if n != 1 else ''} {'are' if n != 1 else 'is'} costing you "
            f"${summary['annual_extra_cost']:,.0f} a year. Start with {top.item.lower()} from "
            f"{top.supplier} (+${top.annual_impact:,.0f}/yr).")


def recommend(findings, summary, lines=None, max_findings=8):
    top = [f for f in findings if f.type != "price_decrease"][:max_findings]
    if not top:
        return {"headline": headline(findings, summary), "actions": [], "email": None}, True
    sold_by = {}
    if lines is not None:
        for item, sup in lines[["canonical_name", "supplier"]].drop_duplicates().itertuples(index=False):
            sold_by.setdefault(item, set()).add(sup)
    payload = {"business_summary": {
        "monthly_supplier_spend": f"${summary['monthly_spend']:,.0f}",
        "total_extra_cost_per_year_from_increases": f"${summary['annual_extra_cost']:,.0f}",
        "period": f"{summary['date_from']} to {summary['date_to']}"},
        "findings": _findings_for_prompt(top, sold_by)}
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": f"[{PROMPT_VERSION}]\n{json.dumps(payload, indent=1)}"}]
    try:
        data = chat_json(messages, max_tokens=2000)
        valid_ids = {f.id for f in top}
        data["actions"] = [a for a in data.get("actions", []) if a.get("finding_id") in valid_ids]
        if not data["actions"]:
            raise LLMError("no usable actions")
        data["headline"] = headline(findings, summary)
        return data, True
    except LLMError:
        plan = _fallback(top)
        plan["headline"] = headline(findings, summary)
        return plan, False
