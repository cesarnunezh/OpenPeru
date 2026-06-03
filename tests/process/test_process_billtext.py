from backend.process.billtext import extract_bill_body, normalize_bill_text


def test_normalize_preserves_accents():
    assert normalize_bill_text("próyecto") == "PRÓYECTO"


def test_extract_starts_at_first_anchor():
    raw = (
        "OFICIO blah blah\n"
        "EL CONGRESO DE LA REPÚBLICA\n"
        "HA DADO LA LEY SIGUIENTE\n"
        "ARTÍCULO 1..."
    )
    out = extract_bill_body(raw)
    assert out is not None
    assert out.startswith("EL CONGRESO DE LA REPÚBLICA")


def test_extract_preserves_original_casing_and_accents():
    raw = (
        "oficio previo...\n"
        "El Congreso de la República\n"
        "Ha dado la Ley siguiente: el presente proyecto..."
    )
    out = extract_bill_body(raw)
    assert out is not None
    assert out.startswith("El Congreso de la República")


def test_extract_trims_trailing_marker():
    raw = (
        "cover page\n"
        "EL CONGRESO DE LA REPÚBLICA\n"
        "HA DADO LA LEY SIGUIENTE\n"
        "cuerpo del proyecto aquí.\n"
        "COMUNIQUESE AL SEÑOR PRESIDENTE DE LA REPUBLICA PARA SU PROMULGACIÓN acuerda..."
    )
    out = extract_bill_body(raw)
    assert out is not None
    assert out.startswith("EL CONGRESO DE LA REPÚBLICA")
    assert (
        "COMUNIQUESE AL SEÑOR PRESIDENTE DE LA REPUBLICA PARA SU PROMULGACIÓN"
        not in out
    )
    assert out.rstrip().endswith("cuerpo del proyecto aquí.")


def test_extract_returns_none_without_anchor():
    assert extract_bill_body("solo oficio sin marcadores") is None
