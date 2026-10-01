# SPDX-License-Identifier: GPL-3.0-or-later
import json
import time
import urllib.parse

import pytest
from helpers import image, make_post, setup_world

from dandelion.core.models import Profile, ProfileStatus, TargetPart
from dandelion.core.validation import validate
from dandelion.net.http import Response
from dandelion.platforms.base import Composition, PlatformError
from dandelion.platforms.linkedin import escape_little


def add_profile(store, secrets, run, platform, remote_id, handle, secret):
    p = store.save_profile(Profile(platform, remote_id, handle, "byo-oauth"))
    run(secrets.set(p.uuid, "oauth", "l", secret))
    return p


# --------------------------------------------------------------------- X

def test_x_login_pkce_public_client(http, run):
    store, secrets, reg, *_ = setup_world(http)
    x = reg.get("x")
    login = x.begin_app_login("CID", "")
    q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(login.url).query))
    assert q["code_challenge_method"] == "S256" and q["redirect_uri"] == x.redirect_uri
    assert "offline.access" in q["scope"]
    http.add("POST", "https://api.x.com/2/oauth2/token",
             {"access_token": "at", "refresh_token": "rt", "expires_in": 7200})
    http.add("GET", "https://api.x.com/2/users/me",
             {"data": {"id": "77", "username": "linuxundich", "name": "Linux und Ich"}})
    [(profile, secret)] = run(x.complete_app_login(login, "CODE"))
    assert profile.handle == "linuxundich" and secret["refresh_token"] == "rt"
    req = http.find("POST", "https://api.x.com/2/oauth2/token")[0]
    assert req.form["client_id"] == "CID" and req.form["code_verifier"] == login.verifier
    assert "Authorization" not in req.headers


def test_x_confidential_client_uses_basic_auth(http, run):
    store, secrets, reg, *_ = setup_world(http)
    x = reg.get("x")
    req = x._token_request("CID", "SECRET", {"grant_type": "refresh_token"})
    assert req.headers["Authorization"].startswith("Basic ") and "client_id" not in req.form


def test_x_post_with_image_alt_and_refresh(http, run, tmp_path):
    store, secrets, reg, *_ = setup_world(http)
    p = add_profile(store, secrets, run, "x", "77", "linuxundich", {
        "access_token": "old", "refresh_token": "rt", "expires_at": time.time() - 5,
        "client_id": "CID", "client_secret": ""})
    http.add("POST", "https://api.x.com/2/oauth2/token",
             {"access_token": "new", "refresh_token": "rt2", "expires_in": 7200})
    http.add("POST", "https://api.x.com/2/media/upload", {"data": {"id": "M1"}})
    http.add("POST", "https://api.x.com/2/media/metadata", {})
    http.add("POST", "https://api.x.com/2/tweets", {"data": {"id": "T1", "text": "x"}})
    img = tmp_path / "a.png"
    img.write_bytes(b"\x89PNG fake")
    x = reg.get("x")
    ref = run(x.upload_media(p, image(alt="Pusteblume", path=str(img))))
    part = run(x.post(p, Composition("Hallo"), [ref], reply_to=None, root=None,
                      idempotency_key="k"))
    assert part.remote_url == "https://x.com/linuxundich/status/T1"
    meta = http.find("POST", "https://api.x.com/2/media/metadata")[0].json
    assert meta == {"id": "M1", "metadata": {"alt_text": {"text": "Pusteblume"}}}
    tweet = http.find("POST", "https://api.x.com/2/tweets")[0]
    assert tweet.json["media"] == {"media_ids": ["M1"]}
    assert tweet.headers["Authorization"] == "Bearer new"
    assert run(secrets.get(p.uuid, "oauth"))["refresh_token"] == "rt2"


def test_x_payment_required(http, run):
    store, secrets, reg, *_ = setup_world(http)
    p = add_profile(store, secrets, run, "x", "77", "lui", {
        "access_token": "at", "expires_at": time.time() + 999, "client_id": "CID"})
    http.add("POST", "https://api.x.com/2/tweets", {"title": "CreditsDepleted"}, 402)
    with pytest.raises(PlatformError) as e:
        run(reg.get("x").post(p, Composition("x"), [], reply_to=None, root=None,
                              idempotency_key="k"))
    assert "credits" in e.value.message.lower()


def test_x_cost_warning_in_validation(http, run):
    store, secrets, reg, role, m, b = setup_world(http)
    p = add_profile(store, secrets, run, "x", "77", "lui", {"access_token": "a"})
    rep = validate(make_post(role, [p], body="Neu: https://linuxundich.de/artikel"), role, [p], reg)
    issues = rep.targets[0].issues
    assert any(i.code == "cost" and "0.20" in i.message for i in issues)
    assert rep.can_send


