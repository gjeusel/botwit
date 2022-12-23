import json
import os
from pathlib import Path

import pytest
from vcr import VCR
from vcr.persisters.filesystem import FilesystemPersister as VCRFilesystemPersister

from botwit.twitter_client import TwitterClient

from . import TWITTER_CASSETTES_DIR, VCR_DIR


@pytest.fixture(scope="session")
def vcr() -> VCR:
    class VCRAcceptingPath(VCR):  # type: ignore
        def use_cassette(self, path=None, **kwargs):
            if isinstance(path, Path):
                path = path.as_posix()
            return super().use_cassette(path, **kwargs)

    def hide_sensible_informations_from_response(response):
        if "access_token" in response.get("content", ""):
            response["content"] = json.dumps(
                {"token_type": "bearer", "access_token": "fake-access-token"}
            )
        return response

    vcr = VCRAcceptingPath(
        before_record_response=hide_sensible_informations_from_response
    )

    class Persister:
        @classmethod
        def _add_prefix(cls, cassette_path):
            if isinstance(cassette_path, str):
                if not cassette_path.startswith(VCR_DIR.as_posix()):
                    cassette_path = VCR_DIR / cassette_path

            return cassette_path

        @classmethod
        def load_cassette(cls, cassette_path, serializer):
            return VCRFilesystemPersister.load_cassette(
                cassette_path=cls._add_prefix(cassette_path), serializer=serializer
            )

        @classmethod
        def save_cassette(cls, cassette_path, cassette_dict, serializer):
            return VCRFilesystemPersister.save_cassette(
                cassette_path=cls._add_prefix(cassette_path),
                cassette_dict=cassette_dict,
                serializer=serializer,
            )

    vcr.register_persister(Persister)
    return vcr


@pytest.fixture(scope="session")
def twitter(vcr: VCR) -> TwitterClient:
    client = TwitterClient(
        consumer_key=str(os.environ.get("TWITTER_CONSUMER_KEY")),
        consumer_secret=str(os.environ.get("TWITTER_CONSUMER_SECRET")),
    )

    # Ensure auth is done.
    with vcr.use_cassette(TWITTER_CASSETTES_DIR / "auth_flow.yaml"):
        client.auth.request_new_token()
    return client


@pytest.fixture(scope="session")
def notion():
    pass
