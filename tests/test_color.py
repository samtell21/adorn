from adorn import color


def approx(a, b, tol):
    return abs(a - b) <= tol


def test_hsl_parses_components():
    h, s, l = color.hsl("#3a9d23")
    assert approx(h, 109, 3)
    assert approx(s, 0.635, 0.05)
    assert approx(l, 0.376, 0.05)


def test_make_hsl_round_trips():
    c = color.make_hsl(120, 0.5, 0.5)
    h, s, l = color.hsl(c)
    assert approx(h, 120, 3)
    assert approx(s, 0.5, 0.05)
    assert approx(l, 0.5, 0.05)


def test_make_hsl_returns_hex():
    c = color.make_hsl(0, 1.0, 0.5)
    assert c.startswith("#") and len(c) == 7


def test_lighten_increases_lightness():
    base = "#404040"
    out = color.lighten(base, 0.2)
    assert color.hsl(out)[2] > color.hsl(base)[2]


def test_gradient_returns_n_colors():
    g = color.gradient(["#000000", "#ffffff"], 5)
    assert len(g) == 5
    assert all(x.startswith("#") for x in g)
