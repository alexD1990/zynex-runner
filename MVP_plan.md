# Zynex Runner MVP — Arbeidsplan

**Versjon:** 0.1.0  
**Status:** Plan — ikke implementert  
**Scope:** Minimal product for å verifisere at runner og Zynex snakker sammen

---

## Oversikt

Runner er et frittstående script som:
1. Leser en `.yml`-fil med tabeller som skal sjekkes
2. Kaller Zynex `check()` for hver tabell
3. Samler resultater og skriver til en `.json`-fil

---

## Fase 1: Input

### 1.1 — Parse YAML

- Les `.yml`-fil fra disk
- Ekstraher `tables`-nøkkel

**Forventet YAML-format:**
```yaml
tables:
  - "catalog.schema.table_x"
  - "catalog.schema.table_y"
```

---

### 1.2 — Valider input

Følgende må være oppfylt før Zynex kalles. Ved feil stoppes kjøringen med en tydelig feilmelding.

| Sjekk | Feilmelding |
|---|---|
| `tables`-nøkkelen eksisterer | `"Missing required key: tables"` |
| `tables` er en ikke-tom liste | `"tables must be a non-empty list"` |
| Hvert element er en string | `"Each table must be a string, got: <type>"` |

---

### 1.3 — Kall Zynex

For hvert element i `tables`:

```python
check(source=tables[i], render=False)
```

**Feilhåndtering per tabell:**

| Situasjon | Håndtering |
|---|---|
| `ValidationReport` returnert | Fortsett til fase 2 |
| `None` returnert (soft failure) | Merk tabellen som feilet, fortsett til neste |
| `ValueError` kastet | Merk tabellen som feilet, fortsett til neste |

Kjøringen avbrytes **aldri** på grunn av én tabell. Alle tabeller forsøkes.

---

## Fase 2: Output

### 2.1 — Motta Zynex output

- For hver tabell: motta enten `ValidationReport` eller `None`
- `None` → merk tabellen som feilet og fortsett

**`ValidationReport`-struktur (fra Zynex-kontrakt):**
```python
@dataclass
class ValidationReport:
    rows: int
    columns: int
    column_names: List[str]
    results: List[RuleResult]

@dataclass
class RuleResult:
    name: str
    status: str        # "ok" | "warning" | "error" | "skipped" | "not_applicable"
    metrics: Dict[str, Any]
    message: str
```

---

### 2.2 — Transformer til JSON-struktur

#### Toppnivå

```json
{
  "run_id": "a3f8c2d1-4b5e-4f6a-8c9d-1e2f3a4b5c6d",
  "run_timestamp": "2026-02-25T14:32:00Z",
  "modules": ["core_quality"],
  "tables": [ ... ]
}
```

| Felt | Type | Beskrivelse |
|---|---|---|
| `run_id` | `string` (UUID) | Unik ID generert av runner per kjøring |
| `run_timestamp` | `string` (ISO 8601 UTC) | Tidspunkt for kjøringen |
| `modules` | `list[string]` | Moduler sendt til Zynex — hardkodet `["core_quality"]` i MVP |
| `tables` | `list` | Resultater per tabell |

---

#### Per vellykket tabell

```json
{
  "table": "catalog.schema.table_x",
  "status": "ok",
  "rows": 10000,
  "columns": 3,
  "column_names": ["id", "name", "salary"],
  "results": [
    {
      "name": "null_ratio",
      "status": "warning",
      "message": "Null values detected",
      "metrics": {
        "total_nulls": 42,
        "per_column": {
          "name": {"nulls": 42}
        }
      }
    },
    {
      "name": "duplicate_rows",
      "status": "ok",
      "message": "No duplicate full rows",
      "metrics": {
        "total_rows": 10000.0,
        "unique_rows": 10000.0,
        "duplicate_rows": 0.0
      }
    },
    {
      "name": "extreme_values",
      "status": "warning",
      "message": "Extreme values detected in 1 columns (>3.0 stddev)",
      "metrics": {
        "threshold_stddev": 3.0,
        "flagged_columns": {
          "salary": {
            "min": 10.0,
            "max": 9999999.0,
            "avg": 55000.0,
            "std": 12000.0,
            "max_sigma": 8.2
          }
        }
      }
    }
  ]
}
```

| Felt | Type | Kilde |
|---|---|---|
| `table` | `string` | Fra YAML input |
| `status` | `string` | Fra `ValidationReport` via runner |
| `rows` | `int` | `ValidationReport.rows` |
| `columns` | `int` | `ValidationReport.columns` |
| `column_names` | `list[string]` | `ValidationReport.column_names` |
| `results` | `list` | `ValidationReport.results` |
| `results[i].name` | `string` | `RuleResult.name` |
| `results[i].status` | `string` | `RuleResult.status` |
| `results[i].message` | `string` | `RuleResult.message` |
| `results[i].metrics` | `dict` | `RuleResult.metrics` (serialisert as-is) |

---

#### Per feilet tabell

```json
{
  "table": "catalog.schema.table_y",
  "status": "failed",
  "rows": null,
  "columns": null,
  "column_names": null,
  "results": null
}
```

| Felt | Verdi |
|---|---|
| `table` | Fra YAML input |
| `status` | `"failed"` |
| Alle andre felt | `null` |

---

### 2.3 — Skriv til fil

- Sett sammen toppnivå-objekt med alle tabeller under `tables`
- Skriv komplett JSON til `.json`-fil på disk

---

## Merknader

- `metrics`-key-navn er ikke garantert stabile mellom Zynex-versjoner (per kontrakt). Runner serialiserer dem as-is uten transformasjon.
- `modules` er hardkodet til `["core_quality"]` i MVP. YAML-filen støtter ikke modul-konfigurasjon ennå.
- Runner grupperer ikke regler per modul i output — dette er en bevisst begrensning basert på at `ValidationReport` returnerer en flat `results`-liste.