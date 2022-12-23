from vcr import VCR

from botwit.twitter_client import TwitterClient

from . import TWITTER_CASSETTES_DIR


def test_it_can_get_user(twitter: TwitterClient, vcr: VCR):
    with vcr.use_cassette(TWITTER_CASSETTES_DIR / "get_user_by_username.yaml"):
        user = twitter.get_user(username="@gjeusel")

    assert user.username == "Gjeusel"

    with vcr.use_cassette(TWITTER_CASSETTES_DIR / "get_user_by_id.yaml"):
        user_by_id = twitter.get_user(id=user.id)

    assert user == user_by_id


def test_it_can_get_tweets(twitter: TwitterClient, vcr: VCR):
    ids = [1605264002111643651, 1605198012636356608, 1604623003614154752]

    with vcr.use_cassette(TWITTER_CASSETTES_DIR / "get_tweets_by_ids.yaml"):
        tweets = twitter.get_tweets(ids)

    assert len(tweets) == 3


def test_it_can_get_tweet(twitter: TwitterClient, vcr: VCR):
    id = 1605264002111643651

    with vcr.use_cassette(TWITTER_CASSETTES_DIR / "get_tweet.yaml"):
        tweet = twitter.get_tweet(id)

    assert tweet.author_id
    assert not tweet.author  # is from expansions

    with vcr.use_cassette(TWITTER_CASSETTES_DIR / "get_tweet_with_expansions.yaml"):
        tweet = twitter.get_tweet(id, expansions=["author_id"])

    assert tweet.author
