from pathlib import Path
import re

path = Path("../data/processed/explainability_report.md")
text = path.read_text(encoding="utf-8")

# 1. Remove Section 4 definitions block (up to next blank line after event-sweep bullet)
text = re.sub(
    r"\*\*Definitions \(computed before the table\):\*\*\n\n(?:(?!\n\n).)*event-sweep[^\n]*\n",
    "",
    text,
    flags=re.DOTALL,
)

# 2. Remove Section 5 definitions block
text = re.sub(
    r"\*\*Definitions \(computed before the tables\):\*\*\n\n(?:- [^\n]+\n)+",
    "",
    text,
    flags=re.DOTALL,
)

# 3. Remove "Total depot hours" lines (the data lines, not the definition)
text = re.sub(r"^- Total depot hours — min = [^\n]+\n", "", text, flags=re.MULTILINE)

# 4. Remove "Rows in crew_schedule" lines
text = re.sub(r"^- Rows in `crew_schedule\.csv`[^\n]+\n", "", text, flags=re.MULTILINE)

# 5. Remove "Delay model" line in Section 6 (but keep the Phase 2 provenance line in Section 7)
text = re.sub(r"^- Delay model: `clipped_normal`[^\n]+\n", "", text, flags=re.MULTILINE)

path.write_text(text, encoding="utf-8")
print("Done. Removed blocks.")