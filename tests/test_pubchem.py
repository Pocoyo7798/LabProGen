import json
from unittest.mock import MagicMock, patch

from src.config import KEY_FORMULA, KEY_INCHI, KEY_NAME, KEY_SMILES
from src.pubchem import (
    CompoundSearchPage,
    PubChemCompoundRecord,
    build_compound_autocomplete_url,
    fetch_compound_autocomplete,
    fetch_compound_autocomplete_page,
    fetch_compound_search_batch,
    map_pubchem_to_form_fields,
    parse_cid_list_payload,
    parse_compound_autocomplete_page,
    parse_compound_autocomplete_payload,
    parse_compound_property_payload,
    build_sdq_compound_search_query,
    parse_sdq_cid_page,
)

SAMPLE_RESPONSE = {
    "status": {"code": 0},
    "total": 3,
    "dictionary_terms": {
        "compound": ["Water", "water", "Water-18O"],
        "gene": ["wat"],
    },
}

SAMPLE_CIDS = {
    "IdentifierList": {"CID": [962, 105142, 24602]},
}

SAMPLE_SDQ = {
    "SDQOutputSet": [
        {
            "status": {"code": 0},
            "totalCount": 6046,
            "outputCount": 5,
            "rows": [
                {"cid": "962"},
                {"cid": "16217612"},
                {"cid": "129010977"},
                {"cid": "189830"},
                {"cid": "16216984"},
            ],
        }
    ]
}

SAMPLE_PROPERTY = {
    "PropertyTable": {
        "Properties": [
            {
                "CID": 962,
                "MolecularFormula": "H2O",
                "ConnectivitySMILES": "O",
                "InChI": "InChI=1S/H2O/h1H2",
                "IUPACName": "oxidane",
            }
        ]
    }
}


def test_parse_compound_autocomplete_payload():
    assert parse_compound_autocomplete_payload(SAMPLE_RESPONSE) == [
        "Water",
        "water",
        "Water-18O",
    ]


def test_parse_compound_autocomplete_payload_empty():
    assert parse_compound_autocomplete_payload({}) == []
    assert parse_compound_autocomplete_payload(None) == []


def test_fetch_compound_autocomplete_page_total():
    page = parse_compound_autocomplete_page(SAMPLE_RESPONSE)
    assert page.total == 3
    assert len(page.terms) == 3


def test_parse_sdq_cid_page():
    page = parse_sdq_cid_page(SAMPLE_SDQ)
    assert page.cids == [962, 16217612, 129010977, 189830, 16216984]
    assert page.total == 6046


def test_build_sdq_compound_search_query_uses_one_based_start():
    query = build_sdq_compound_search_query("Water", start=6, limit=5)
    payload = json.loads(query)
    assert payload["start"] == 6
    assert payload["limit"] == 5
    assert payload["where"] == {"ands": [{"*": "Water"}]}
    assert payload["order"] == ["relevancescore,desc"]


def test_build_compound_autocomplete_url_encodes_query():
    url = build_compound_autocomplete_url("sodium chloride", limit=5)
    assert url.endswith("/sodium%20chloride/json?limit=5")


def test_fetch_short_query_returns_empty():
    assert fetch_compound_autocomplete("ab") == []


def test_parse_cid_list_payload():
    assert parse_cid_list_payload(SAMPLE_CIDS) == [962, 105142, 24602]
    assert parse_cid_list_payload({}) == []


def test_parse_compound_property_payload():
    record = parse_compound_property_payload(SAMPLE_PROPERTY, "Water")
    assert record is not None
    assert record.cid == 962
    assert record.molecular_formula == "H2O"
    assert record.connectivity_smiles == "O"


def test_map_pubchem_to_form_fields_filters_visible():
    record = PubChemCompoundRecord(
        compound_name="Water",
        molecular_formula="H2O",
        connectivity_smiles="O",
        inchi="InChI=1S/H2O/h1H2",
    )
    mapped = map_pubchem_to_form_fields(
        record,
        "Water",
        visible_keys={KEY_NAME, KEY_FORMULA, KEY_SMILES},
        chemical_type="Molecules",
    )
    assert mapped[KEY_NAME] == "Water"
    assert mapped[KEY_FORMULA] == "H2O"
    assert mapped[KEY_SMILES] == "O"
    assert KEY_INCHI not in mapped


def test_map_pubchem_only_fills_visible_keys():
    record = PubChemCompoundRecord(
        compound_name="Water",
        molecular_formula="H2O",
        connectivity_smiles="O",
        inchi="InChI=1S/H2O/h1H2",
    )
    mapped = map_pubchem_to_form_fields(
        record,
        "Water",
        visible_keys={KEY_NAME, KEY_FORMULA},
        chemical_type="Media",
    )
    assert mapped == {KEY_NAME: "Water", KEY_FORMULA: "H2O"}


@patch("src.pubchem.urllib.request.urlopen")
def test_fetch_compound_autocomplete_parses_json(mock_urlopen):
    payload = json.dumps(SAMPLE_RESPONSE).encode("utf-8")
    mock_response = MagicMock()
    mock_response.read.return_value = payload
    mock_response.__enter__.return_value = mock_response
    mock_urlopen.return_value = mock_response

    terms = fetch_compound_autocomplete("water")
    assert terms == ["Water", "water", "Water-18O"]


@patch("src.pubchem.urllib.request.urlopen")
def test_fetch_compound_autocomplete_page(mock_urlopen):
    payload = json.dumps(SAMPLE_RESPONSE).encode("utf-8")
    mock_response = MagicMock()
    mock_response.read.return_value = payload
    mock_response.__enter__.return_value = mock_response
    mock_urlopen.return_value = mock_response

    page = fetch_compound_autocomplete_page("water", limit=5)
    assert page.total == 3
    assert page.terms[0] == "Water"


@patch("src.pubchem.fetch_compound_properties_by_cids")
@patch("src.pubchem.fetch_compound_search_cids_page")
def test_fetch_compound_search_batch_uses_sdq_page(mock_cids_page, mock_props):
    mock_cids_page.return_value = CompoundSearchPage(
        cids=[962, 16217612, 129010977],
        total=6046,
    )
    mock_props.return_value = [
        PubChemCompoundRecord(compound_name="Water", cid=962, molecular_formula="H2O"),
        PubChemCompoundRecord(compound_name="Water", cid=16217612, molecular_formula="H6N2O"),
        PubChemCompoundRecord(compound_name="Water", cid=129010977, molecular_formula="H2O"),
    ]

    page, records = fetch_compound_search_batch("Water", start=0, batch_size=3)

    mock_cids_page.assert_called_once_with("Water", start=0, batch_size=3)
    mock_props.assert_called_once_with([962, 16217612, 129010977], "Water")
    assert page.total == 6046
    assert page.cids == [962, 16217612, 129010977]
    assert len(records) == 3


@patch("src.pubchem.urllib.request.urlopen")
def test_fetch_compound_autocomplete_network_error(mock_urlopen):
    mock_urlopen.side_effect = OSError("network down")
    assert fetch_compound_autocomplete("water") == []
