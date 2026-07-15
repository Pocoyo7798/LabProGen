"""PubChem REST helpers (compound autocomplete and properties)."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from src.core.config import KEY_BIGSMILES, KEY_FORMULA, KEY_INCHI, KEY_NAME, KEY_SMILES

PUBCHEM_AUTOCOMPLETE_BASE = (
    "https://pubchem.ncbi.nlm.nih.gov/rest/autocomplete/compound"
)
PUBCHEM_PUG_BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound"
PUBCHEM_SDQ_SPHINXQL = "https://pubchem.ncbi.nlm.nih.gov/sdq/sphinxql.cgi"
PUBCHEM_AUTOCOMPLETE_MIN_LEN = 3
DEFAULT_AUTOCOMPLETE_LIMIT = 10
PUBCHEM_SEARCH_BATCH_SIZE = 5
REQUEST_TIMEOUT_SEC = 15
USER_AGENT = "LabProGen/1.0 (chemical autocomplete; +https://github.com/)"

_COMPOUND_PROPERTIES = "MolecularFormula,ConnectivitySMILES,InChI,IUPACName"


@dataclass(frozen=True)
class CompoundAutocompletePage:
    terms: list[str]
    total: int


@dataclass(frozen=True)
class CompoundSearchPage:
    """PubChem compound search hits (CIDs) for one query, as on pubchem.ncbi.nlm.nih.gov search."""

    cids: list[int]
    total: int


@dataclass(frozen=True)
class PubChemCompoundRecord:
    compound_name: str
    cid: int | None = None
    molecular_formula: str = ""
    connectivity_smiles: str = ""
    inchi: str = ""
    iupac_name: str = ""


def build_compound_autocomplete_url(search_term: str, *, limit: int = DEFAULT_AUTOCOMPLETE_LIMIT) -> str:
    encoded = urllib.parse.quote(search_term.strip(), safe="")
    return f"{PUBCHEM_AUTOCOMPLETE_BASE}/{encoded}/json?limit={int(limit)}"


def build_compound_cids_url(compound_name: str) -> str:
    encoded = urllib.parse.quote(compound_name.strip(), safe="")
    return f"{PUBCHEM_PUG_BASE}/name/{encoded}/cids/JSON"


def build_compound_property_url(compound_name: str) -> str:
    encoded = urllib.parse.quote(compound_name.strip(), safe="")
    return f"{PUBCHEM_PUG_BASE}/name/{encoded}/property/{_COMPOUND_PROPERTIES}/JSON"


def build_cid_property_url(cids: list[int]) -> str:
    cid_list = ",".join(str(int(cid)) for cid in cids)
    return f"{PUBCHEM_PUG_BASE}/cid/{cid_list}/property/{_COMPOUND_PROPERTIES}/JSON"


def _http_get_json(url: str) -> object | None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SEC) as response:
            raw = response.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError, OSError, urllib.error.HTTPError):
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def parse_compound_autocomplete_payload(data: object) -> list[str]:
    if not isinstance(data, dict):
        return []
    dictionary_terms = data.get("dictionary_terms")
    if not isinstance(dictionary_terms, dict):
        return []
    compound = dictionary_terms.get("compound")
    if not isinstance(compound, list):
        return []
    return [str(term) for term in compound if str(term).strip()]


def parse_compound_autocomplete_page(data: object) -> CompoundAutocompletePage:
    if not isinstance(data, dict):
        return CompoundAutocompletePage(terms=[], total=0)
    terms = parse_compound_autocomplete_payload(data)
    total_raw = data.get("total", len(terms))
    try:
        total = int(total_raw)
    except (TypeError, ValueError):
        total = len(terms)
    return CompoundAutocompletePage(terms=terms, total=max(total, len(terms)))


def parse_cid_list_payload(data: object) -> list[int]:
    if not isinstance(data, dict):
        return []
    if "Fault" in data:
        return []
    identifier_list = data.get("IdentifierList")
    if not isinstance(identifier_list, dict):
        return []
    raw_cids = identifier_list.get("CID")
    if not isinstance(raw_cids, list):
        return []
    cids: list[int] = []
    for value in raw_cids:
        try:
            cids.append(int(value))
        except (TypeError, ValueError):
            continue
    return cids


def fetch_compound_autocomplete(
    search_term: str,
    *,
    limit: int = DEFAULT_AUTOCOMPLETE_LIMIT,
) -> list[str]:
    """Return compound dictionary suggestions from PubChem autocomplete."""
    return fetch_compound_autocomplete_page(search_term, limit=limit).terms


def fetch_compound_autocomplete_page(
    search_term: str,
    *,
    limit: int,
) -> CompoundAutocompletePage:
    query = search_term.strip()
    if len(query) < PUBCHEM_AUTOCOMPLETE_MIN_LEN:
        return CompoundAutocompletePage(terms=[], total=0)

    url = build_compound_autocomplete_url(query, limit=limit)
    payload = _http_get_json(url)
    if payload is None:
        return CompoundAutocompletePage(terms=[], total=0)
    return parse_compound_autocomplete_page(payload)


def build_sdq_compound_search_query(
    term: str,
    *,
    start: int,
    limit: int,
) -> str:
    """SDQ/SphinxQL query for PubChem website compound text search (1-based start)."""
    query = {
        "select": "cid",
        "collection": "compound",
        "where": {"ands": [{"*": term.strip()}]},
        "order": ["relevancescore,desc"],
        "start": max(int(start), 1),
        "limit": max(int(limit), 1),
    }
    return json.dumps(query, separators=(",", ":"))


def build_sdq_compound_search_url(term: str, *, start: int, limit: int) -> str:
    encoded_query = urllib.parse.quote(
        build_sdq_compound_search_query(term, start=start, limit=limit),
        safe="",
    )
    return f"{PUBCHEM_SDQ_SPHINXQL}?infmt=json&outfmt=json&query={encoded_query}"


def parse_sdq_cid_page(data: object) -> CompoundSearchPage:
    """Parse PubChem SphinxQL compound search JSON (website Compounds tab)."""
    if not isinstance(data, dict):
        return CompoundSearchPage(cids=[], total=0)
    output_set = data.get("SDQOutputSet")
    if not isinstance(output_set, list) or not output_set:
        return CompoundSearchPage(cids=[], total=0)
    block = output_set[0]
    if not isinstance(block, dict):
        return CompoundSearchPage(cids=[], total=0)

    cids: list[int] = []
    rows = block.get("rows")
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            raw_cid = row.get("cid")
            if raw_cid is None:
                raw_cid = row.get("CID")
            try:
                cids.append(int(raw_cid))
            except (TypeError, ValueError):
                continue

    try:
        total = int(block.get("totalCount", len(cids)))
    except (TypeError, ValueError):
        total = len(cids)
    return CompoundSearchPage(cids=cids, total=max(total, 0))


def fetch_compound_search_cids_page(
    query: str,
    *,
    start: int = 0,
    batch_size: int = PUBCHEM_SEARCH_BATCH_SIZE,
) -> CompoundSearchPage:
    """One page of compound CIDs for a PubChem text search (website Compounds tab order)."""
    term = query.strip()
    if len(term) < PUBCHEM_AUTOCOMPLETE_MIN_LEN:
        return CompoundSearchPage(cids=[], total=0)

    url = build_sdq_compound_search_url(
        term,
        start=int(start) + 1,
        limit=int(batch_size),
    )
    payload = _http_get_json(url)
    if payload is None:
        return CompoundSearchPage(cids=[], total=0)
    return parse_sdq_cid_page(payload)


def parse_compound_property_rows(
    data: object,
    compound_name: str,
) -> list[PubChemCompoundRecord]:
    if not isinstance(data, dict):
        return []
    table = data.get("PropertyTable")
    if not isinstance(table, dict):
        return []
    properties = table.get("Properties")
    if not isinstance(properties, list):
        return []

    records: list[PubChemCompoundRecord] = []
    for row in properties:
        if not isinstance(row, dict):
            continue
        cid = row.get("CID")
        try:
            cid_value = int(cid) if cid is not None else None
        except (TypeError, ValueError):
            cid_value = None
        records.append(
            PubChemCompoundRecord(
                compound_name=compound_name,
                cid=cid_value,
                molecular_formula=str(row.get("MolecularFormula", "") or "").strip(),
                connectivity_smiles=str(row.get("ConnectivitySMILES", "") or "").strip(),
                inchi=str(row.get("InChI", "") or "").strip(),
                iupac_name=str(row.get("IUPACName", "") or "").strip(),
            )
        )
    return records


def parse_compound_property_payload(data: object, compound_name: str) -> PubChemCompoundRecord | None:
    rows = parse_compound_property_rows(data, compound_name)
    return rows[0] if rows else None


def fetch_compound_properties_by_cids(
    cids: list[int],
    compound_name: str,
) -> list[PubChemCompoundRecord]:
    if not cids:
        return []
    payload = _http_get_json(build_cid_property_url(cids))
    if payload is None:
        return []
    if isinstance(payload, dict) and "Fault" in payload:
        return []
    return parse_compound_property_rows(payload, compound_name)


def fetch_compound_properties_by_name(compound_name: str) -> PubChemCompoundRecord | None:
    name = compound_name.strip()
    if not name:
        return None
    payload = _http_get_json(build_compound_property_url(name))
    if payload is None:
        return None
    if isinstance(payload, dict) and "Fault" in payload:
        return None
    return parse_compound_property_payload(payload, name)


def map_pubchem_to_form_fields(
    record: PubChemCompoundRecord | None,
    compound_name: str,
    *,
    visible_keys: set[str],
    chemical_type: str,
) -> dict[str, str]:
    """Map PubChem data to LabProGen chemical param keys (visible fields only)."""
    visible = {str(k).lower() for k in visible_keys}
    mapped: dict[str, str] = {}

    if KEY_NAME in visible:
        mapped[KEY_NAME] = compound_name

    if record is None:
        return mapped

    if KEY_FORMULA in visible and record.molecular_formula:
        mapped[KEY_FORMULA] = record.molecular_formula
    if KEY_INCHI in visible and record.inchi:
        mapped[KEY_INCHI] = record.inchi

    smiles = record.connectivity_smiles
    if smiles:
        if chemical_type == "Polymers":
            if KEY_BIGSMILES in visible:
                mapped[KEY_BIGSMILES] = smiles
        elif KEY_SMILES in visible:
            mapped[KEY_SMILES] = smiles

    return mapped


def fetch_compound_search_batch(
    selected_name: str,
    *,
    start: int = 0,
    batch_size: int = PUBCHEM_SEARCH_BATCH_SIZE,
) -> tuple[CompoundSearchPage, list[PubChemCompoundRecord | None]]:
    """Load a batch of compound records for one PubChem search query (SDQ + PUG properties)."""
    name = selected_name.strip()
    page = fetch_compound_search_cids_page(name, start=start, batch_size=batch_size)
    records = fetch_compound_properties_by_cids(page.cids, name) if page.cids else []
    if len(records) < len(page.cids):
        records_by_cid = {record.cid: record for record in records if record.cid is not None}
        records = [records_by_cid.get(cid) for cid in page.cids]
    return page, records
