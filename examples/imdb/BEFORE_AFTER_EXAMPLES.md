# IMDB Data Cleaning: Before & After Examples

## Quick Reference Guide

### Issue 1: Encoding Errors in Column Names

**Before:**
```
Column 1: "IMBD title ID" → "IMBD_Title_ID" (typo in IMBD)
Column 2: "Original titlÊ" → "Original_Title" (corrupted character Ê)
Column 4: "Genrë¨" → "Genre" (corrupted characters ë and ¨)
Column 9: "Unnamed: 8" → DELETED (completely empty)
Column 11: " Votes " → "Votes" (extra spaces)
```

**After:**
✓ All column names properly encoded
✓ Consistent snake_case naming
✓ Clear, descriptive names
✓ No encoding issues

---

### Issue 2: Release Year Format Inconsistency

**Before - Multiple formats mixed:**
| Raw Value | Issue |
|-----------|-------|
| 1995-02-10 | Date format (YYYY-MM-DD) |
| 09 21 1972 | Space-separated format |
| 23 -07-2008 | Invalid format with negative |
| 1975-09-25 | Date format (YYYY-MM-DD) |
| 22 Feb 04 | Text month abbreviation |
| 10-29-99 | Two-digit year (ambiguous) |

**After - Standardized years:**
| Cleaned Value | Data Type |
|---------------|-----------|
| 1995 | Integer |
| 1972 | Integer |
| 2008 | Integer |
| 1975 | Integer |
| 1922 | Integer |
| 1999 | Integer |

**Solution:** Extract 4-digit year using regex, validate range 1800-2024

---

### Issue 3: Income Formatting Problems

**Before - Multiple issues:**
```
$ 28815245              ✓ Clean (converted to 28,815,245)
$ 246120974             ✓ Clean (converted to 246,120,974)
$ 1005455211            ✓ Clean (converted to 1,005,455,211)
$ 4o8,035,783           ✗ Typo: "4o8" should be "408"
$ 222831817             ✓ Clean (converted to 222,831,817)
$ 576                   ✓ Clean (converted to 576)
$ 25,252,481            ✗ US format decimals with commas
```

**After - Standardized to float:**
```
28815245.0
246120974.0
1005455211.0
408035783.0
222831817.0
576.0
25252481.0
```

**Solution:** Remove symbols, detect decimal format, fix typos, convert to float

---

### Issue 4: Votes Number Format (European vs US)

**Before - European thousands separators:**
```
2.278.845   ← Dots as thousands separators (European)
1.572.674   ← Should be 1,572,674 in US format
2.241.615   ← Should be 2,241,615 in US format
1.098.714   ← Should be 1,098,714 in US format
1.780.147   ← Should be 1,780,147 in US format
```

**After - Standardized to integer:**
```
2278845
1572674
2241615
1098714
1780147
```

**Solution:** Remove all dots and commas, extract numeric values only

---

### Issue 5: Score Formatting & Special Characters

**Before - Multiple issues:**
```
9.3         ✓ Valid
9.2         ✓ Valid
9.          ✗ Incomplete (9.)
9,.0        ✗ Mixed comma and dot (9,.0)
8,9f        ✗ Letter character 'f' and comma
8.9         ✓ Valid
8..8        ✗ Double dots (8..8)
8:8         ✗ Colon instead of dot
8.8         ✓ Valid
++8.7       ✗ Plus signs
8,7e-0      ✗ Scientific notation format
```

**After - Standardized to float:**
```
9.3
9.2
9.0
9.0
8.9
8.9
8.8
8.8
8.7
8.7
```

**Solution:** Remove special characters, normalize decimal separators, validate 0-10 range

---

### Issue 6: Country Name Inconsistencies

**Before - Typos and variations:**
```
USA             ✓ Correct
US              ✗ Abbreviation (should be USA)
New Zesland     ✗ Typo (should be New Zealand)
UK              ✗ Abbreviation (should be United Kingdom)
USA.            ✗ Extra period
Italy           ✓ Correct
Italy1          ✗ Number appended
US.             ✗ Abbreviation with period
```

