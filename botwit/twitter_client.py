from __future__ import annotations

from datetime import datetime
from typing import Any, Generator, Literal, Sequence

import httpx
import httpx_auth
from pydantic import BaseModel


class TwitterError(Exception):
    def __init__(self, payload: dict[str, Any] | None = None):
        """

        Note: payload is like:

        ```json
        {
            "errors": [
                {
                    "value": "trashh_devowejr",
                    "detail": "Could not find user with username: [trashh_devowejr].",
                    "title": "Not Found Error",
                    "resource_type": "user",
                    "parameter": "username",
                    "resource_id": "trashh_devowejr",
                    "type": "https://api.twitter.com/2/problems/resource-not-found",
                }
            ]
        }
        ```

        """
        self.payload = payload

        def __str__(self) -> str:
            if self.payload:
                errs = [
                    f"{e['resource_type']} '{e['title']}': {e['detail']}"
                    for e in self.payload
                ]
                if len(errs) > 1:
                    raise NotImplementedError
                else:
                    return errs[0]
            else:
                raise super().__str__()


def handle_twitter_error(response: httpx.Response) -> httpx.Response:
    response.read()  # ensure response is read before parsing json
    data = response.json()
    if data.get("errors"):
        raise TwitterError(data.get("errors"))
    return response


class TwitterTokenCache(httpx_auth.oauth2_tokens.TokenMemoryCache):
    NO_EXPIRY = 2524608000  # "2050-01-01T00:00:00+00:00"

    def _add_bearer_token(self, key: str, token: str) -> None:
        if not token:
            raise httpx_auth.errors.InvalidToken(token)

        self._add_token(key=key, token=token, expiry=self.NO_EXPIRY)


class TwitterOAuth2ClientCredentials(httpx_auth.OAuth2ClientCredentials):
    # https://developer.twitter.com/en/docs/authentication/api-reference/token

    token_cache = TwitterTokenCache()

    def auth_flow(
        self, request: httpx.Request
    ) -> Generator[httpx.Request, httpx.Response, None]:
        token = self.token_cache.get_token(
            self.state,
            early_expiry=self.early_expiry,
            on_missing_token=self.request_new_token,
        )
        request.headers[self.header_name] = self.header_value.format(token=token)
        yield request


class User(BaseModel):
    id: int
    name: str
    username: str


class Tweet(BaseModel):
    id: int
    author_id: int
    text: str
    created_at: datetime

    edit_history_tweet_ids: list[int]  # always there even if not asked

    referenced_tweets: list[dict[str, str]] | None = None

    users: list[User] | None = None
    tweets: list[Tweet] | None = None

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> Tweet:
        kwargs = payload["data"]

        if payload.get("includes"):
            kwargs |= payload["includes"]

        return cls(**kwargs)

    @property
    def author(self) -> User | None:
        return {u.id: u for u in self.users or []}.get(self.author_id)

    def __repr__(self) -> str:
        core = f"Tweet n°{self.id}"

        if self.author is not None:
            core = f"{core} - {self.author.username}"

        text_peek_max_len = 30
        text = self.text
        if len(text) > text_peek_max_len:
            text = text[:text_peek_max_len] + "..."

        return f"<{core}> {text}"


TweetExpansions = Literal[
    "attachments.poll_ids",
    "attachments.media_keys",
    "author_id",
    "edit_history_tweet_ids",
    "entities.mentions.username",
    "geo.place_id",
    "in_reply_to_user_id",
    "referenced_tweets.id",
    "referenced_tweets.id.author_id",
]

TweetFields = Literal[
    "attachments",
    "author_id",
    "context_annotations",
    "conversation_id",
    "created_at",
    "edit_controls",
    "entities",
    "geo",
    "id",
    "in_reply_to_user_id",
    "lang",
    "non_public_metrics",
    "public_metrics",
    "organic_metrics",
    "promoted_metrics",
    "possibly_sensitive",
    "referenced_tweets",
    "reply_settings",
    "source",
    "text",
    "withheld",
]

DEFAULT_TWEET_FIELDS: tuple[TweetFields] = (
    "id",
    "author_id",
    "created_at",
    "text",
)


class TwitterClient(httpx.Client):
    def __init__(
        self,
        consumer_key: str,
        consumer_secret: str,
        base_url: str = "https://api.twitter.com",
        **kwargs: dict[str, Any],
    ):
        auth = TwitterOAuth2ClientCredentials(
            token_url=base_url + "/oauth2/token",
            client_id=consumer_key,
            client_secret=consumer_secret,
        )
        kwargs = {
            "follow_redirects": True,
            "event_hooks": {
                "request": [],
                "response": [
                    lambda resp: resp.raise_for_status(),
                    handle_twitter_error,
                ],
            },
        } | kwargs
        super().__init__(base_url=base_url, auth=auth, **kwargs)

    def get_user(self, username: str) -> User:
        username = username.lstrip("@")
        resp = self.get(f"/2/users/by/username/{username}")
        return User(**resp.json()["data"])

    def get_tweets(
        self,
        ids: Sequence[int],
        fields: Sequence[TweetFields] = DEFAULT_TWEET_FIELDS,
    ) -> list[Tweet]:
        """
        https://developer.twitter.com/en/docs/twitter-api/tweets/lookup/api-reference/get-tweets
        """
        params = {
            "ids": ",".join(str(e) for e in ids),
            "tweet.fields": ",".join(fields),
        }
        resp = self.get("/2/tweets", params=params)
        return [Tweet(**e) for e in resp.json()["data"]]

    def get_tweet(
        self,
        id: int,
        *,
        fields: Sequence[TweetFields] = DEFAULT_TWEET_FIELDS,
        expansions: Sequence[TweetExpansions],
    ) -> Tweet:
        """
        https://developer.twitter.com/en/docs/twitter-api/tweets/lookup/api-reference/get-tweets-id
        """
        params = {
            "expansions": ",".join(expansions),
            "tweet.fields": ",".join(fields),
        }
        resp = self.get(f"/2/tweets/{id}", params=params)
        return Tweet.from_payload(resp.json())

    def get_user_tweets(
        self,
        user_id: int,
        fields: Sequence[TweetFields] = DEFAULT_TWEET_FIELDS,
    ) -> list[Tweet]:
        """
        https://developer.twitter.com/en/docs/twitter-api/tweets/timelines/api-reference/get-users-id-tweets
        """
        params = {
            "fields": ",".join(fields),
            "tweet.fields": ",".join(fields),
        }
        resp = self.get(f"/2/users/{user_id}/tweets", params=params)
        return [Tweet(**e) for e in resp.json()["data"]]

    def get_user_mentions(
        self, user_id: int, fields: Sequence[TweetFields] = DEFAULT_TWEET_FIELDS
    ) -> list[Tweet]:
        """
        https://developer.twitter.com/en/docs/twitter-api/tweets/timelines/api-reference/get-users-id-mentions
        """
        params = {
            "tweet.fields": ",".join(fields),
        }
        resp = self.get(f"/2/users/{user_id}/mentions", params=params)
        return [Tweet(**e) for e in resp.json()["data"]]
