from __future__ import annotations

from botwit.config import CFG
from botwit.twitter_client import TwitterClient


def main():
    twitter = TwitterClient(
        # access_token_key=CFG.TWITTER_ACCESS_TOKEN,
        # access_token_secret=CFG.TWITTER_ACCESS_TOKEN_SECRET,
        consumer_key=CFG.TWITTER_CONSUMER_KEY,
        consumer_secret=CFG.TWITTER_CONSUMER_SECRET,
    )

    # tweets = twitter.get_tweets([1261326399320715264, 1278347468690915330])
    # user = twitter.get_user("@trashh_dev")

    user = twitter.get_user("@gjeusel")
    # tweets = twitter.get_user_tweets(user.id)
    mentions = twitter.get_user_mentions(user.id)

    latest_mention = max(mentions, key=lambda x: x.created_at)

    tweet = twitter.get_tweet(
        latest_mention.id,
        expansions=[
            "referenced_tweets.id",
            "referenced_tweets.id.author_id",
        ],
    )


if __name__ == "__main__":
    main()
