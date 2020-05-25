"""Tests for pywemo.ouimeaux_device.api.service."""

from xml.etree import cElementTree as et
import mock
import pytest
import requests

import pywemo.ouimeaux_device.api.service as svc

HEADERS_KWARG_KEY = 'headers'
CONTENT_TYPE_KEY = 'Content-Type'
SOAPACTION_KEY = 'SOAPACTION'

svc.LOG = mock.Mock()


class TestAction:
    @staticmethod
    def get_mock_action(name="", service_type=""):
        device = mock.Mock()

        service = mock.Mock()
        service.serviceType = service_type

        action_config = mock.MagicMock()
        action_config.get_name = lambda: name

        return svc.Action(device, service, action_config)

    def test_call_post_request_is_made_exactly_once_when_successful(self):
        action = self.get_mock_action()
        requests.post = mock.Mock()
        et.fromstring = mock.MagicMock()

        action()

        requests.post.assert_called_once()

    def test_call_request_has_correct_headers(self):
        action = self.get_mock_action()
        requests.post = post_mock = mock.Mock()
        et.fromstring = mock.MagicMock()

        action()

        headers = post_mock.call_args.kwargs[HEADERS_KWARG_KEY]
        for header in [CONTENT_TYPE_KEY, SOAPACTION_KEY]:
            assert header in headers

    def test_call_headers_has_correct_content_type(self):
        action = self.get_mock_action()
        requests.post = post_mock = mock.Mock()
        et.fromstring = mock.MagicMock()

        action()

        headers = post_mock.call_args.kwargs[HEADERS_KWARG_KEY]
        content_type_header = headers[CONTENT_TYPE_KEY]

        assert content_type_header == "text/xml"

    def test_call_headers_has_correct_soapaction(self):
        service_type = "some_service"
        name = "cool_name"
        action = self.get_mock_action(name, service_type)
        requests.post = post_mock = mock.Mock()
        et.fromstring = mock.MagicMock()

        action()

        headers = post_mock.call_args.kwargs[HEADERS_KWARG_KEY]
        soapaction_header = headers[SOAPACTION_KEY]

        assert soapaction_header == f'"{service_type}#{name}"'

    def test_call_request_is_tried_up_to_max_on_communication_error(self):
        action = self.get_mock_action()
        requests.post = mock.Mock(
            side_effect=requests.exceptions.RequestException)
        et.fromstring = mock.MagicMock()

        try:
            action()
        except svc.ActionException:
            pass

        assert requests.post.call_count == svc.MAX_RETRIES

    def test_call_throws_when_final_retry_fails(self):
        action = self.get_mock_action()
        requests.post = mock.Mock(
            side_effect=requests.exceptions.RequestException)
        et.fromstring = mock.MagicMock()

        with pytest.raises(svc.ActionException):
            action()

    def test_call_returns_correct_dictionary_with_response_contents(self):
        action = self.get_mock_action()
        requests.post = mock.Mock()

        envelope = et.Element("soapEnvelope")
        body = et.SubElement(envelope, "soapBody")
        response = et.SubElement(body, "soapResponse")

        response_content = {
            "key1": "value1",
            "key2": "value2",
            "key3": "value3",
        }

        for key, value in response_content.items():
            element = et.SubElement(response, key)
            element.text = value

        et.fromstring = mock.MagicMock(return_value=envelope)

        actual_responses = action()

        assert actual_responses == response_content
