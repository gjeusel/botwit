from __future__ import annotations

from datetime import datetime
from typing import Any, Generator, Literal, Sequence, TypedDict

import httpx
import httpx_auth
import structlog
from pydantic import BaseModel, Field, root_validator
from typing_extensions import NotRequired

logger = structlog.getLogger(__name__)


class TwitterError(Exception):
    def __init__(
        self, *, message: str | None = None, payload: list[dict[str, Any]] | None = None
    ):
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
        self.message = message
        self.payload = payload
        super().__init__(message, payload)

    def __str__(self) -> str:
        if self.payload:
            errs = [
                f"{e['resource_type']} '{e['title']}': {e['detail']}"
                for e in self.payload
            ]
            if len(errs) > 1:
                errs.insert(0, "Had several issues.")
                return "\n  - ".join(errs)
            else:
                return errs[0]
        elif self.message:
            return self.message
        else:
            raise super().__str__()  # type: ignore


def handle_http_error(response: httpx.Response) -> httpx.Response:
    if response.is_error:
        response.read()  # ensure response is read before parsing json
        data = response.json()
        req = response.request
        errors = data["errors"]
        if len(errors) > 1:
            raise NotImplementedError

        error = errors[0]
        logger.error(f"Failed {req.method} - {req.url.path}.", **error)
        raise TwitterError(message=error["message"])

    return response


def handle_twitter_error(response: httpx.Response) -> httpx.Response:
    response.read()  # ensure response is read before parsing json
    data = response.json()
    if data.get("errors"):
        raise TwitterError(payload=data.get("errors"))
    return response


class TwitterTokenCache(httpx_auth.oauth2_tokens.TokenMemoryCache):
    NO_EXPIRY = 2524608000  # "2050-01-01T00:00:00+00:00"

    def _add_bearer_token(self, key: str, token: str) -> None:
        if not token:
            raise httpx_auth.errors.InvalidToken(token)

        self._add_token(key=key, token=token, expiry=self.NO_EXPIRY)


class TwitterOAuth2ClientCredentials(httpx_auth.OAuth2ClientCredentials):
    # https://developer.twitter.com/en/docs/authentication/api-reference/token

    token_cache = TwitterTokenCache()  # type: ignore

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
    conversation_id: int

    in_reply_to_user_id: int | None = None

    referenced_tweets: list[dict[str, str]] = Field(default_factory=list)

    # coming from expansions:
    users: list[User] = Field(default_factory=list)
    tweets: list[Tweet] = Field(default_factory=list)

    unmapped: dict[str, Any] = Field(default_factory=dict)

    @root_validator(pre=True)
    def _fill_unmapped(cls, values: dict[str, Any]) -> dict[str, Any]:
        unmapped: dict[str, Any] = {}
        for key, value in values.items():
            if key not in cls.__fields__:
                unmapped[key] = value

        return values | {"unmapped": unmapped}

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> Tweet:
        kwargs = payload["data"]

        if payload.get("includes"):
            kwargs |= payload["includes"]

        return cls(**kwargs)

    @property
    def author(self) -> User | None:
        return {u.id: u for u in self.users or []}.get(self.author_id)

    @property
    def url(self) -> str:
        if self.author:
            return f"https://twitter.com/{self.author.username}/status/{self.id}"
        else:
            raise TwitterError(
                message=f"Can't build url while missing author username ({self!r}) "
            )

    def __repr__(self) -> str:
        core = f"Tweet n°{self.id}"

        if self.author is not None:
            core = f"{core} - {self.author.username}"

        text_peek_max_len = 30
        text = self.text
        if len(text) > text_peek_max_len:
            text = text[:text_peek_max_len] + "..."

        return f"<{core}> {text}"


def _parse_tweets_payload(payload: dict[str, Any]) -> list[Tweet]:
    if "data" not in payload:
        return []

    data = payload["data"]
    included_tweets = payload.get("includes", {}).get("tweets", [])
    included_users = payload.get("includes", {}).get("users", [])
    if isinstance(data, dict):
        data.update({"tweets": included_tweets, "users": included_users})
        return [Tweet(**data)]
    else:
        map_id_includes = {
            t["id"]: t
            | {"users": [u for u in included_users if u["id"] == t["author_id"]]}
            for t in included_tweets
        }
        tweets: list[Tweet] = []
        for tweet in data:
            if "referenced_tweets" in tweet:
                included_tweets = [
                    map_id_includes[e["id"]] for e in tweet["referenced_tweets"]
                ]
                tweet.update({"tweets": included_tweets, "users": included_users})
            tweets.append(Tweet(**tweet))
        return tweets


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

DEFAULT_TWEET_FIELDS: tuple[TweetFields, ...] = (
    "id",
    "author_id",
    "created_at",
    "text",
    "conversation_id",
)


class PaginationParams(TypedDict):
    max_results: NotRequired[int]


