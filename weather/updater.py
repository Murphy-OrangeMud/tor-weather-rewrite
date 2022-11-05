from datetime import datetime
import logging
from smtplib import SMTPException

from weather.ctlutil import CtlUtil
from weather.model import BandwithSub, DeployedDatetime, Subscriber, Router, NodeDownSub, OutdatedVersionSub, DNSFailSub
from weather.model import db

import emails

def check_node_down(email_list):
    subs = NodeDownSub.query.all()

    for sub in subs:
        new_sub = sub
        if sub.subscriber.confirmed():
            if sub.triggered:
                new_sub.triggered = False
                new_sub.emailed = False
                new_sub.last_changed = datetime.now()

        else:
            if not sub.triggered:
                new_sub.triggered = True
                new_sub.last_changed = datetime.now()

            if sub.is_grace_passed() and sub.emailed == False:
                recipient = sub.subscriber.email
                fingerprint = sub.subscriber.router.fingerprint
                name = sub.subscriber.router.name
                grace_pd = sub.grace_pd
                unsubs_auth = sub.subscriber.unsubs_auth
                pref_auth = sub.subscriber.pref_auth

                email = emails.node_down_tuple(recipient, fingerprint, 
                                                   name, grace_pd,          
                                                   unsubs_auth, pref_auth)

                email_list.append(email)
                new_sub.emailed = True
        
        db.session.delete(sub)
        db.session.add(new_sub)
        db.session.commit()
        
    return email_list


def check_low_bandwith(ctl_util, email_list):
    subs = BandwithSub.query.all()

    for sub in subs:
        fingerprint = str(sub.subscriber.router.fingerprint)
        new_sub = sub

        if sub.subscriber.confirmed:
            bandwidth = ctl_util.get_bandwith(fingerprint)
            if bandwidth < sub.threshold:
                if sub.emailed == False:
                    recipient = sub.subscriber.email
                    name = sub.subscriber.router.name
                    threshold = sub.threshold
                    unsubs_auth = sub.subscriber.unsubs_auth
                    pref_auth = sub.subscriber.pref_auth
                    email = emails.bandwidth_tuple(recipient, 
                                                    fingerprint, name, bandwidth, threshold, unsubs_auth,
                                                    pref_auth)

                    email_list.append(email)
                    new_sub.emailed = True
            else:
                new_sub.emailed = False
            
            db.session.delete(sub)
            db.session.add(new_sub)
            db.session.commit()
    
    return email_list


def check_version(ctl_util, email_list):
    subs = OutdatedVersionSub.query.all()

    for sub in subs:
        if sub.subscriber.confirmed:
            fingerprint = str(sub.subscriber.router.fingerprint)
            version_type = ctl_util.get_version_type(fingerprint)
            new_sub = sub

            if version_type != 'ERROR':
                if version_type == 'OBSOLETE':
                    if sub.emailed == False:
                        fingerprint = sub.subscriber.router.fingerprint
                        name = sub.subscriber.router.name
                        recipient = sub.subscriber.email
                        unsubs_auth = sub.subscriber.unsubs_auth
                        pref_auth = sub.subscriber.pref_auth
                        email = emails.version_tuple(recipient, 
                                                    fingerprint,
                                                    name,
                                                    version_type,
                                                    unsubs_auth,
                                                   pref_auth)

                        email_list.append(email)
                        new_sub.emailed = True

                else:
                    new_sub.emailed = False
            else:
                logging.info("Couldn't parse the version relay %s is running" \
                              % str(sub.subscriber.router.fingerprint))
            
            db.session.delete(sub)
            db.session.add(new_sub)
            db.session.commit()

    return email_list


def check_dns_failure(ctl_util, email_list):
    pass


def check_all_subs(ctl_util, email_list):
    check_node_down(email_list)
    check_version(ctl_util, email_list)
    check_low_bandwith(ctl_util, email_list)
    check_dns_failure(ctl_util, email_list)


def update_all_routers(ctl_util, email_list):
    deployed_query = DeployedDatetime.query.all()
    if len(deployed_query) == 0:
        deployed = datetime.now()
        db.session.add(DeployedDatetime(deployed))
        db.session.commit()
    else:
        deployed = deployed_query[0].deployed
    
    if (datetime.now() - deployed).days < 2:
        fully_deployed = False
    else:
        fully_deployed = True

    router_set = Router.objects.all()
    for router in router_set:
        if (datetime.now() - router.last_seen).days > 365:
            db.session.delete(router)
        else:
            new_router = router
            new_router.up = False
            db.session.delete(router)
            db.session.add(new_router)

        db.session.commit()

    finger_name = ctl_util.get_finger_name_list()

    for router in finger_name:
        finger = router[0]
        name = router[1]

        if ctl_util.is_up_or_hibernaing(finger):
            router_data = None

            try:
                router_data = Router.query.filter_all(fingerprint=finger).first()
                new_router_data = router_data
                db.session.delete(router_data)
            except:
                if fully_deployed:
                    router_data = Router(name=name, fingerprint=finger, welcomed=False)
                else:
                    router_data = Router(name=name, fingerprint=finger, welcomed=True)

            new_router_data = router_data
            new_router_data.last_seen = datetime.now()
            new_router_data.name = name
            new_router_data.up = True
            new_router_data.exit = ctl_util.is_exit(finger)

            if router_data.welcomed == False and ctl_util.is_stable(finger):
                recipient = ctl_util.get_email(finger)
                is_exit = ctl_util.is_exit(finger)
                if not recipient == "":
                    email = emails.welcome_tuple(recipient, finger, name, is_exit)
                    email_list.append(email)

                new_router_data.welcomed = True

            db.session.add(new_router_data)
            db.session.commit()

    return email_list


def run_all():
    ctl_util = CtlUtil()
    email_list = []
    email_list = update_all_routers(ctl_util, email_list)
    email_list = check_all_subs(ctl_util, email_list)
    mails = tuple(email_list)

    # TODO: send mass email
    

            