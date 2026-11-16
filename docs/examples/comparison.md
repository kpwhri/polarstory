# Compare healthcare research extracts

This example uses synthetic encounter-level data to demonstrate changes in
age distribution, encounter type, and insurance coding between extracts.

```python
import polars as pl
import polarstory as ps

before = pl.DataFrame({
    'age': [20.0, 30.0, 40.0, None],
    'enctype': ['ED', 'ED', 'IP', None],
    'ins_medicaid': ['Y', 'N', 'U', 'Y'],
})

after = pl.DataFrame({
    'age': [30.0, 40.0, 50.0, 60.0, None],
    'enctype': ['ED', 'IP', 'IP', None, 'ED'],
    'ins_medicaid': ['Y', 'Y', 'N', 'U', 'U'],
})

comparison = ps.compare(before, after)
comparison.write_html('extract_changes.html')
```

The average age changes from 30 to 45 years. The missing-age rate changes
from 25% (1/4) to 20% (1/5): **−5 percentage points**. `U` is treated as
an ordinary category; it is not silently converted to null.

For real clinical extracts, confirm whether each row represents a unique
patient, encounter, claim, or other unit. Review the final HTML report for
small-cell disclosure before sharing with colleagues.
