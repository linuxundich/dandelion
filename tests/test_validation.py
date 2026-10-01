# SPDX-License-Identifier: GPL-3.0-or-later
from helpers import image, make_post, setup_world

from dandelion.core.compose import apply_signature, composition_for
from dandelion.core.models import ProfileStatus, Variant
from dandelion.core.validation import validate


def codes(report, platform):
    t = next(t for t in report.targets if t.profile.platform == platform)
    return {(i.severity, i.code) for i in t.issues}


def test_ok(http):
    store, _, reg, role, m, b = setup_world(http)
    rep = validate(make_post(role, [m, b]), role, [m, b], reg)
    assert rep.can_send and rep.issue_count == 0


def test_no_profiles(http):
    store, _, reg, role, m, b = setup_world(http)
    rep = validate(make_post(role, []), role, [m, b], reg)
    assert not rep.can_send and rep.general[0].code == "no_profiles"


def test_bluesky_too_long_mastodon_ok(http):
    store, _, reg, role, m, b = setup_world(http)
    rep = validate(make_post(role, [m, b], body="x" * 400), role, [m, b], reg)
    assert ("error", "too_long") in codes(rep, "bluesky")
    assert codes(rep, "mastodon") == set()


def test_variant_fixes_length(http):
    store, _, reg, role, m, b = setup_world(http)
    post = make_post(role, [m, b], body="x" * 400)
    post.variants.append(Variant("bluesky", "kurz"))
    assert validate(post, role, [m, b], reg).can_send


def test_alt_text_policy(http):
    store, _, reg, role, m, b = setup_world(http)
    post = make_post(role, [m, b], media=[image(alt="")])
    rep = validate(post, role, [m, b], reg)
    assert ("error", "missing_alt") in codes(rep, "mastodon")
    assert ("warning", "missing_alt") in codes(rep, "bluesky")
    rep = validate(post, role, [m, b], reg, require_alt_everywhere=True)
    assert ("error", "missing_alt") in codes(rep, "bluesky")


def test_alt_too_long(http):
    store, _, reg, role, m, b = setup_world(http)
    rep = validate(make_post(role, [m], media=[image(alt="a" * 1501)]), role, [m], reg)
    assert ("error", "alt_too_long") in codes(rep, "mastodon")


def test_too_many_images_and_video(http):
    store, _, reg, role, m, b = setup_world(http)
    media = [image(alt="x") for _ in range(5)]
    rep = validate(make_post(role, [m], media=media), role, [m], reg)
    assert ("error", "too_many_images") in codes(rep, "mastodon")
    video = image(alt="x", mime="video/mp4")
    rep = validate(make_post(role, [b], media=[video]), role, [b], reg)
    assert ("error", "video_unsupported") in codes(rep, "bluesky")


def test_expired_profile(http):
    store, _, reg, role, m, b = setup_world(http)
    m.status = ProfileStatus.EXPIRED
    rep = validate(make_post(role, [m]), role, [m], reg)
    assert ("error", "auth") in codes(rep, "mastodon")


def test_signature_counts(http):
    store, _, reg, role, m, b = setup_world(http)
    post = make_post(role, [b], body="x" * 295)
    assert not validate(post, role, [b], reg).can_send     # + "\n\n#linux"
    post.use_signature = False
    assert validate(post, role, [b], reg).can_send


def test_apply_signature():
    assert apply_signature("Text", "#linux") == "Text\n\n#linux"
    assert apply_signature("Text #linux", "#linux") == "Text #linux"
    assert apply_signature("", "#linux") == "#linux"


def test_profile_variant_beats_platform_variant(http):
    store, _, reg, role, m, b = setup_world(http)
    post = make_post(role, [m])
    post.variants += [Variant("mastodon", "Plattform"), Variant("mastodon", "Profil", m.id)]
    assert composition_for(post, m, None).text == "Profil"


def test_signature_alone_is_empty(http):
    store, _, reg, role, m, b = setup_world(http)
    rep = validate(make_post(role, [m], body=""), role, [m], reg)
    assert ("error", "empty") in codes(rep, "mastodon")
