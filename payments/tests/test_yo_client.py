"""
payments/tests/test_yo_client.py
Unit tests for YoPaymentsClient — XML building, response parsing,
endpoint fallback, and phone normalization.

Run with:
    python manage.py test payments.tests.test_yo_client
"""

import os
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch, call

from django.test import TestCase

os.environ.setdefault("YO_API_USERNAME", "test_user")
os.environ.setdefault("YO_API_PASSWORD", "test_pass")

from payments.yoo_client import YoPaymentsClient
from payments.exceptions import YoNetworkError, YoValidationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client():
    return YoPaymentsClient(username="test_user", password="test_pass")


def _xml_success(txn_ref="TXN-001", txn_status="SUCCEEDED"):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<AutoCreate>
  <Response>
    <Status>OK</Status>
    <StatusCode>0</StatusCode>
    <StatusMessage>Transaction initiated</StatusMessage>
    <TransactionStatus>{txn_status}</TransactionStatus>
    <TransactionReference>{txn_ref}</TransactionReference>
    <MNOTransactionReferenceId>MNO-999</MNOTransactionReferenceId>
  </Response>
</AutoCreate>"""


def _xml_pending(txn_ref="TXN-002"):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<AutoCreate>
  <Response>
    <Status>OK</Status>
    <StatusCode>1</StatusCode>
    <StatusMessage>Transaction pending</StatusMessage>
    <TransactionStatus>PENDING</TransactionStatus>
    <TransactionReference>{txn_ref}</TransactionReference>
  </Response>
</AutoCreate>"""


def _xml_error(code="E001", msg="Insufficient funds"):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<AutoCreate>
  <Response>
    <Status>ERROR</Status>
    <StatusCode>3</StatusCode>
    <StatusMessage>Transaction failed</StatusMessage>
    <ErrorMessageCode>{code}</ErrorMessageCode>
    <ErrorMessage>{msg}</ErrorMessage>
    <TransactionStatus>FAILED</TransactionStatus>
  </Response>
