import base64
from datetime import datetime
import re

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relation

import base64
import os
from .config import config

engine = create_engine(config.sql_alchemy_uri)
# db_session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

Base = declarative_base()
Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def insert_fingerprint_spaces(fingerprint):
    return ' '.join(re.findall('.{4}', str(fingerprint)))

def get_rand_string():
    r = base64.urlsafe_b64encode(os.urandom(18))

    if r.endswith(bytes("-", encoding='utf-8')):
        r = r.replace(bytes("-", encoding='utf-8'), bytes("x", encoding='utf-8'))
    return r

def hours_since(time):
    delta = datetime.now() - time
    hours = (delta.days * 24) + (delta.seconds / 3600)
    return hours


class Router(Base):

    __tablename__ = "router"

    fingerprint = Column(String, primary_key=True, unique=True)
    name = Column(String)
    welcomed = Column(Boolean)
    last_seen = Column(DateTime)
    up = Column(Boolean)
    exit = Column(Boolean)

    subscriber_id = Column(String, ForeignKey('subscriber.email'))
    subscriber = relation("Subscriber", backref='routers', lazy=False)

    #subscriptions = relation('Subscription', backref='router', lazy=False)

    def __init__(self, fingerprint=None,
                       subscriber=None,
                       name='Unnamed',
                       welcomed=False,
                       last_seen=None,
                       up=True,
                       exit=False):
        super().__init__()
        self.fingerprint = fingerprint
        self.welcomed = welcomed
        self.name = name
        if last_seen is None:
            last_seen = datetime.now()
        self.last_seen = last_seen
        self.up = up
        self.exit = exit
        self.subscriber_id = subscriber

    def __repr__(self):
        return "<Router: %s %s %s %s %s %s>" % (self.fingerprint, self.name, self.welcomed, self.last_seen, self.up, self.exit)

    def _spaced_fingerprint(self):
        return insert_fingerprint_spaces(self.fingerprint)


class Subscriber(Base):

    __tablename__ = "subscriber"

    email = Column(String, primary_key=True, unique=True)
    # router = Column(String, ForeignKey(Router.fingerprint), primary_key=True)
    sub_date = Column(DateTime)

    # routers = relation('Router', backref='subscriber', lazy=False)

    def __init__(self, email=None):
        super().__init__()
        self.email = email
        self.sub_date = datetime.now()

    def __repr__(self):
        return self.email


class Subscription(Base):

    __tablename__ = "subscription"

    id = Column(String, primary_key=True, unique=True, default=get_rand_string)
    # subscriber_id = Column(String, ForeignKey(Subscriber.email))
    router = relation('Router', backref='subscriptions', lazy=False)
    router_id = Column(String, ForeignKey(Router.fingerprint))
    emailed = Column(Boolean, default=False)
    type=Column(String)

    __mapper_args__ = {
        'polymorphic_identity': 'subscriptions',
        'with_polymorphic': '*',
        "polymorphic_on": type
    }

    def __repr__(self):
        return "<Subscription: %s %s %s %s>" % (self.id, self.router_id, self.emailed, self.router)

    # subscriber = relation('Subscriber', foreign_keys='Subscriber.email')
    # router = relation('Router', back_populates='subscriptions')

    """
    def __init__(self, router, emailed=False):
        super().__init__()
        self.id = get_rand_string()
        self.router = router
        self.emailed = emailed
    """


class NodeDownSub(Subscription):
    triggered = Column(Boolean, default=False)
    grace_pd = Column(Integer)
    last_changed = Column(DateTime, default=datetime.now)

    """
    def __init__(self, router, emailed=False, grace_pd=config.grace_pd, last_changed=None):
        super().__init__(router, emailed)
        self.grace_pd = grace_pd
        if last_changed is None:
            last_changed = datetime.now()
        self.last_changed = last_changed
    """

    __mapper_args__ = {
        'polymorphic_identity': 'nodedownsub',
        'with_polymorphic': '*'
    }


class OutdatedVersionSub(Subscription):
    notify_type = Column(String, default='OBSOLETE')

    """
    def __init__(self, router, emailed=False, notify_type='OBSOLETE'):
        super().__init__(router, emailed)
        self.notify_type = notify_type
    """

    __mapper_args__ = {
        'polymorphic_identity': 'outdatedversionsub',
        'with_polymorphic': '*'
    }

class BandwithSub(Subscription):
    threshold = Column(Integer, default=20)

    """
    def __init__(self, router, emailed=False, threshold=20):
        super().__init__(router, emailed)
        self.threshold = threshold
    """

    __mapper_args__ = {
        'polymorphic_identity': 'bandwithsub',
        'with_polymorphic': '*'
    }


class DNSFailSub(Subscription):
    """
    def __init__(self, router, emailed=False):
        super().__init__(router, emailed)
    """

    __mapper_args__ = {
        'polymorphic_identity': 'dnsfailsub',
        'with_polymorphic': '*'
    }


class DeployedDatetime(Base):

    __tablename__ = "deployeddatetime"
    
    deployed = Column(DateTime, primary_key=True)

    def __init__(self, deployed):
        super().__init__()
        self.deployed = deployed

    def __repr__(self):
        return self.deployed

def init_db():
    Base.metadata.create_all(engine)

