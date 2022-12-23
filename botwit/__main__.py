from __future__ import annotations

import argparse
from bdb import BdbQuit
from dataclasses import dataclass
from typing import Any

import pytz
import structlog
from notion_client import Client as NotionClient

from botwit.config import CFG
from botwit.twitter_client import Tweet, TwitterClient
from botwit.twitter_client import User as TwitterUser

logger = structlog.getLogger("botwit")


@dataclass(repr=False)
class TweetMemo:
    me: TwitterUser
    author: TwitterUser
    my_tweet: Tweet
    conversation: list[Tweet]

    @property
    def tags(self) -> set[str]:
        parts = set(self.my_tweet.text.split(" "))
        tags = [e for e in parts if not e.startswith("@") and e not in ["notion"]]
        return set(tags)

    @property
    def thread_text(self) -> str:
        parts = [tweet.text for tweet in self.conversation]
        return "\n\n".join(parts)

    @property
    def date(self) -> str:
        cet = pytz.timezone("Europe/Paris")
        return self.my_tweet.created_at.astimezone(cet).strftime("%Y-%m-%d")

    def __repr__(self) -> str:
        return f"<Memo> @{self.author.username} - {len(self.conversation)} tweets"


def get_recent_memos(twitter: TwitterClient, user: TwitterUser) -> list[TweetMemo]:
    """Get recent memos from twitter."""
    mentions = twitter.search_tweets(
        query=f"from:{user.id} is:reply {user.username}",
        expansions=["referenced_tweets.id", "referenced_tweets.id.author_id"],
    )

    memos: list[TweetMemo] = []
    for mention in mentions:
        if not mention.tweets:
            raise RuntimeError(f"Not referenced tweets linked to {mention!r}")
        elif len(mention.tweets) > 1:
            raise NotImplementedError(
                f"Multiple referenced tweets linked to {mention!r}"
            )

        target_tweet = mention.tweets[0]
        if not target_tweet.author:
            raise RuntimeError(f"Failed to fetch author on {target_tweet!r}")

        conversation = twitter.search_tweets(
            query=" ".join(
                [
                    f"conversation_id:{target_tweet.conversation_id}",  # within this conversation
                    f"from:{target_tweet.author_id}",  # from the author
                    f"to:{target_tweet.author_id}",  # in reply to the author for threads
                ],
            ),
        )
        for tweet in conversation:
            tweet.users = target_tweet.users

        conversation.insert(0, target_tweet)
        conversation.sort(key=lambda tweet: tweet.created_at)

        memos.append(
            TweetMemo(
                me=user,
                author=target_tweet.author,
                my_tweet=mention,
                conversation=conversation,
            )
        )

    return memos


def create_new_memo(notion: NotionClient, memo: TweetMemo) -> dict[str, Any]:
    """Create new memos in my notion."""
    tags = [{"name": tag} for tag in memo.tags]

    children = [
        # https://developers.notion.com/reference/block#embed-blocks
        {
            "object": "block",
            "type": "embed",
            "embed": {"url": tweet.url},
        }
        for tweet in memo.conversation
    ]

    root_tweet = memo.conversation[0]

    payload = {
        "parent": {"database_id": CFG.NOTION_DATABASE_ID},
        "children": children,
        "icon": {"emoji": "🪶"},
        "properties": {
            "URL": {"url": root_tweet.url},
            "Content": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": root_tweet.text,
                            "link": {"url": root_tweet.url},
                        },
                    }
                ]
            },
            "tweet_date": {"date": {"start": memo.date}},
            "Tags": {"multi_select": tags},
            "Author": {
                "title": [
                    {
                        "text": {"content": f"@{memo.author.username}"},
                    }
                ]
            },
        },
    }

    logger.info(f"Creating a new page for memo: {memo!r}")
    return notion.pages.create(**payload)  # type: ignore


def main() -> None:
    twitter = TwitterClient(
        consumer_key=CFG.TWITTER_CONSUMER_KEY.get_secret_value(),
        consumer_secret=CFG.TWITTER_CONSUMER_SECRET.get_secret_value(),
    )

    user = twitter.get_user(username="@gjeusel")

    memos = get_recent_memos(twitter=twitter, user=user)

    # https://developers.notion.com/reference
    notion = NotionClient(auth=CFG.NOTION_SECRET_KEY.get_secret_value())
    database = notion.databases.query(database_id=CFG.NOTION_DATABASE_ID)

    already_stored: set[str] = set()
    for row in database["results"]:  # type: ignore
        tweet_url = row["properties"]["URL"]["url"]
        if tweet_url is not None:
            already_stored.add(tweet_url)

    new_memos = [
        memo for memo in memos if memo.conversation[0].url not in already_stored
    ]
    if len(new_memos) == 0:
        logger.info("Found no new memo.")
        return

    logger.info(f"Found {len(new_memos)} new memos.")

    for memo in new_memos:
        create_new_memo(notion=notion, memo=memo)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    if args.debug:
        try:
            main()
        except BdbQuit:
            pass
        except Exception:
            __import__("pdb").post_mortem()  # POSTMORTEM
    else:
        main()