</AutoCreate>"""


# ---------------------------------------------------------------------------
# XML builder tests
# ---------------------------------------------------------------------------

class TestBuildXmlRequest(TestCase):

    def setUp(self):
        self.client = _make_client()

    def test_structure(self):
        xml = self.client._build_xml_request({"Method": "acdepositfunds", "Amount": "5000"})
        root = ET.fromstring(xml.replace('<?xml version="1.0" encoding="UTF-8"?>', ""))
        self.assertEqual(root.tag, "AutoCreate")
        req = root.find("Request")
        self.assertIsNotNone(req)
        self.assertEqual(req.find("APIUsername").text, "test_user")
        self.assertEqual(req.find("APIPassword").text, "test_pass")
        self.assertEqual(req.find("Method").text, "acdepositfunds")
        self.assertEqual(req.find("Amount").text, "5000")

    def test_credentials_not_in_fields(self):
        """Credentials must come from self, not from the fields dict."""
        xml = self.client._build_xml_request({"Method": "accheckbalance"})
        # Only one APIUsername tag should exist
        root = ET.fromstring(xml.replace('<?xml version="1.0" encoding="UTF-8"?>', ""))
        usernames = root.findall(".//APIUsername")
        self.assertEqual(len(usernames), 1)

    def test_xml_escaping(self):
        """Special characters in field values must be escaped by ElementTree."""
        xml = self.client._build_xml_request({"Narrative": "<test> & 'value'"})
        self.assertNotIn("<test>", xml)   # must be escaped
        self.assertIn("&lt;test&gt;", xml)


# ---------------------------------------------------------------------------
# XML response parser tests
# ---------------------------------------------------------------------------

class TestParseXmlResponse(TestCase):

    def setUp(self):
        self.client = _make_client()

    def test_parse_success(self):
        result = self.client._parse_xml_response(_xml_success())
        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["status_code"], "0")
        self.assertEqual(result["transaction_status"], "SUCCEEDED")
        self.assertEqual(result["transaction_reference"], "TXN-001")
        self.assertEqual(result["mno_reference"], "MNO-999")

    def test_parse_pending(self):
        result = self.client._parse_xml_response(_xml_pending())
        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["status_code"], "1")
        self.assertEqual(result["transaction_status"], "PENDING")

    def test_parse_error(self):
        result = self.client._parse_xml_response(_xml_error())
        self.assertEqual(result["status"], "ERROR")
        self.assertEqual(result["error_code"], "E001")
        self.assertEqual(result["error_message"], "Insufficient funds")
        self.assertEqual(result["transaction_status"], "FAILED")

    def test_parse_invalid_xml(self):
        result = self.client._parse_xml_response("not xml at all")
        self.assertEqual(result["status"], "ERROR")
        self.assertIn("Invalid XML", result["error_message"])

    def test_raw_preserved(self):
        raw = _xml_success()
        result = self.client._parse_xml_response(raw)
        self.assertEqual(result["raw"], raw)


# ---------------------------------------------------------------------------
# Response classification helpers
# ---------------------------------------------------------------------------

class TestResponseHelpers(TestCase):

    def test_is_success_ok_zero(self):
        self.assertTrue(YoPaymentsClient.is_success({"status": "OK", "status_code": "0"}))

    def test_is_success_txn_status(self):
        self.assertTrue(YoPaymentsClient.is_success({"status": "OK", "status_code": "1", "transaction_status": "SUCCEEDED"}))

    def test_is_pending_ok_one(self):
        self.assertTrue(YoPaymentsClient.is_pending({"status": "OK", "status_code": "1", "transaction_status": "PENDING"}))

    def test_is_error_status(self):
        self.assertTrue(YoPaymentsClient.is_error({"status": "ERROR"}))

    def test_is_error_txn_failed(self):
        self.assertTrue(YoPaymentsClient.is_error({"status": "OK", "transaction_status": "FAILED"}))

    def test_not_success_when_pending(self):
        self.assertFalse(YoPaymentsClient.is_success({"status": "OK", "status_code": "1", "transaction_status": "PENDING"}))


# ---------------------------------------------------------------------------
# Phone normalization
# ---------------------------------------------------------------------------

class TestNormalizePhone(TestCase):

    def test_plus_prefix(self):
        self.assertEqual(YoPaymentsClient._normalize_phone("+256771234567"), "256771234567")

    def test_leading_zero(self):
        self.assertEqual(YoPaymentsClient._normalize_phone("0771234567"), "256771234567")

    def test_already_256(self):
        self.assertEqual(YoPaymentsClient._normalize_phone("256771234567"), "256771234567")

    def test_spaces_stripped(self):
        self.assertEqual(YoPaymentsClient._normalize_phone("0771 234 567"), "256771234567")

    def test_validation_rejects_short(self):
        with self.assertRaises(YoValidationError):
            YoPaymentsClient._validate_phone("123")

    def test_validation_rejects_alpha(self):
        with self.assertRaises(YoValidationError):
            YoPaymentsClient._validate_phone("abcdefghij")


# ---------------------------------------------------------------------------
# Endpoint fallback (mock-based integration test)
# ---------------------------------------------------------------------------

class TestEndpointFallback(TestCase):

    def setUp(self):
        self.client = _make_client()

    @patch("payments.yoo_client.requests.post")
    def test_uses_primary_on_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = _xml_pending()
        mock_post.return_value = mock_resp

        result = self.client.check_balance()

        self.assertEqual(mock_post.call_count, 1)
        called_url = mock_post.call_args[0][0]
        self.assertIn("paymentsapi1", called_url)
        self.assertEqual(result["status"], "OK")

    @patch("payments.yoo_client.requests.post")
    def test_falls_back_to_backup_on_timeout(self, mock_post):
        import requests as req_lib

        success_resp = MagicMock()
        success_resp.status_code = 200
        success_resp.text = _xml_pending()

        # First call (primary) raises Timeout, second call (backup) succeeds
        mock_post.side_effect = [req_lib.Timeout(), success_resp]

        result = self.client.check_balance()

        self.assertEqual(mock_post.call_count, 2)
        backup_url = mock_post.call_args[0][0]
        self.assertIn("paymentsapi2", backup_url)
        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["_endpoint"], self.client._endpoints[1])

    @patch("payments.yoo_client.requests.post")
    def test_raises_network_error_when_all_fail(self, mock_post):
        import requests as req_lib
        mock_post.side_effect = req_lib.ConnectionError("unreachable")

        with self.assertRaises(YoNetworkError):
            self.client.check_balance()

        self.assertEqual(mock_post.call_count, 2)

    @patch("payments.yoo_client.requests.post")
    def test_correct_headers_sent(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = _xml_pending()
        mock_post.return_value = mock_resp

        self.client.check_balance()

        _, kwargs = mock_post.call_args
        headers = kwargs.get("headers") or mock_post.call_args[1].get("headers", {})
        self.assertEqual(headers.get("Content-Type"), "text/xml")
        self.assertEqual(headers.get("Content-transfer-encoding"), "text")