def test_x_limits_and_count(http):
    store, secrets, reg, *_ = setup_world(http)
    x = reg.get("x")
    limits = x.default_limits()
    assert x.count(Composition("日本" * 141), limits).over
    assert not x.count(Composition("a" * 280), limits).over


# --------------------------------------------------------------- LinkedIn

def test_escape_little():
    assert escape_little("Preis (neu) *jetzt* @Toff") == "Preis \\(neu\\) \\*jetzt\\* \\@Toff"
    assert escape_little("Mehr zu #GNOME_50!") == "Mehr zu {hashtag|\\#|GNOME\\_50}!"
    assert escape_little("https://ex.org/a_(b)") == "https://ex.org/a\\_\\(b\\)"
    assert escape_little("a\\b") == "a\\\\b"


def test_linkedin_login_and_post_with_article(http, run):
    store, secrets, reg, *_ = setup_world(http)
    li = reg.get("linkedin")
    login = li.begin_app_login("CID", "SEC")
    http.add("POST", "https://www.linkedin.com/oauth/v2/accessToken",
             {"access_token": "lat", "expires_in": 5184000})
    http.add("GET", "https://api.linkedin.com/v2/userinfo",
             {"sub": "abc123", "name": "Christoph Langner", "picture": "https://p"})
    [(profile, secret)] = run(li.complete_app_login(login, "CODE"))
    assert profile.remote_id == "abc123" and secret["client_secret"] == "SEC"
    assert http.find("POST", "https://www.linkedin.com/oauth/v2/accessToken")[0] \
        .form["client_secret"] == "SEC"
    profile = store.save_profile(profile)
    run(li.store_credentials(profile, secret))

    http.add("GET", "https://linuxundich.de/", raw=b'<meta property="og:title" content="GNOME 50">',
             headers={"content-type": "text/html"})
    http.add("POST", "https://api.linkedin.com/rest/posts",
             lambda req: Response(201, {"x-restli-id": "urn:li:share:9"}, b"", req.url))
    part = run(li.post(profile, Composition("Neu (lesen): https://linuxundich.de/x #GNOME"), [],
                       reply_to=None, root=None, idempotency_key="k"))
    assert part.remote_url == "https://www.linkedin.com/feed/update/urn:li:share:9/"
    req = http.find("POST", "https://api.linkedin.com/rest/posts")[0]
    assert req.headers["Linkedin-Version"] and req.headers["X-Restli-Protocol-Version"] == "2.0.0"
    body = req.json
    assert body["author"] == "urn:li:person:abc123"
    assert body["commentary"].startswith("Neu \\(lesen\\):")
    assert "{hashtag|\\#|GNOME}" in body["commentary"]
    assert body["content"]["article"]["title"] == "GNOME 50"


def test_linkedin_images_single_and_multi(http, run, tmp_path):
    store, secrets, reg, *_ = setup_world(http)
    p = add_profile(store, secrets, run, "linkedin", "abc", "C", {
        "access_token": "lat", "expires_at": time.time() + 9999})
    http.add("POST", "https://api.linkedin.com/rest/images?action=initializeUpload",
             {"value": {"uploadUrl": "https://upload.example/1", "image": "urn:li:image:1"}})
    http.add("PUT", "https://upload.example/1", raw=b"", status=201)
    http.add("POST", "https://api.linkedin.com/rest/posts",
             lambda req: Response(201, {"x-restli-id": "urn:li:share:1"}, b"", req.url))
    img = tmp_path / "a.png"
    img.write_bytes(b"\x89PNG fake")
    li = reg.get("linkedin")
    ref = run(li.upload_media(p, image(alt="Alt", path=str(img))))
    run(li.post(p, Composition("x"), [ref], reply_to=None, root=None, idempotency_key="k"))
    run(li.post(p, Composition("x"), [ref, ref], reply_to=None, root=None, idempotency_key="k"))
    posts = http.find("POST", "https://api.linkedin.com/rest/posts")
    assert posts[0].json["content"] == {"media": {"id": "urn:li:image:1", "altText": "Alt"}}
    assert len(posts[1].json["content"]["multiImage"]["images"]) == 2


def test_linkedin_expired_and_expiring(http, run):
    store, secrets, reg, *_ = setup_world(http)
    li = reg.get("linkedin")
    p = add_profile(store, secrets, run, "linkedin", "abc", "C", {
        "access_token": "lat", "expires_at": time.time() - 1})
    with pytest.raises(PlatformError) as e:
        run(li.post(p, Composition("x"), [], reply_to=None, root=None, idempotency_key="k"))
    assert e.value.auth
    q = add_profile(store, secrets, run, "linkedin", "def", "D", {
        "access_token": "lat", "expires_at": time.time() + 3 * 86400})
    http.add("GET", "https://api.linkedin.com/v2/userinfo", {"sub": "def", "name": "D"})
    q = run(li.refresh_profile(q))
    assert q.status == ProfileStatus.EXPIRING


