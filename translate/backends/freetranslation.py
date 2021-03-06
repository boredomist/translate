# -*- coding: utf-8 -*-

# This file is part of translate.
#
# translate is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# translate is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# translate.  If not, see <http://www.gnu.org/licenses/>.


from translate.backend import IBackend
from translate.exceptions import TranslationException
from translate.utils import iso639_convert

import requests
import json
import urllib

import logging
log = logging.getLogger(__name__)


API_URL = 'https://api.beglobal.com/'
API_TIMEOUT = 5
API_ERRORS = {
    401: 'Unauthorized: bad API key',
    420: 'Request failed',
    422: 'Semantic error within request',
    500: 'Internal server error'
}

# API key is passed in a request header: "Authorization: BeGlobal apiKey=KEY"


class FreeTranslationBackend(IBackend):
    name = "FreeTranslation"
    description = "Web translation service from freetranslation.com"
    url = 'http://freetranslation.com'
    preference = 30
    language_pairs = []

    def activate(self, config):
        self.config = config

        if not self.config.get('active', False):
            return False

        if config.get('key') is None:
            log.error("Don't have an API key, can't proceed")
            return False

        self.key = config['key']
        self.timeout = self.config.get('timeout', API_TIMEOUT)

        self.auth_header = 'BeGlobal apiKey=%s' % self.key

        try:
            resp = self._api_get_request('languages', quality='Q1')

            if resp.status_code != 200:
                log.error("Request failed: %s", resp.text)
                return False

            jsobj = json.loads(resp.text)
        except (ValueError, requests.exceptions.RequestException):
            return False

        self.language_pairs = []

        for obj in jsobj['languageExpertise']['Q1']:
            from_lang = obj['languagePair']['from']['code'].lower()
            to_lang = obj['languagePair']['to']['code'].lower()

            from_lang = iso639_convert(from_lang)
            to_lang = iso639_convert(to_lang)

            self.language_pairs.append((from_lang, to_lang))

        # Just in case the API returns duplicates for whatever reason
        self.language_pairs = list(set(self.language_pairs))

        if len(self.language_pairs) == 0:
            log.error('Got zero translation pairs, aborting')
            return False

        return True

    def translate(self, text, from_lang, to_lang):

        # Switch to 3 char codes
        from_lang = iso639_convert(from_lang)
        to_lang = iso639_convert(to_lang)

        # Free translate requires text to be URI-encoded
        quoted = urllib.quote(text.encode('utf8'))

        params = {'from': from_lang, 'to': to_lang, 'text': quoted}

        try:
            resp = self._api_post_request('translate', **params)

            if resp.status_code != 200:
                error = API_ERRORS.get(resp.status_code, "Unknown error")
                raise TranslationException("Failed to translate: %s" % error)

            jsobj = json.loads(resp.text)
            text = jsobj['translation']
            return urllib.unquote(text)

        except (ValueError, requests.exceptions.RequestException) as exc:
            raise TranslationException('Translation request failed: %s' %
                                       str(exc))

    def deactivate(self):
        pass

    def _api_get_request(self, method, **kwargs):
        try:
            r = requests.get(API_URL + method, params=kwargs,
                             headers={'Authorization': self.auth_header,
                                      'Content-type': 'application/json'},
                             timeout=self.timeout)
            return r

        except requests.exceptions.RequestException as exc:
            log.error('API request {0} params={1} failed!'
                      .format(method, kwargs))
            log.error(repr(exc))

            raise exc

    def _api_post_request(self, method, **kwargs):
        try:
            r = requests.post(API_URL + method, data=json.dumps(kwargs),
                              headers={'Authorization': self.auth_header,
                                       'Content-type': 'application/json'},
                              timeout=self.timeout)
            return r

        except requests.exceptions.RequestException as exc:
            log.error('API request {0} params={1} failed!'
                      .format(method, kwargs))
            log.error(repr(exc))

            raise exc
