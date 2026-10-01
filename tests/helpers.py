# SPDX-License-Identifier: GPL-3.0-or-later
from dandelion.core.models import Media, Post, Profile, Role, Target
from dandelion.core.secrets import MemorySecretStore
from dandelion.core.store import Store
from dandelion.platforms import Registry


def setup_world(http):
    store = Store(":memory:")
    secrets = MemorySecretStore()
    registry = Registry(http, secrets)
    role = store.save_role(Role("linuxundich", "🐧", signature="#linux"))
    masto = store.save_profile(Profile("mastodon", "1", "toff", "oauth", server="social.example"))
    bsky = store.save_profile(Profile("bluesky", "did:plc:abc", "lui.bsky.social", "app-password",
                                      server="https://pds.example"))
    for p in (masto, bsky):
        store.set_role_profile(role.id, p.id, True)
    return store, secrets, registry, role, masto, bsky


def make_post(role, profiles, body="Hallo Welt", media=None):
    return Post(role_id=role.id, body=body, targets=[Target(p.id) for p in profiles],
                media=media or [])


def image(alt="", bytes_=1000, mime="image/png", path="/tmp/x.png"):
    return Media(path=path, sha256="0" * 64, mime=mime, bytes=bytes_, width=800, height=600,
                 alt_text=alt)
