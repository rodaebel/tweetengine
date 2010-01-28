import datetime
import logging
import urlparse

from google.appengine.api import users

from tweetengine.handlers import base
from tweetengine import model
from tweetengine import oauth

class TweetHandler(base.BaseHandler):
    @base.requires_account
    def post(self, account_name):
        permission = self.current_permission
        tweet = model.OutgoingTweet(account=self.current_account,
                                    user=self.user_account,
                                    message=self.request.get("tweet"))
        if permission.can_send():
            tweet.approved_by=self.user_account
            response = tweet.send()
            if response.status_code != 200:
                self.error(500)
                logging.error(response.content)
        elif permission.can_suggest():
            tweet.put()
        self.redirect("/%s/" % (account_name,))


def publishApprovedTweets():
    q = model.OutgoingTweet.all()
    q.filter("approved =", True)
    q.filter("sent =", False)
    q.filter("timestamp <", datetime.datetime.now())
    for tweet in q.fetch(20):
        tweet.send()
        logging.error('sending tweet %s' % tweet.message)
