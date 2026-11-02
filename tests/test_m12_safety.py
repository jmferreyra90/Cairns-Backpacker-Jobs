"""Local, fully offline tests: no Gmail/Outlook/Supabase network requests."""
import asyncio
import base64
from email import policy
from email.parser import BytesParser
from types import SimpleNamespace

import httpx
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import Base
from app import models_accounts, models_selftest
from app.models_accounts import ApplicantAccount, ApplicationDraft
from app.models_selftest import SelfTestAttempt
from app.services.selftest_send import build_self_message, provider_self_send


def test_header_and_own_address_only(monkeypatch):
    account = SimpleNamespace(full_name='Alex Test', phone='0400000000')
    draft = SimpleNamespace(subject='Receptionist\r\nBCC: bad@example.com [Business Name]',
                            cover_letter='Hello [Business Name], from [Your Name].')
    sub, body = build_self_message(account, draft, 'Example Hotel', 'test.pdf')
    assert '\n' not in sub and '\r' not in sub
    assert 'Example Hotel' in body and 'Alex Test' in body

    requests = []

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return False
        async def post(self, url, **kwargs):
            requests.append((url, kwargs))
            return SimpleNamespace(status_code=200 if 'gmail' in url else 202)

    monkeypatch.setattr(httpx, 'AsyncClient', FakeAsyncClient)
    google = SimpleNamespace(provider='google', email='owner@example.com', access_token='DUMMY')
    assert asyncio.run(provider_self_send(google, sub, body, 'demo.pdf', b'%PDF-mock')) == 200
    sent = requests[-1][1]['json']['raw']
    message = BytesParser(policy=policy.default).parsebytes(base64.urlsafe_b64decode(sent))
    assert message['To'] == 'owner@example.com'
    assert message['From'] == 'owner@example.com'
    assert 'bad@example.com' not in (message['Bcc'] or '')
    assert 'business' not in message['To']
    assert len(list(message.iter_attachments())) == 1

    ms = SimpleNamespace(provider='microsoft', email='owner@example.com', access_token='DUMMY')
    assert asyncio.run(provider_self_send(ms, sub, body, 'demo.docx', b'fake')) == 202
    recipient = requests[-1][1]['json']['message']['toRecipients'][0]['emailAddress']['address']
    assert recipient == 'owner@example.com'


def test_database_uniqueness_one_attempt_per_draft():
    engine = create_engine('sqlite:///:memory:')
    with engine.connect().execution_options(schema_translate_map={'app_private': None}) as c:
        Base.metadata.create_all(bind=c)
        with Session(bind=c) as s:
            s.add(ApplicantAccount(id='account1', email='owner@example.com'))
            s.add(ApplicationDraft(id='draft1', account_id='account1', business_ids=[1],
                                   subject='Test', cover_letter='Hello'))
            s.commit()
            s.add(SelfTestAttempt(draft_id='draft1', account_id='account1',
                                  provider='google', recipient_email='owner@example.com'))
            s.commit()
            s.add(SelfTestAttempt(draft_id='draft1', account_id='account1',
                                  provider='google', recipient_email='owner@example.com'))
            try:
                s.commit()
            except IntegrityError:
                s.rollback()
            else:
                raise AssertionError('duplicate email attempt must be rejected')
