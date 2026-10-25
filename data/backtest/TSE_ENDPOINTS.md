# TSE result endpoints for the backtest notebook

Checked on 2026-10-25 between 00:20 and 00:25 GMT-3 (03:20 to 03:25 UTC) with `curl -I` and small GETs. All times below are GMT-3 unless they are marked as HTTP `Last-Modified` (GMT).

---

## (a) 2022 runoff by municipality: TSE open-data CDN

Base: `https://cdn.tse.jus.br/estatistica/sead/odsele/`

All files are ZIPs of `;`-separated, double-quoted, **Latin-1** CSVs with a header row. Rows are per **municipality x electoral zone** (`NR_ZONA`), so you sum over zones to get municipality totals. `CD_MUNICIPIO` is the 5-digit **TSE** code, not the 7-digit IBGE code; see the crosswalk below. Abroad votes are under `SG_UF = "ZZ"`. Every file holds both rounds: filter on `NR_TURNO = 2` (or on `CD_ELEICAO = 545`; round 1 is 544) and `CD_CARGO = 1` (Presidente).

Note that TSE regenerated the 2022 files on 2026-10-24 (`DT_GERACAO = 24/10/2026`). If you need a byte-stable artifact, hash what you download.

| Purpose | URL | Size (Content-Length) | Last-Modified (GMT) |
|---|---|---|---|
| Candidate votes (canonical) | `votacao_candidato_munzona/votacao_candidato_munzona_2022.zip` | 642,592,078 B | Sat, 24 Oct 2026 07:24:58 |
| Party votes (equal to candidate votes for president; much smaller) | `votacao_partido_munzona/votacao_partido_munzona_2022.zip` | 26,046,497 B | (not recorded) |
| Electorate, turnout, blank, null | `detalhe_votacao_munzona/detalhe_votacao_munzona_2022.zip` | 4,429,327 B | Sat, 24 Oct 2026 06:52:18 |

### Candidate file: use only the `_BR` member

`votacao_candidato_munzona_2022.zip` contains `votacao_candidato_munzona_2022_<UF>.csv` for every state, plus `_BR.csv` and `_BRASIL.csv`. `votacao_candidato_munzona_2022_BR.csv` is the **presidential-only** file: 38,081,808 bytes uncompressed and 2,044,812 bytes deflated (method 8). `_BRASIL.csv` is every office together, at 4.3 GB uncompressed.

You don't need the 642 MB download. The `_BR` member's local header sits at byte offset **120,874,990**, so an HTTP range request fetches only about 2 MB:

```
curl -r 120874990-122920032 -o br_member.bin \
  https://cdn.tse.jus.br/estatistica/sead/odsele/votacao_candidato_munzona/votacao_candidato_munzona_2022.zip
# local header: 30 bytes + name + extra, then raw DEFLATE -> zlib.decompressobj(-15)
```

This was tested: it inflated to exactly 38,081,808 bytes. If TSE regenerates the ZIP, re-read the offset from the central directory by fetching the last ~200 KB with `curl -r -200000` (the parser is `scripts/zipcd.py`).

Columns needed for the runoff (`votacao_candidato_munzona_2022_BR.csv`):

| Column | Use |
|---|---|
| `NR_TURNO` | `2` = runoff |
| `CD_ELEICAO` | `545` = 2022 runoff (`544` = first round) |
| `CD_CARGO` / `DS_CARGO` | `1` / `Presidente` |
| `SG_UF` | state; `ZZ` = abroad |
| `CD_MUNICIPIO`, `NM_MUNICIPIO` | TSE municipality code and name |
| `NR_ZONA` | electoral zone; sum over this |
| `NR_CANDIDATO`, `NM_URNA_CANDIDATO`, `SG_PARTIDO` | 13 / LULA / PT; 22 / JAIR BOLSONARO / PL |
| `QT_VOTOS_NOMINAIS_VALIDOS` | **candidate votes; use this one** (`QT_VOTOS_NOMINAIS` also exists) |
| `ST_VOTO_EM_TRANSITO` | in-transit flag; keep all rows |

Check (round 2, summed over zones): LULA **60,345,999**, JAIR BOLSONARO **58,206,354**, across **5,751** municipality codes (Brazil plus abroad). This matches the party file.

### Party file (lighter alternative)

The member is `votacao_partido_munzona_2022_BR.csv` (president only). It has the same keys plus `SG_PARTIDO` and `QT_VOTOS_NOMINAIS_VALIDOS`. For president, the PT and PL nominal votes equal the candidate votes. In the 2002 to 2014 files the vote column is named `QT_VOTOS_NOMINAIS`.

### Turnout file

