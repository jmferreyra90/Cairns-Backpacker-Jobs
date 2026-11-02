"""Focused integration checks; run from the root of an existing project."""
import asyncio
from types import SimpleNamespace

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Business
from app.models_business_emails import BusinessExtraEmail
from app.services.business_recipients import approved_recipients
from app.services.mail_api import send_employer_application, send_self_test
from app.services.session_store import Draft, Connection


def test_business_emails_approval():
    engine = create_engine('sqlite://', connect_args={'check_same_thread':False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[Business.__table__, BusinessExtraEmail.__table__])
    Session = sessionmaker(bind=engine)
    with Session() as db:
        biz = Business(name='Test Restaurant', category='Restaurant', active=True)
        db.add(biz)
        db.flush()
        biz.email='info@testrestaurant.com'; biz.email_verified=True
        db.add_all([
            BusinessExtraEmail(business_id=biz.id,email='manager@testrestaurant.com',approved=True),
            BusinessExtraEmail(business_id=biz.id,email='nonapproved@testrestaurant.com',approved=False),
        ])
        db.commit()
        assert approved_recipients(db,biz)==['info@testrestaurant.com','manager@testrestaurant.com']


def test_outlook_multi_recipient_keeps_self_test_single(monkeypatch):
    requests=[]
    class FakeClient:
        def __init__(self,*a,**kw):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*a):pass
        async def post(self,url,**kw):
            requests.append((url,kw))
            return httpx.Response(202,request=httpx.Request('POST',url))
    monkeypatch.setattr(httpx,'AsyncClient',FakeClient)
    conn=Connection('microsoft','owner@example.com','dummy',9999999999)
    draft=Draft((1,),'Test','owner@example.com','0400000000','Job','I can work','test.pdf',b'%PDF-1.4',False,False,0)
    asyncio.run(send_employer_application(conn,draft,dict(to='front@cafecairns.com, manager@cafecairns.com',subject='Job',body='Hello')))
    recipients=requests[-1][1]['json']['message']['toRecipients']
    assert [x['emailAddress']['address'] for x in recipients]==['front@cafecairns.com','manager@cafecairns.com']
    asyncio.run(send_self_test(conn,draft,dict(subject='Job',business_name='Cafe',body='Hello')))
    recipients=requests[-1][1]['json']['message']['toRecipients']
    assert [x['emailAddress']['address'] for x in recipients]==['owner@example.com']


def test_seven_day_duplicate_window():
    from datetime import datetime, timedelta, timezone
    from app.models_campaign import Campaign, CampaignAttempt
    from app.services.campaign_queue import recently_contacted_ids
    engine = create_engine('sqlite://', connect_args={'check_same_thread':False}, poolclass=StaticPool)
    Base.metadata.create_all(engine, tables=[Campaign.__table__, CampaignAttempt.__table__])
    Session = sessionmaker(bind=engine)
    with Session() as db:
        campaign = Campaign(session_hash='a'*64, sender_email='sender@example.com', provider='google', mode='real', status='completed')
        db.add(campaign); db.flush()
        db.add(CampaignAttempt(campaign_id=campaign.id,business_id=1,business_name='Old Cafe',recipient_email='old@cafe.test',status='accepted',attempted_at=datetime.now(timezone.utc)-timedelta(days=8)))
        db.add(CampaignAttempt(campaign_id=campaign.id,business_id=2,business_name='Recent Cafe',recipient_email='recent@cafe.test',status='uncertain',attempted_at=datetime.now(timezone.utc)-timedelta(days=2)))
        db.commit()
        assert recently_contacted_ids(db, 'sender@example.com', [1,2,3]) == {2}