def test_linkedin_counts_utf16(http):
    store, secrets, reg, *_ = setup_world(http)
    li = reg.get("linkedin")
    assert li.count(Composition("👍" * 1500), li.default_limits()).used == 3000


# --------------------------------------------------------------- Facebook

def test_facebook_login_returns_pages(http, run):
    store, secrets, reg, *_ = setup_world(http)
    fb = reg.get("facebook")
    login = fb.begin_app_login("APP", "SEC")
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A8742%2Fcallback" in login.url

    def token(req):
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(req.full_url()).query))
        tok = "long" if q.get("grant_type") == "fb_exchange_token" else "short"
        return Response(200, {}, json.dumps({"access_token": tok}).encode(), req.url)

    http.add("GET", "https://graph.facebook.com/v26.0/oauth/access_token", token)
    http.add("GET", "https://graph.facebook.com/v26.0/me/accounts", {"data": [
        {"id": "1", "name": "Linux und Ich", "access_token": "page1",
         "tasks": ["CREATE_CONTENT", "MODERATE"]},
        {"id": "2", "name": "Nur Analyse", "access_token": "page2", "tasks": ["ANALYZE"]}]})
    pages = run(fb.complete_app_login(login, "CODE"))
    assert [(p.handle, s["access_token"]) for p, s in pages] == [("Linux und Ich", "page1")]
    accounts = http.find("GET", "https://graph.facebook.com/v26.0/me/accounts")[0]
    assert "access_token=long" in accounts.full_url()


def test_facebook_post_photos_and_link(http, run, tmp_path):
    store, secrets, reg, *_ = setup_world(http)
    p = add_profile(store, secrets, run, "facebook", "1", "Linux und Ich",
                    {"access_token": "page1"})
    fb = reg.get("facebook")
    http.add("POST", "https://graph.facebook.com/v26.0/1/photos", {"id": "P1"})
    http.add("POST", "https://graph.facebook.com/v26.0/1/feed", {"id": "1_99"})
    img = tmp_path / "a.png"
    img.write_bytes(b"\x89PNG fake")
    ref = run(fb.upload_media(p, image(alt="Alt", path=str(img))))
    part = run(fb.post(p, Composition("Bild"), [ref], reply_to=None, root=None,
                       idempotency_key="k"))
    assert part.remote_url == "https://www.facebook.com/1_99"
    photo = http.find("POST", "https://graph.facebook.com/v26.0/1/photos")[0]
    assert photo.form["published"] == "false" and photo.form["alt_text_custom"] == "Alt"
    feed = http.find("POST", "https://graph.facebook.com/v26.0/1/feed")[0]
    assert json.loads(feed.form["attached_media[0]"]) == {"media_fbid": "P1"}
    run(fb.post(p, Composition("Lies https://linuxundich.de/a"), [], reply_to=None, root=None,
                idempotency_key="k"))
    assert http.find("POST", "https://graph.facebook.com/v26.0/1/feed")[1].form["link"] == \
        "https://linuxundich.de/a"


def test_facebook_token_invalid(http, run):
    store, secrets, reg, *_ = setup_world(http)
    p = add_profile(store, secrets, run, "facebook", "1", "Seite", {"access_token": "bad"})
    http.add("GET", "https://graph.facebook.com/v26.0/1",
             {"error": {"code": 190, "message": "Invalid OAuth access token"}}, 400)
    p = run(reg.get("facebook").refresh_profile(p))
    assert p.status == ProfileStatus.EXPIRED


def test_delete_calls(http, run):
    store, secrets, reg, *_ = setup_world(http)
    x = add_profile(store, secrets, run, "x", "7", "l", {"access_token": "a",
                                                        "expires_at": time.time() + 999})
    li = add_profile(store, secrets, run, "linkedin", "a", "c", {"access_token": "a",
                                                                "expires_at": time.time() + 999})
    http.add("DELETE", "https://api.x.com/2/tweets/T1", {"data": {"deleted": True}})
    http.add("DELETE", "https://api.linkedin.com/rest/posts/urn%3Ali%3Ashare%3A9", raw=b"",
             status=204)
    run(reg.get("x").delete(x, TargetPart(0, "T1")))
    run(reg.get("linkedin").delete(li, TargetPart(0, "urn:li:share:9")))
    assert len(http.requests) == 2
