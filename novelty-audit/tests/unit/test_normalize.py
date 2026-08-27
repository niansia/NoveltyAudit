from normalize_paper import canonical_key, normalize_arxiv_id, normalize_doi, normalize_paper, normalize_title, split_arxiv_id


def test_identifier_normalization():
    assert normalize_doi("https://doi.org/10.1000/ABC.") == "10.1000/abc"
    assert normalize_doi("ＤＯＩ：１０．１０００／ＡＢＣ。") == "10.1000/abc"
    assert normalize_arxiv_id("arXiv:2401.01234v3") == "2401.01234"
    assert split_arxiv_id("arXiv:2401.01234v3") == ("2401.01234", 3)


def test_unicode_title_normalization():
    assert normalize_title("Ａ Method:  Memory—Update") == "a method memory update"


def test_canonical_key_prefers_doi():
    paper = normalize_paper({"title": "A", "doi": "10.1/X", "authors": []})
    assert canonical_key(paper) == "doi:10.1/x"
