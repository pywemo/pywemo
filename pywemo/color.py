"""Various utilities for handling colors."""

# Define usable ranges as bulbs either ignore or behave unexpectedly
# when it is sent a value is outside of the range.
TEMPERATURE_PROFILES = dict((model, temp) for models, temp in (
    # Lightify RGBW, 1900-6500K
    (["LIGHTIFY A19 RGBW"], (151, 555)),
) for model in models)

COLOR_PROFILES = dict((model, gamut) for models, gamut in (
    # Lightify RGBW, 1900-6500K
    # http://flow-morewithless.blogspot.com/2015/01/osram-lightify-color-gamut-and-spectrum.html
    (["LIGHTIFY A19 RGBW"],
     ((0.683924, 0.315904), (0.391678, 0.501414), (0.136990, 0.051035))),
) for model in models)


def get_profiles(model):
    """Return the temperature and color profiles for a given model."""
    return (TEMPERATURE_PROFILES.get(model, (150, 600)),
            COLOR_PROFILES.get(model, ((1., 0.), (0., 1.), (0., 0.))))


# pylint: disable=invalid-name
def is_same_side(p1, p2, a, b):
    """Test if points p1 and p2 lie on the same side of line a-b."""
    vector_ab = [y - x for x, y in zip(a, b)]
    vector_ap1 = [y - x for x, y in zip(a, p1)]
    vector_ap2 = [y - x for x, y in zip(a, p2)]
    cross_vab_ap1 = vector_ab[0] * vector_ap1[1] - vector_ab[1] * vector_ap1[0]
    cross_vab_ap2 = vector_ab[0] * vector_ap2[1] - vector_ab[1] * vector_ap2[0]
    return (cross_vab_ap1 * cross_vab_ap2) >= 0


# pylint: disable=invalid-name
def closest_point(p, a, b):
    """Test if points p1 and p2 lie on the same side of line a-b."""
    vector_ab = [y - x for x, y in zip(a, b)]
    vector_ap = [y - x for x, y in zip(a, p)]
    dot_ap_ab = sum(x * y for x, y in zip(vector_ap, vector_ab))
    dot_ab_ab = sum(x * y for x, y in zip(vector_ab, vector_ab))
    t = max(0.0, min(dot_ap_ab / dot_ab_ab, 1.0))
    return a[0] + vector_ab[0] * t, a[1] + vector_ab[1] * t


# pylint: disable=invalid-name
def limit_to_gamut(xy, gamut):
    """Return the closest point within the gamut triangle for colorxy."""
    r, g, b = gamut

    # http://www.blackpawn.com/texts/pointinpoly/
    if not is_same_side(xy, r, g, b):
        xy = closest_point(xy, g, b)

    if not is_same_side(xy, g, b, r):
        xy = closest_point(xy, b, r)

    if not is_same_side(xy, b, r, g):
        xy = closest_point(xy, r, g)

    return xy
