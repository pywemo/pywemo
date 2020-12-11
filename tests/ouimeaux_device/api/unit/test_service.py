"""Tests for pywemo.ouimeaux_device.api.service."""

from xml.etree import cElementTree as cet
from xml.etree import ElementTree
import unittest.mock as mock
import pytest
import requests

import pywemo.ouimeaux_device.api.service as svc

HEADERS_KWARG_KEY = "headers"
CONTENT_TYPE_KEY = "Content-Type"
SOAPACTION_KEY = "SOAPACTION"

MOCK_ARGS_ORDERED = 0
MOCK_ARGS_KWARGS = 1

svc.LOG = mock.Mock()

MOCK_RESPONSE = (
    b'<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"'
    b' s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
    b'<s:Body>\n<u:GetInsightParamsResponse xmlns:u="urn:Belkin:service:metainfo:1">'
    b"\r\n<InsightParams>0|1604849509|85|1315|27628|1209600|772|0|21689183|386799026.000000|8000"
    b"</InsightParams>\r\n</u:GetInsightParamsResponse>\r\n</s:Body> </s:Envelope>"
)


class TestAction:
    @staticmethod
    def get_mock_action(name="", service_type="", url=""):
        device = mock.Mock()

        service = mock.Mock()
        service.serviceType = service_type
        service.controlURL = url

        action_config = mock.MagicMock()
        action_config.get_name = lambda: name

        return svc.Action(device, service, action_config)

    @staticmethod
    def get_et_mock():
        resp = cet.fromstring(MOCK_RESPONSE)
        return mock.MagicMock(return_value=resp)

    def test_call_post_request_is_made_exactly_once_when_successful(self):
        action = self.get_mock_action()
        requests.post = post_mock = mock.Mock()
        cet.fromstring = self.get_et_mock()

        action()

        assert post_mock.call_count == 1

    def test_call_request_has_well_formed_xml_body(self):
        action = self.get_mock_action(name="cool_name", service_type="service")
        requests.post = post_mock = mock.Mock()
        cet.fromstring = self.get_et_mock()

        action()

        body = post_mock.call_args[MOCK_ARGS_ORDERED][1]
        ElementTree.fromstring(body)  # will raise error if xml is malformed

    def test_call_request_has_correct_header_keys(self):
        action = self.get_mock_action()
        requests.post = post_mock = mock.Mock()

        action()

        headers = post_mock.call_args[MOCK_ARGS_KWARGS][HEADERS_KWARG_KEY]
        for header in [CONTENT_TYPE_KEY, SOAPACTION_KEY]:
            assert header in headers

    def test_call_headers_has_correct_content_type(self):
        action = self.get_mock_action()
        requests.post = post_mock = mock.Mock()

        action()

        headers = post_mock.call_args[MOCK_ARGS_KWARGS][HEADERS_KWARG_KEY]
        content_type_header = headers[CONTENT_TYPE_KEY]

        assert content_type_header == "text/xml"

    def test_call_headers_has_correct_soapaction(self):
        service_type = "some_service"
        name = "cool_name"
        action = self.get_mock_action(name, service_type)
        requests.post = post_mock = mock.Mock()

        action()

        headers = post_mock.call_args[MOCK_ARGS_KWARGS][HEADERS_KWARG_KEY]
        soapaction_header = headers[SOAPACTION_KEY]

        assert soapaction_header == '"%s#%s"' % (service_type, name)

    def test_call_headers_has_correct_url(self):
        url = "http://www.github.com/"
        action = self.get_mock_action(url=url)
        requests.post = post_mock = mock.Mock()

        action()

        actual_url = post_mock.call_args[MOCK_ARGS_ORDERED][0]
        assert actual_url == url

    def test_call_request_is_tried_up_to_max_on_communication_error(self):
        action = self.get_mock_action()
        requests.post = post_mock = mock.Mock(
            side_effect=requests.exceptions.RequestException
        )

        try:
            action()
        except svc.ActionException:
            pass

        assert post_mock.call_count == svc.MAX_RETRIES

    def test_call_throws_when_final_retry_fails(self):
        action = self.get_mock_action()
        requests.post = mock.Mock(
            side_effect=requests.exceptions.RequestException
        )

        with pytest.raises(svc.ActionException):
            action()

    def test_call_returns_correct_dictionary_with_response_contents(self):
        action = self.get_mock_action()
        requests.post = mock.Mock()

        envelope = cet.Element("soapEnvelope")
        body = cet.SubElement(envelope, "soapBody")
        response = cet.SubElement(body, "soapResponse")

        response_content = {
            "key1": "value1",
            "key2": "value2",
            "key3": "value3",
        }

        for key, value in response_content.items():
            element = cet.SubElement(response, key)
            element.text = value

        cet.fromstring = mock.MagicMock(return_value=envelope)

        actual_responses = action()

        assert actual_responses == response_content
