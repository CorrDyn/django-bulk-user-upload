"""
Settings for bulk-user-upload are all namespaced in the BULK_USER_UPLOAD setting.
For example your project's `settings.py` file might look like this:
BULK_USER_UPLOAD = {
    'ACCOUNT_CREATION_EMAIL_SUBJECT': 'Account Created',
    'LOGIN_URL': '/login/',
}
This module provides the `settings` object, that is used to access
bulk-user-upload settings, checking for user settings first, then falling
back to the defaults.

Modified from django-rest-framework
https://github.com/encode/django-rest-framework/blob/master/rest_framework/settings.py. See License below.

Copyright © 2011-present, Encode OSS Ltd. All rights reserved.
Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:
    Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.
    Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
    Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.
THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""
from django.conf import settings
from django.test.signals import setting_changed
from django.utils.module_loading import import_string

DEFAULTS = {
    'ACCOUNT_CREATION_EMAIL_SENDER_ADDRESS': None,
    'ACCOUNT_CREATION_EMAIL_SUBJECT': 'Account Created',
    'USERNAME_FIELD': 'username',
    'EMAIL_FIELD': 'email',
    'LOGIN_URL': '/',
    'USER_UPLOAD_FORM': 'bulk_user_upload.forms.BulkUserUploadForm',
    'USERS_CREATOR': 'bulk_user_upload.utils.BaseUsersCreator',
    'USERS_VALIDATOR': 'bulk_user_upload.utils.UsersValidator',
    'USER_FIELD_VALIDATORS': {},
    'EMAIL_SENDER': 'bulk_user_upload.utils.EmailSender',
    'GET_EMAIL_RECIPIENT_NAME': 'bulk_user_upload.utils.get_email_recipient_name',
}


# List of settings that may be in string import notation.
IMPORT_STRINGS = [
    'USER_UPLOAD_FORM',
    'USERS_CREATOR',
    'USERS_VALIDATOR',
    'USER_FIELD_VALIDATORS',
    'EMAIL_SENDER',
    'GET_EMAIL_RECIPIENT_NAME',
]


# List of settings that have been removed
REMOVED_SETTINGS = []


def perform_import(val, setting_name):
    """
    If the given setting is a string import notation,
    then perform the necessary import or imports.
    """
    if val is None:
        return None
    elif isinstance(val, str):
        return import_from_string(val, setting_name)
    elif isinstance(val, (list, tuple)):
        return [import_from_string(item, setting_name) for item in val]
    return val


def import_from_string(val, setting_name):
    """
    Attempt to import a class from a string representation.
    """
    try:
        return import_string(val)
    except ImportError as e:
        msg = "Could not import '%s' for API setting '%s'. %s: %s." % (val, setting_name, e.__class__.__name__, e)
        raise ImportError(msg)


class Settings:
    """
    A settings object that allows bulk-user-upload settings to be accessed as
    properties. For example:
        bulk_user_upload.settings import bulk_user_upload_settings
        print(bulk_user_upload_settings.USER_UPLOAD_FORM)
    Any setting with string import paths will be automatically resolved
    and return the class, rather than the string literal.
    Note:
    This is an internal class that is only compatible with settings namespaced
    under the BULK_USER_UPLOAD name. It is not intended to be used by 3rd-party
    apps, and test helpers like `override_settings` may not work as expected.
    """
    def __init__(self, user_settings=None, defaults=None, import_strings=None):
        if user_settings:
            self._user_settings = user_settings
        self.defaults = defaults or DEFAULTS
        self.import_strings = import_strings or IMPORT_STRINGS
        self._cached_attrs = set()

    @property
    def user_settings(self):
        if not hasattr(self, '_user_settings'):
            self._user_settings = getattr(settings, 'BULK_USER_UPLOAD', {})
        return self._user_settings

    def __getattr__(self, attr):
        if attr not in self.defaults:
            raise AttributeError("Invalid setting: '%s'" % attr)

        try:
            # Check if present in user settings
            val = self.user_settings[attr]
        except KeyError:
            # Fall back to defaults
            val = self.defaults[attr]

        # Coerce import strings into classes
        if attr in self.import_strings:
            val = perform_import(val, attr)

        # Cache the result
        self._cached_attrs.add(attr)
        setattr(self, attr, val)
        return val

    def reload(self):
        for attr in self._cached_attrs:
            delattr(self, attr)
        self._cached_attrs.clear()
        if hasattr(self, '_user_settings'):
            delattr(self, '_user_settings')


bulk_user_upload_settings = Settings(None, DEFAULTS, IMPORT_STRINGS)


def reload_bulk_user_upload_settings(*args, **kwargs):
    setting = kwargs['setting']
    if setting == 'BULK_USER_UPLOAD':
        bulk_user_upload_settings.reload()


setting_changed.connect(reload_bulk_user_upload_settings)
