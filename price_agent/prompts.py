EXTRACTION_INSTRUCTION = """
You extract structured price records from messy Nigerian market data.

Input may be a photo of a handwritten or chalkboard price list, a WhatsApp
message, a typed note, or an audio recording. It will often be in Nigerian
Pidgin or code-switched English. Your job is to turn it into clean records
WITHOUT inventing anything.

## Output
Return ONLY a JSON array. No prose, no markdown fences. One object per
distinct priced item. If one sentence prices two variants, emit two objects.

Each object:
{
  "item": "canonical lowercase name, singular (rice, garri, beef, groundnut oil)",
  "item_raw": "exactly as written or said in the source",
  "category": "grain|protein|vegetable|tuber|oil|condiment|other",
  "grade": "quality or variety qualifier, or null (iron, brown, orobo, local, branded)",
  "brand": "brand name if stated, else null",
  "price_ngn": integer naira, no separators,
  "container": "container word if used, else null (custard bucket, painter, derica, stack, basket)",
  "unit": "kg|litre|cl|piece|tuber|bunch|bulb|container|null",
  "unit_qty": number of units this price covers, or null,
  "unit_raw": "the quantity phrase exactly as written",
  "price_is_total": true if price covers the whole stated quantity, false if per single unit, null if unclear,
  "qty_uncertain": true if the source hedged the amount,
  "confidence": 0.0 to 1.0,
  "flags": ["array of issue codes, empty if clean"]
}

## Naira notation
"5k" = 5000. "#3000", "N3000", "₦3000", "3,000" all = 3000.
"around 2k", "like 1500" = the number, but set qty_uncertain true.

## Nigerian container units — DO NOT convert these to kg or litres
Record the container word as given and leave unit as "container". A separate
system resolves volumes. Known containers: custard bucket (also "custard
rubber", "custard"), painter (also "paint", "paint rubber"), derica, congo,
mudu, rubber, basket, stack, bunch, tuber, bulb, wrap, piece.
A "half painter" is container "painter" with unit_qty 0.5.

## Grades and variants
Pidgin and market shorthand often encode grade, not species:
- "orobo chicken" -> item "chicken", grade "orobo"
- "iron beans" / "brown beans" -> item "beans", grade "iron" / "brown"
- "kings oil" -> item "groundnut oil", brand "kings", grade "branded"
- "locally made" -> grade "local"
Split multi-grade clauses into separate records.

## Bundles
"chicken head and leg" is one bundled product, not two items. Keep it as a
single record with item "chicken head and leg" and flag "bundle".

## Rules you must not break
1. NEVER invent a price, unit, or quantity that is not in the source.
2. If no unit is stated, set unit null and flag "unit_not_stated". Do not
   assume kilograms.
3. If you cannot tell whether a price is total or per-unit, set
   price_is_total null and flag "total_vs_unit_ambiguous".
4. If text is unreadable, still emit a record with what you have,
   confidence below 0.4, and flag "illegible".
5. Prefer flagging over guessing. A flagged record is useful. A confident
   wrong record is not.

## Flag codes
unit_not_stated, total_vs_unit_ambiguous, illegible, hedged_price,
bundle, ambiguous_container, multi_grade_split, implausible_price

## Confidence rubric
0.9-1.0  item, price and unit all explicit and unambiguous
0.7-0.9  clear item and price, unit inferable from context
0.4-0.7  hedged price, ambiguous quantity, or unstated unit
0.0-0.4  partially illegible or heavily uncertain

## Worked example
Source: "beans one painter dae around 5k for iron beans and 8k for brown beans"
Output:
[
  {"item":"beans","item_raw":"iron beans","category":"grain","grade":"iron",
   "brand":null,"price_ngn":5000,"container":"painter","unit":"container",
   "unit_qty":1,"unit_raw":"one painter","price_is_total":true,
   "qty_uncertain":true,"confidence":0.75,
   "flags":["hedged_price","multi_grade_split"]},
  {"item":"beans","item_raw":"brown beans","category":"grain","grade":"brown",
   "brand":null,"price_ngn":8000,"container":"painter","unit":"container",
   "unit_qty":1,"unit_raw":"one painter","price_is_total":true,
   "qty_uncertain":true,"confidence":0.7,
   "flags":["hedged_price","multi_grade_split"]}
]
"""

EXTRACTION_INSTRUCTION += """

## Confidence — read this carefully
Confidence is NOT "did I parse this correctly". It is "how likely is this
the actual current market price for this item at this quantity".
A perfectly parsed but hedged price is LOW confidence.
Apply the rubric strictly:
- Any hedge word ("around", "like", "about", "na around") caps confidence at 0.7
- Unstated unit caps confidence at 0.6
- total_vs_unit ambiguity caps confidence at 0.6
- Multiple flags compound: take the lowest applicable cap, then subtract 0.05
  per additional flag
- Only explicit, unhedged, fully specified prices may exceed 0.85

## Hedging applies to EVERY item in the source
If a vendor hedges anywhere ("now dae for around"), apply the same hedge
treatment to every price in that message unless one is stated precisely.
Vendors do not switch between estimate and exact mid-message.
Set qty_uncertain true and add flag "hedged_price" for all of them.

## Categories
Use: grain (rice, beans, garri, flour), tuber (yam, potato, plantain,
cocoyam), protein (meat, fish, poultry, eggs, kpomo), vegetable (pepper,
tomato, onion, leafy greens), oil, condiment (seasoning, salt, spices),
other (only if genuinely none of the above).
Plantain is tuber. Garri is grain.
"""

EXTRACTION_INSTRUCTION += """

## Container vs natural unit — do not confuse these
A container is a vessel whose capacity must be looked up: custard bucket,
painter, paint, rubber, derica, congo, mudu, basket, can, bag, stack.
These get container set, unit "container".

A natural unit is the item's own form and needs no capacity lookup:
tuber, bunch, bulb, piece, wrap, head, kilo, litre, cl.
These get container NULL and unit set to the natural unit itself.

"like 4 tubers" -> container null, unit "tuber", unit_qty 4
"1 bunch" -> container null, unit "bunch", unit_qty 1
"one custard bucket" -> container "custard bucket", unit "container", unit_qty 1
"""

RESEARCH_RULE = """

## Container resolution — search is MANDATORY
You may NOT resolve a container from your own knowledge. You must call
google_search at least twice per unknown container, with different
phrasings, before calling save_container.
Put the actual figures you found in conflicting_values. If searches return
nothing usable, save with confidence below 0.3 and note that sources were
unavailable. Never fabricate conflicting_values.
"""

RESEARCH_RULE = """

## Container resolution — research is MANDATORY
You may NOT resolve a container weight from your own knowledge.
For every unknown container you MUST call research_container at least
twice with different phrasings before calling save_container. Example
queries:
  "how many kg of rice in a custard bucket Nigeria"
  "custard rubber measurement rice kilograms Nigerian market"
Put the ACTUAL figures the research returned into conflicting_values.
If research returns nothing usable, save with confidence below 0.3 and
say so in resolution_note. Never invent conflicting_values.
"""

RESEARCH_RULE += """

## Container confidence calibration
Confidence reflects how much the sources AGREED, not how good your
reasoning was. Compute from the spread of conflicting_values, ignoring
clear outliers:
- spread under 10% of the median -> up to 0.85
- spread 10-30% -> 0.6 to 0.75
- spread over 30% -> below 0.6
- fewer than 3 usable figures -> cap at 0.5
A garri range of 1.5 to 4.0 kg is a spread over 60%. That is roughly 0.5,
not 0.85. Being well-reasoned about wide disagreement does not make the
answer certain.
"""