**After - Standardized:**
```
USA
USA
New Zealand
United Kingdom
USA
Italy
Italy
USA
```

**Solution:** Apply corrections dictionary for common misspellings

---

### Issue 7: Duration Value Issues

**Before - Mixed formats and invalid values:**
```
142         ✓ Valid
175         ✓ Valid
152         ✓ Valid
220         ✓ Valid
(blank)     ✗ Empty/spaces
Nan         ✗ Text "Nan"
96          ✓ Valid
178c        ✗ Character suffix
-           ✗ Dash/invalid
Not Applicable  ✗ Text value
```

**After - Standardized to integer (minutes):**
```
142
175
152
220
129 (filled with median)
129 (filled with median)
96
178
129 (filled with median)
129 (filled with median)
```

**Solution:** Extract numeric values, validate 10-500 range, fill missing with median

---

### Issue 8: Missing Content Rating

**Before:**
```
R
PG-13
Not Rated
Approved
PG
(NULL)      ✗ Missing value (24 instances, 23.76%)
Unrated
G
```

**After - Filled with meaningful default:**
```
R
PG-13
Not Rated
Approved
PG
Not Rated   (filled missing)
Unrated
G
```

**Solution:** Fill missing values with 'Not Rated' (appropriate default)

---

### Issue 9: Missing Critical Values

**Before:**
```
Row 1:  ✓ Complete
Row 2:  ✓ Complete
Row 3:  ✗ Missing IMDB_Title_ID
Row 4:  ✓ Complete
Row 5:  ✗ Missing Title
...
```

**After - Only complete rows retained:**
```
Row 1:  ✓ Complete (kept)
Row 2:  ✓ Complete (kept)
Row 3:  ✗ Removed (missing IMDB_Title_ID)
Row 4:  ✓ Complete (kept)
Row 5:  ✗ Removed (missing Title)
...
```

**Solution:** Remove rows with missing critical values

---

## Complete Example: Movie Record Transformation

### Example Movie: Inception

**Before Cleaning:**
```
IMDB_Title_ID: tt1375666
Title: Inception
Release_Year: 2010-09-24     ← Full date, needs year extraction
Genre: Action, Adventure, Sci-Fi
Duration: 148               ← Already clean
Country: USA                ← Already clean
Content_Rating: PG-13       ← Already clean
Director: Christopher Nolan ← Already clean
Income: $ 1005455211        ← Has currency symbol
Votes: 2.002.816            ← European number format
Score: 8.8                  ← Already clean
```

**After Cleaning:**
```
IMDB_Title_ID: tt1375666    ← Unchanged
Title: Inception             ← Unchanged
Release_Year: 2010          ← Extracted from date (integer)
Genre: Action, Adventure, Sci-Fi ← Unchanged
Duration: 148               ← Already valid (integer)
Country: USA                ← Unchanged
Content_Rating: PG-13       ← Unchanged
Director: Christopher Nolan ← Unchanged
Income: 1005455211.0        ← Symbol removed, converted to float
Votes: 2002816              ← Normalized to integer
Score: 8.8                  ← Already valid (float)
```

---

## Summary: Data Transformation Results

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Rows | 101 | 95 | -6 (5.94%) |
| Columns | 12 | 11 | -1 empty |
| Missing Values | 50+ | 0 | -100% |
| Encoding Issues | 4 | 0 | Fixed |
| Format Issues | 25+ | 0 | Fixed |
| Data Completeness | ~95% | 100% | +5% |
| Usability | Low | High | ✓ |

---

## Data Validation Report

### Validation Checks Performed ✓

- [x] Column name encoding and format
- [x] Data type consistency
- [x] Missing value detection and handling
- [x] Value range validation
- [x] Format standardization
- [x] Special character removal
- [x] Duplicate detection
- [x] Null value elimination

### All Checks PASSED ✓

The cleaned dataset is validated and ready for analysis.

