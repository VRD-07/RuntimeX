"""Offline parser tests for the patent tool.

Every keyless patent endpoint now throttles or has been retired (see the module
docstring in tools/patent_tool.py), and EPO OPS needs a key that CI will not
have. A live smoke test therefore cannot prove the response parsers work — it
just proves the network refused us.

So the parsers are exercised here against fixtures that reproduce the exact
response shapes captured from the real services, including the awkward parts:
OPS's ``{"$": value}`` wrappers and its bare-object-vs-list ambiguity, and
Google's routed ``patent/XX.../en`` publication ids and placeholder Indian
titles. Run with:

    cd backend && python test_patent_parsers.py

No network access required.
"""

import sys

from tools.patent_tool import (
    _build_snippet,
    _family_coverage,
    _jurisdiction_rank,
    _normalize_pub,
    _parse_ops_document,
)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass


# An OPS exchange-document with every field in its "one occurrence" form: the
# title is a bare object rather than a list, and each party appears twice (once
# epodoc, once original) exactly as the service returns it.
OPS_SINGLE = {
    "@country": "IN",
    "@doc-number": "202141034567",
    "@kind": "A",
    "@family-id": "74569811",
    "bibliographic-data": {
        "invention-title": {"@lang": "en", "$": "Method for multilingual speech recognition"},
        "publication-reference": {
            "document-id": [
                {"@document-id-type": "docdb", "date": {"$": "20230317"}},
            ]
        },
        "application-reference": {
            "document-id": {"@document-id-type": "docdb", "date": {"$": "20210731"}}
        },
        "parties": {
            "applicants": {
                "applicant": [
                    {"@data-format": "epodoc", "applicant-name": {"name": {"$": "SARVAM AI PVT LTD"}}},
                    {"@data-format": "original", "applicant-name": {"name": {"$": "Sarvam AI Private Limited"}}},
                ]
            },
            "inventors": {
                "inventor": {
                    "@data-format": "original",
                    "inventor-name": {"name": {"$": "Kumar, Vivek"}},
                }
            },
        },
        "abstract": {"@lang": "en", "p": {"$": "A system for recognising speech across Indic languages."}},
    },
}

# The same document in its "several occurrences" form: title as a list with a
# non-English entry first, applicants with no original-language variant at all.
OPS_MULTI = {
    "@country": "WO",
    "@doc-number": "2023012345",
    "@kind": "A1",
    "bibliographic-data": {
        "invention-title": [
            {"@lang": "de", "$": "Verfahren zur Spracherkennung"},
            {"@lang": "en", "$": "Speech recognition method"},
        ],
        "publication-reference": {"document-id": {"date": {"$": "20230119"}}},
        "parties": {
            "applicants": {
                "applicant": {"@data-format": "epodoc", "applicant-name": {"name": {"$": "AI4BHARAT"}}}
            }
        },
    },
}

GOOGLE_FIXTURE = {
    "results": {
        "cluster": [
            {
                "result": [
                    {
                        "id": "patent/IN2014DN09942A/en",
                        "patent": {
                            # Indian records really do carry a placeholder title.
                            "title": " Patent IN2014DN09942A",
                            "snippet": "A <b>speech</b> processing pipeline for low-resource languages.",
                            "assignee": "Google LLC",
                            "inventor": "Jane Doe",
                            "filing_date": "2013-05-21",
                            "publication_date": "2015-08-14",
                            "publication_number": "IN2014DN09942A",
                            "family_metadata": {
                                "aggregated": {
                                    "country_status": [
                                        {"country_code": "IN", "best_patent_stage": {"state": "ACTIVE"}},
                                        {"country_code": "US", "best_patent_stage": {"state": "ACTIVE"}},
                                        {"country_code": "CN", "best_patent_stage": {"state": "NOT_ACTIVE"}},
                                        {"country_code": "JP", "best_patent_stage": {"state": "UNKNOWN"}},
                                    ]
                                }
                            },
                        },
                    }
                ]
            }
        ]
    }
}


def expect(label, actual, wanted):
    if actual == wanted:
        print(f"  OK   {label}")
        return []
    print(f"  FAIL {label}\n         got:    {actual!r}\n         wanted: {wanted!r}")
    return [label]