class TweetQueryParams(TypedDict):
    fields: NotRequired[Sequence[TweetFields]]
    expansions: NotRequired[Sequence[TweetExpansions]]


class PagTweetQueryParams(PaginationParams, TweetQueryParams):
    pass


# Note typing: can't use new peps
#  - PEP 692 - Using TypedDict for more precise **kwargs typing (https://peps.python.org/pep-0692/)
#  - PEP 655 – Marking individual TypedDict items as required or potentially-missing (https://peps.python.org/pep-0655/#usage-in-python-3-11)
#
#    def get_tweets(
#        self,
#        ids: Sequence[int],
#        *,
#        **kwargs: **TweetQueryParams,
#    ) -> list[Tweet]:
#
# The reason is because it breaks black formatting & ruff linting.


def _parse_params(params: PagTweetQueryParams) -> dict[str, Any]:
    sain_params: dict[str, Any] = {
        "tweet.fields": ",".join(
            sorted(set(params.get("fields", ())) | set(DEFAULT_TWEET_FIELDS))
        ),
        "expansions": ",".join(sorted(params.get("expansions", ()))),
    }
    if params.get("max_results"):
        sain_params["max_results"] = params["max_results"]

    return sain_params


class TwitterClient(httpx.Client):
    auth: TwitterOAuth2ClientCredentials

    def __init__(
        self,
        consumer_key: str,
        consumer_secret: str,
        base_url: str = "https://api.twitter.com",
        **kwargs: Any,
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
                    handle_http_error,
                    handle_twitter_error,
                ],
            },
        } | kwargs
        super().__init__(base_url=base_url, auth=auth, **kwargs)  # type: ignore

    def get_user(self, *, username: str | None = None, id: int | None = None) -> User:
        if username:
            username = username.lstrip("@")
            resp = self.get(f"/2/users/by/username/{username}")
        else:
            resp = self.get(f"/2/users/{id}")
        return User(**resp.json()["data"])

    def get_tweets(
        self,
        ids: Sequence[int],
        *,
        fields: Sequence[TweetFields] = DEFAULT_TWEET_FIELDS,
        expansions: Sequence[TweetExpansions] = (),
    ) -> list[Tweet]:
        """
        https://developer.twitter.com/en/docs/twitter-api/tweets/lookup/api-reference/get-tweets
        """
        params = {
            "ids": ",".join(str(e) for e in ids),
        }
        resp = self.get(
            "/2/tweets",
            params=params | _parse_params({"fields": fields, "expansions": expansions}),
        )
        return _parse_tweets_payload(resp.json())

    def get_tweet(
        self,
        id: int,
        *,
        fields: Sequence[TweetFields] = DEFAULT_TWEET_FIELDS,
        expansions: Sequence[TweetExpansions] = (),
    ) -> Tweet:
        """
        https://developer.twitter.com/en/docs/twitter-api/tweets/lookup/api-reference/get-tweets-id
        """
        resp = self.get(
            f"/2/tweets/{id}",
            params=_parse_params({"fields": fields, "expansions": expansions}),
        )
        return _parse_tweets_payload(resp.json())[0]

    # _______ Search endpoint _______

    def search_tweets(
        self,
        query: str,
        *,
        fields: Sequence[TweetFields] = DEFAULT_TWEET_FIELDS,
        expansions: Sequence[TweetExpansions] = (),
    ) -> list[Tweet]:
        """
        https://developer.twitter.com/en/docs/twitter-api/tweets/search/api-reference/get-tweets-search-recent
        Query Builder Tool: https://developer.twitter.com/apitools/query?query=
        """
        resp = self.get(
            "/2/tweets/search/recent",
            params={"query": query}
            | _parse_params({"fields": fields, "expansions": expansions}),
        )
        return _parse_tweets_payload(resp.json())

    # _______  Timelines endpoint _______

    def get_user_tweets(
        self,
        user_id: int,
        *,
        fields: Sequence[TweetFields] = DEFAULT_TWEET_FIELDS,
    ) -> list[Tweet]:
        """
        https://developer.twitter.com/en/docs/twitter-api/tweets/timelines/api-reference/get-users-id-tweets
        """
        resp = self.get(
            f"/2/users/{user_id}/tweets",
            params=_parse_params({"fields": fields}),
        )
        return _parse_tweets_payload(resp.json())

    def get_user_mentions(
        self,
        user_id: int,
        *,
        fields: Sequence[TweetFields] = DEFAULT_TWEET_FIELDS,
        expansions: Sequence[TweetExpansions] = (),
    ) -> list[Tweet]:
        """
        https://developer.twitter.com/en/docs/twitter-api/tweets/timelines/api-reference/get-users-id-mentions
        """
        resp = self.get(
            f"/2/users/{user_id}/mentions",
            params=_parse_params({"fields": fields, "expansions": expansions}),
        )
        return _parse_tweets_payload(resp.json())