The member is `detalhe_votacao_munzona_2022_BR.csv`. Use these columns: `QT_APTOS` (electorate), `QT_COMPARECIMENTO` (turnout), `QT_ABSTENCOES`, `QT_VOTOS_BRANCOS`, `QT_TOTAL_VOTOS_NULOS`, `QT_VOTOS_NOMINAIS_VALIDOS` (valid votes) and `QT_TOTAL_VOTOS_VALIDOS`.

National round-2 totals: electorate 156,454,011; turnout 124,252,796 (79.42%); valid votes 118,552,353.

### Same files for other years

Swap the year in the file names for 2002, 2006, 2010, 2014 or 2018. `results.csv` was built from the `_BR` members of `votacao_partido_munzona_<year>.zip` and `detalhe_votacao_munzona_<year>.zip`. Election codes: 2002 = 200201/200202, 2006 = 2006001/2006002, 2010 = 37/38, 2014 = 143/144, 2018 = 295/296, 2022 = 544/545.

### TSE to IBGE municipality crosswalk

`https://resultados.tse.jus.br/oficial/ele2026/6257/config/mun-e006257-cm.json` (plain JSON) maps `abr[].mu[].cd` (TSE code) to `cdi` (IBGE code). Abroad entries have an empty `cdi`.

### Legacy 2022 live-results paths are gone

`https://resultados.tse.jus.br/oficial/ele2022/545/dados-simplificados/br/br-c0001-e000545-r.json` and the matching 544 path now return **404** (`NoSuchKey`). Use the CDN files above for 2022.

---

## (b) 2026: resultados.tse.jus.br (signed JWS files)

### Election codes, from the config file

`https://resultados.tse.jus.br/oficial/comum/config/ele-c.json` (config generated 18/10/2026 12:38:11):

| Pleito | Date | Election code | Name | Turno | Offices / scope |
|---|---|---|---|---|---|
| 3220 | 04/10/2026 | **6257** (`cdt2` = 6258) | Eleição Ordinária Federal - 2026 1º Turno | 1 | Presidente, `br` |
| 3221 | 25/10/2026 | **6258** | **Eleição Ordinária Federal - 2026 2º Turno** | 2 | Presidente, `br` |
| 3221 | 25/10/2026 | 6260 | Eleição Ordinária Estadual - 2026 2º Turno | 2 | Governador, AM and RN only |

**The 2026 presidential runoff code is 6258** (`e006258` in file names).

### Path templates

The config's `arq` list gives `<base>/<ambiente>/<ciclo>/<cd_eleicao>/dados/<uf>`, with base `https://resultados.tse.jus.br`, ambiente `oficial` and ciclo `ele2026`. `uf` is lowercase. `cargo` is 4 digits (`c0001` = Presidente) and the election code is 6 digits (`e006257`, `e006258`).

| Level | 1st round (tested) | Runoff (tested) |
|---|---|---|
| National | `/oficial/ele2026/6257/dados/br/br-c0001-e006257-u.jws` | `/oficial/ele2026/6258/dados/br/br-c0001-e006258-u.jws` |
| State | `/oficial/ele2026/6257/dados/{uf}/{uf}-c0001-e006257-u.jws` (e.g. `sp`) | `/oficial/ele2026/6258/dados/{uf}/{uf}-c0001-e006258-u.jws` |
| Abroad aggregate | `/oficial/ele2026/6257/dados/zz/zz-c0001-e006257-u.jws` | `/oficial/ele2026/6258/dados/zz/zz-c0001-e006258-u.jws` (200) |
| **Municipality** | `/oficial/ele2026/6257/dados/{uf}/{uf}{cdmun}-c0001-e006257-u.jws` (e.g. `sp/sp71072-...` for São Paulo, `ac/ac01120-...`) | `/oficial/ele2026/6258/dados/{uf}/{uf}{cdmun}-c0001-e006258-u.jws` (e.g. `sp/sp71072-...`, `zz/zz29254-...` for Abidjan) |
| Municipality list | `/oficial/ele2026/6257/config/mun-e006257-cm.json` (also `.jws`) | `/oficial/ele2026/6258/config/mun-e006258-cm.json` (also `.jws`) |
| Turnout by sub-area (no candidate votes) | `/oficial/ele2026/6257/dados/{uf}/{uf}-e006257-ab.jws` (per municipality); `br-e006257-ab.jws` (per state) | `/oficial/ele2026/6258/dados/{uf}/{uf}-e006258-ab.jws`; `br-e006258-ab.jws` |

`{cdmun}` is the 5-digit TSE code from the `-cm.json` file. Both rounds list **5,757** entries: 28 `abr` groups, 186 of them abroad (`zz`). For a full municipal pull, iterate `abr[].cd` x `abr[].mu[].cd`. That is 5,757 GETs of about 4 KB (runoff) to about 12 KB (1st round) each.

