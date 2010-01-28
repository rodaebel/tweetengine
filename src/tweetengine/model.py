import datetime
from google.appengine.api import urlfetch
from google.appengine.ext import db
from google.appengine.ext.db import polymodel

from tweetengine import oauth

class UserAccount(polymodel.PolyModel):
    def get_username(self):
        raise NotImplementedError()


class GoogleUserAccount(UserAccount):
    user = db.UserProperty(required=True)

    def get_username(self):
        return self.user.email()


ROLE_ANYONE = 0
ROLE_USER = 1
ROLE_ADMINISTRATOR = 2

ROLES = [
    (ROLE_ANYONE, "Anyone"),
    (ROLE_USER, "User"),
    (ROLE_ADMINISTRATOR, "Administrator")
]
ROLE_IDS = [id for id,name in ROLES]


class TwitterAccount(db.Model):
    oauth_token = db.TextProperty(required=True)
    oauth_secret = db.TextProperty(required=True)
    name = db.TextProperty()
    picture = db.TextProperty()
    
    # Permission levels
    suggest_tweets = db.IntegerProperty(required=True, choices=ROLE_IDS,
                                        default=ROLE_ANYONE)
    send_tweets = db.IntegerProperty(required=True, choices=ROLE_IDS,
                                     default=ROLE_USER)
    review_tweets = db.IntegerProperty(required=True, choices=ROLE_IDS,
                                       default=ROLE_USER)

    @property
    def username(self):
        return self.key().name()

    def make_request(self, url, additional_params=None, method=urlfetch.POST):
        client = Configuration.instance().get_client("")
        return client.make_request(
            url,
            token=self.oauth_token,
            secret=self.oauth_secret,
            additional_params=additional_params,
            protected=True,
            method=method)
        
    def prepare_request(self, url, additional_params=None, 
                        method=urlfetch.GET):
        client = Configuration.instance().get_client("")
        return client.prepare_request(
            url,
            token=self.oauth_token,
            secret=self.oauth_secret,
            additional_params=additional_params,
            method=method)


def _normalize_key_name(key):
    if isinstance(key, db.Model):
        key = key.key()
    if isinstance(key, db.Key):
        key = key.id_or_name()
    return key


class Permission(db.Model):
    user = db.ReferenceProperty(UserAccount, required=True)
    account = db.ReferenceProperty(TwitterAccount, required=True)
    role = db.IntegerProperty(required=True,
                              choices=ROLE_IDS)
    invite_nonce = db.StringProperty()

    @classmethod
    def create(cls, user, account, role, invite_nonce=None):
        user_name = _normalize_key_name(user)
        account_name = _normalize_key_name(account)
        key_name = "%s:%s" % (user_name, account_name)
        return cls(
            key_name=key_name,
            user=user,
            account=account,
            role=role,
            invite_nonce=invite_nonce)

    @classmethod
    def find(cls, user, account):
        user = _normalize_key_name(user)
        account = _normalize_key_name(account)
        key_name = "%s:%s" % (user, account)
        return cls.get_by_key_name(key_name)

    def can_suggest(self):
        return self.role >= self.account.suggest_tweets
    
    def can_send(self):
        return self.role >= self.account.send_tweets
    
    def can_review(self):
        return self.role >= self.account.review_tweets


class OutgoingTweet(db.Model):
    account = db.ReferenceProperty(TwitterAccount, required=True)
    user = db.ReferenceProperty(UserAccount, required=True,
                                collection_name='tweets')
    approved_by = db.ReferenceProperty(UserAccount,
                                       collection_name='approved_tweets')
    message = db.TextProperty(required=True)
    timestamp = db.DateTimeProperty()
    sent = db.BooleanProperty(required=True, default=False)
    approved = db.BooleanProperty(required=True, default=False)

    def send(self):
        response = self.account.make_request(
            "http://twitter.com/statuses/update.json",
            additional_params={"status": self.message})
        if response.status_code == 200:
            self.sent = True
            self.timestamp = datetime.datetime.now()
            self.put()
        return response


class Configuration(db.Model):
    INSTANCE = None
    
    oauth_secret = db.StringProperty()
    oauth_key = db.StringProperty()
    mail_from = db.StringProperty()
    allow_public = db.BooleanProperty(required=True, default=False)
    
    @classmethod
    def instance(cls):
        if not cls.INSTANCE:
            cls.INSTANCE = cls.get_or_insert('oauthkey')
        return cls.INSTANCE

    def get_client(self, callback_url):
        return oauth.TwitterClient(self.oauth_key, self.oauth_secret,
                                   callback_url)