def test_ops_single():
    print("OPS document, single-occurrence shape")
    doc = _parse_ops_document(OPS_SINGLE)
    assert doc is not None, "parser returned None"
    return (
        expect("publication_number", doc["publication_number"], "IN202141034567A")
        + expect("country", doc["country"], "IN")
        + expect("title", doc["title"], "Method for multilingual speech recognition")
        # The original-language applicant wins over the uppercased epodoc form.
        + expect("assignees", doc["assignees"], ["Sarvam AI Private Limited"])
        + expect("inventors", doc["inventors"], ["Kumar, Vivek"])
        + expect("publication_date", doc["publication_date"], "2023-03-17")
        + expect("filing_date", doc["filing_date"], "2021-07-31")
        + expect("abstract", doc["abstract"], "A system for recognising speech across Indic languages.")
        + expect("family_id", doc["family_id"], "74569811")
    )


def test_ops_multi():
    print("OPS document, list shape with epodoc-only parties")
    doc = _parse_ops_document(OPS_MULTI)
    assert doc is not None, "parser returned None"
    return (
        expect("publication_number", doc["publication_number"], "WO2023012345A1")
        + expect("title (first listed)", doc["title"], "Verfahren zur Spracherkennung")
        + expect("assignees (epodoc fallback)", doc["assignees"], ["AI4BHARAT"])
        + expect("inventors (absent)", doc["inventors"], [])
        + expect("filing_date (absent)", doc["filing_date"], "")
        + expect("abstract (absent)", doc["abstract"], "")
    )


def test_ops_rejects_garbage():
    print("OPS parser rejects unusable input")
    return (
        expect("None", _parse_ops_document(None), None)
        + expect("string", _parse_ops_document("nope"), None)
        + expect("missing doc-number", _parse_ops_document({"@country": "IN"}), None)
        + expect("missing country", _parse_ops_document({"@doc-number": "123"}), None)
    )


def test_google_shapes():
    print("Google Patents publication-id normalisation")
    problems = (
        expect("routed form", _normalize_pub("patent/IN2014DN09942A/en"), "IN2014DN09942A")
        + expect("bare form", _normalize_pub("IN2014DN09942A"), "IN2014DN09942A")
        + expect("empty", _normalize_pub(""), "")
    )

    print("Google Patents family coverage (ACTIVE only)")
    patent = GOOGLE_FIXTURE["results"]["cluster"][0]["result"][0]["patent"]
    problems += expect("active jurisdictions", _family_coverage(patent), ["IN", "US"])
    problems += expect("no family_metadata", _family_coverage({}), [])
    return problems


def test_snippet_and_ranking():
    print("Snippet composition and jurisdiction ranking")
    record = {
        "assignees": ["Sarvam AI Private Limited"],
        "inventors": ["Kumar, Vivek"],
        "filing_date": "2021-07-31",
        "active_jurisdictions": ["IN", "US"],
        "abstract": "A system for recognising speech.",
    }
    snippet = _build_snippet(record)
    problems = []
    for fragment in ("Assignee: Sarvam AI Private Limited", "Filed: 2021-07-31", "Active in: IN, US"):
        problems += expect(f"snippet contains {fragment!r}", fragment in snippet, True)
    problems += expect("snippet keeps abstract", snippet.endswith("A system for recognising speech."), True)
    problems += expect("empty record is still readable", _build_snippet({}),
                       "No abstract or assignee metadata available.")

    # India must outrank everything, which is what makes the sort India-first.
    ranks = [_jurisdiction_rank(c) for c in ("IN", "WO", "EP", "US", "CN", "")]
    problems += expect("IN ranks first", ranks[0] == min(ranks), True)
    problems += expect("ranks strictly ordered IN<WO<EP<US", ranks[:4] == sorted(ranks[:4]) and len(set(ranks[:4])) == 4, True)
    problems += expect("unknown country ranks last", ranks[4] > max(ranks[:4]), True)
    return problems


def main():
    failures = []
    for test in (
        test_ops_single,
        test_ops_multi,
        test_ops_rejects_garbage,
        test_google_shapes,
        test_snippet_and_ranking,
    ):
        try:
            failures += test()
        except Exception as exc:
            print(f"  RAISED {type(exc).__name__}: {exc}")
            failures.append(f"{test.__name__} raised {type(exc).__name__}")
        print()

    print("=" * 62)
    if failures:
        print(f"FAILED — {len(failures)} assertion(s):")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print("PASSED — patent response parsers handle every captured shape.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