The `-r.json`, `-v.json` and `-f.jws` variants that 2022 used return **404** for 2026. The only per-office results file is `-u.jws`.

### File format

The `.jws` files are **JWS compact serialization**: `base64url(header).base64url(payload).signature`. The header is `{"kid":"sNbt9Q_fLS65zE1_ZLNV-XRRwPY","typ":"JOSE","alg":"EdDSA"}` and the response is served as `application/json`.

To read a file, split on `.`, base64url-decode part 2 (pad with `=`) and parse it as UTF-8 JSON. I did not locate TSE's public key (JWKS) for this `kid`, so the signature was **not verified**.

```python
import base64, json
def read_jws(text):
    payload = text.strip().split('.')[1]
    return json.loads(base64.urlsafe_b64decode(payload + '=' * (-len(payload) % 4)))
```

Numbers are **strings**. Percentages use a **decimal comma** (`"47,03"`); the `...n` fields carry more precision (`"47,027772356"`).

### JSON fields in a `{uf}{cdmun}-c0001-e00NNNN-u.jws` payload

Top-level fields:

| Field | Meaning |
|---|---|
| `ele` | Election code |
| `t` | Round |
| `tpabr` / `cdabr` | Scope: `br` / `uf` / `mu`, and its code (e.g. `mu` / `71072`) |
| `dg` / `hg` | File generation date and time |
| `dt` / `ht` | Totalization date and time (empty before counting) |
| `tf` | Final totalization, `s`/`n` |
| `s` | Polling sections: `ts` total, `st` totalized, `pst` % totalized |
| `e` | Electorate: `te` electorate, `c` turnout, `pc` % turnout, `a` abstention |
| `v` | Votes: `tv` total votes, `vv` valid, `vnom` nominal, `vb` blank, `tvn` total null, `vn` null, `vnt` technical null |

Candidate votes are under `carg[0]` (`cd` = 1, Presidente), in `agr[]` (coalition or party groups), then `par[]` (party: `n`, `sg`), then `cand[]`:

| `cand` field | Meaning |
|---|---|
| `n` | Ballot number: 13 = Lula, 22 = Flávio Bolsonaro |
| `nm` / `nmu` | Full name / ballot name |
| `sqcand` | Candidate sequence id |
| **`vap`** | **Votes counted (candidate votes in this municipality)** |
| `pvap` / `pvapn` | % of valid votes |
| `e` | Elected, `s`/`n` |
| `st` | Status, e.g. "2º turno" or "Não eleito" |
| `seq` | Rank |

The party-level fields `tvtn` and `tvan` repeat the totals.

Sanity checks from the files:

- **1st round, national** (`br-c0001-e006257-u.jws`, dg 05/10/2026 12:51:47, 100.00% of 499,248 sections): Flávio Bolsonaro (PL) 56,104,503 = 47.03%; Lula (PT) 53,879,538 = 45.16%; valid votes 119,300,788; turnout 125,275,835 of 158,745,502 (78.92%).
- **1st round, São Paulo city** (`sp/sp71072-c0001-e006257-u.jws`): Lula 3,052,349 (46.58%), Flávio Bolsonaro 2,760,747 (42.13%).

### Are the 2026 runoff files published yet?

**Yes, as zero-filled placeholders.** They will fill in after polls close today.

The national runoff file `6258/dados/br/br-c0001-e006258-u.jws` returns 200 (3,993 bytes; Last-Modified Sat, 24 Oct 2026 22:20:12 GMT; payload `dg` 24/10/2026 19:19:13). Its contents:

- Section counts `ts` = 499,248 and `st` = 0 (`pst` = 0,00); `tf` = `n`; `dt` and `ht` are empty.
- Both candidates are listed with `vap` = "0": Lula (13, PT) and Flávio Bolsonaro (22, PL).
- All `v` vote fields are 0; `e.te` = 158,745,502.

State and municipal runoff files (e.g. `sp/sp71072-c0001-e006258-u.jws`, `dg` 13/10/2026) and the runoff municipality list (`mun-e006258-cm.json`, dg 15/10/2026) are also already up with zeros.

Polls close on **25 Oct 2026 at 17:00 GMT-3** (all states vote on Brasília time), and TSE starts releasing totals after that. To detect real data, poll the national file and watch `s.st` / `s.pst` and `dg` / `hg`. The server sends `cache-control: max-age=22` and `x-ratelimit-limit: 5000, 5000;w=1`, so poll politely, for example every 30 to 60 seconds for the national and state files.
