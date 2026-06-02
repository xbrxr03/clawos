# SPDX-License-Identifier: AGPL-3.0-or-later
"""Tests for maild — Email service."""
import pytest
from unittest.mock import patch, MagicMock
from services.maild.engine import MailConfig, EmailMessage, check_mail, send_mail


class TestMailConfig:
    def test_defaults(self):
        cfg = MailConfig()
        assert cfg.imap_host == ""
        assert cfg.imap_port == 993
        assert cfg.use_ssl is True

    def test_load_missing_config(self):
        cfg = MailConfig.load()
        # Should return defaults when config not available
        assert isinstance(cfg, MailConfig)


class TestEmailMessage:
    def test_create(self):
        msg = EmailMessage(id="1", sender="a@b.com", subject="Hello", body="World")
        assert msg.read is False
        assert msg.folder == "INBOX"

    def test_to_dict(self):
        msg = EmailMessage(id="1", sender="a@b.com", subject="Hi")
        d = msg.to_dict()
        assert d["sender"] == "a@b.com"


class TestCheckMail:
    def test_no_config(self):
        cfg = MailConfig()  # empty config
        result = check_mail(config=cfg)
        assert result == []

    def test_imap_failure(self):
        with patch("imaplib.IMAP4_SSL", side_effect=Exception("Connection refused")):
            cfg = MailConfig(imap_host="imap.fake.com", username="test@test.com", password="wrong")
            result = check_mail(config=cfg, limit=5)
            assert isinstance(result, list)


class TestSendMail:
    def test_no_config(self):
        cfg = MailConfig()  # empty
        assert send_mail(to="a@b.com", subject="Test", body="hi", config=cfg) is False

    def test_smtp_failure(self):
        with patch("smtplib.SMTP", side_effect=Exception("Connection refused")):
            cfg = MailConfig(smtp_host="smtp.fake.com", username="test@test.com", password="wrong")
            result = send_mail(to="a@b.com", subject="Test", body="hi", config=cfg)
            assert result is False