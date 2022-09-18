"""Dyson Pure Cool Link library."""

# pylint: disable=too-many-public-methods,too-many-instance-attributes

import logging
import requests
from requests.auth import HTTPBasicAuth
from .utils import is_360_eye_device, is_heating_device

from .dyson_360_eye import Dyson360Eye
from .dyson_pure_cool_link import DysonPureCoolLink
from .dyson_pure_hotcool_link import DysonPureHotCoolLink
from .exceptions import DysonNotLoggedException

_LOGGER = logging.getLogger(__name__)

DYSON_API_URL = "appapi.cp.dyson.com"


class DysonAccount:
    """Dyson account."""

    def __init__(self, email, password, country):
        """Create a new Dyson account.

        :param email: User email
        :param password: User password
        :param country: 2 characters country code
        """
        self._email = email
        self._password = password
        self._country = country
        self._logged = False
        self._headers = {
            "Content-Type": "application/json",
            "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 12; sdk_gphone64_x86_64 Build/S2B2.211203.006)"
        }

    def use_authentication_token(self, authentication_token):
        # Build Authorization header using token in response
        self._headers["Authorization"] = "Bearer " + authentication_token
        self._logged = True

    def login(self):
        """Login to dyson web services."""
        # Get login type
        # Build request body with email address
        request_body = {
            "email": self._email
        }
        _LOGGER.info("Step 1 of login flow: check account state")
        # Example URL /v3/userregistration/email/userstatus?country=US
        authentication_type_response = requests.post(
            "https://{0}/v3/userregistration/email/userstatus?country={1}"
                .format(
                DYSON_API_URL, self._country), json=request_body, headers=self._headers)
        if authentication_type_response.status_code == requests.codes.ok:
            _LOGGER.debug("Got good response for authentication_type request")
            # Expect: {"accountStatus":"ACTIVE","authenticationMethod":"EMAIL_PWD_2FA"}
            json_response = authentication_type_response.json()
            _LOGGER.debug(json_response)
            if json_response['accountStatus'] != 'ACTIVE':
                _LOGGER.warning("Account not ACTIVE, not sure how to proceed, but " + json_response['accountStatus'])
                self._logged = False
                return self._logged
            if json_response['authenticationMethod'] != 'EMAIL_PWD_2FA':
                _LOGGER.warning("Account is using an unexpected authentication type, don't know how to proceed")
                self._logged = False
                return self._logged
            authentication_type = json_response['authenticationMethod']
        else:
            _LOGGER.warning("Got failed response from API with response code: " + str(authentication_type_response.status_code))
            self._logged = False
            return self._logged

        # Start authentication process
        _LOGGER.info("Step 2 of login flow: get challenge ID")
        # Example URL /v3/userregistration/email/auth?country=US&culture=en-US
        challenge_initiate_response = requests.post(
            # Yes I'm assuming English, sorry
            "https://{0}/v3/userregistration/email/auth?country={1}&culture=en-{1}"
                .format(
                DYSON_API_URL, self._country), json=request_body, headers=self._headers)
        if challenge_initiate_response.status_code == requests.codes.ok:
            _LOGGER.debug("Got good response for challenge initiation")
            # Expect: {"challengeId":"e6ff5f3f-204c-4c76-8546-7a536761ebdd"}
            json_response = challenge_initiate_response.json()
            _LOGGER.debug(json_response)
            if 'challengeId' not in json_response:
                _LOGGER.warning("Did not get a challengeId in response; dunno what to do")
                self._logged = False
                return self._logged
            challenge_id = json_response['challengeId']
            _LOGGER.debug("Got challengeId: " + challenge_id)
        else:
            _LOGGER.warning("Got failed response from API with response code: " + str(challenge_initiate_response.status_code))
            self._logged = False
            return self._logged

        # Complete authentication process
        _LOGGER.info("Step 3 of login flow: interactive MFA")
        otp = input('Input the code sent to you by Dyson at ' + self._email + ':       ')

        request_body = {
            "email": self._email,
            "password": self._password,
            "challengeId": challenge_id,
            "otpCode": otp
        }
        # Example URL /v3/userregistration/email/verify?country=US
        login_response = requests.post(
            "https://{0}/v3/userregistration/email/verify?country={1}".format(
                DYSON_API_URL, self._country), json=request_body, headers=self._headers)
        # pylint: disable=no-member
        if login.status_code == requests.codes.ok:
            json_response = login.json()
            _LOGGER.debug(json_response)
            self.use_authentication_token(json_response["token"])
        else:
            self._logged = False
        return self._logged

    def devices(self):
        """Return all devices linked to the account."""
        if self._logged:
            device_response = requests.get(
                "https://{0}/v1/provisioningservice/manifest".format(
                    DYSON_API_URL), headers=self._headers)
            devices = []
            for device in device_response.json():
                if is_360_eye_device(device):
                    dyson_device = Dyson360Eye(device)
                elif is_heating_device(device):
                    dyson_device = DysonPureHotCoolLink(device)
                else:
                    dyson_device = DysonPureCoolLink(device)
                devices.append(dyson_device)

            return devices
        else:
            _LOGGER.warning("Not logged to Dyson Web Services.")
            raise DysonNotLoggedException()

    @property
    def logged(self):
        """Return True if user is logged, else False."""
        return self._logged
