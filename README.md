Installable Django admin interface for bulk user creation from uploaded CSV file.

# Installation

First install using pip
```bash
pip install django-bulk-user-upload
```

Then add to your `INSTALLED_PACKAGES`
```python
INSTALLED_PACKAGES = [
    . . .,
    'bulk_user_upload',
]
```

Then override the default User admin:
```python
from django.contrib.admin import register
from django.contrib.auth import get_user_model

from bulk_user_upload.admin import BulkUploadUserAdmin

User = get_user_model()

@register(User)
class CustomUserAdmin(BulkUploadUserAdmin):
    pass
```

# Setup and Customization
By default, the upload only processes `username`, `email`, `permissions`, and `groups`, e.g., you could use a CSV
with the following information:

|username|email|permissions|groups|
|---|---|---|----|
|user|user@example.com|"auth.add_user,auth.change_user"|"Example Users,Test Users"|

But if you have a custom user model or need to capture more fields, you can modify the defaults by setting `BULK_USER_UPLOAD` in
`settings.py`. Below are the defaults:
```python
BULK_USER_UPLOAD = {
    'USERNAME_FIELD': 'username',  # user model username field
    'EMAIL_FIELD': 'email',  # user model email field
    'LOGIN_URL': '/',  # used in account creation notification email template
    'USER_UPLOAD_FORM': 'bulk_user_upload.forms.BulkUserUploadForm',  # django admin upload form
    'USERS_PREPROCESSOR': 'bulk_user_upload.utils.UsersPreProcessor',  # cleanup/pre-process the uploaded CSV
    'USERS_CREATOR': 'bulk_user_upload.utils.BaseUsersCreator',  # creates users from the uploaded CSV
    'USERS_VALIDATOR': 'bulk_user_upload.utils.UsersValidator',  # validates users from the uploaded CSV
    'USER_FIELD_VALIDATORS': {},  # add or override field-level validators
    'SEND_EMAILS_BY_DEFAULT': True,  # whether "send emails" is checked by default in the upload form
    'ACCOUNT_CREATION_EMAIL_SENDER_ADDRESS': None,  # email address used to notify user of account creation
    'ACCOUNT_CREATION_EMAIL_SUBJECT': 'Account Created',
    'EMAIL_SENDER': 'bulk_user_upload.utils.EmailSender',  # sends emails to created accounts
    # compute the name of the recipient, used in the account creation notification email template
    'GET_EMAIL_RECIPIENT_NAME': 'bulk_user_upload.utils.get_email_recipient_name',
}
```

For example, if you wanted to indicate whether your uploaded users are staff, you could modify these settings like so:
```python
def intish(value):
    try:
        int(value)
        return True
    except:
        return False

BULK_USER_UPLOAD = dict(
    USER_FIELD_VALIDATORS=dict(
        is_staff=(
            lambda is_staff: not intish(is_staff) or int(is_staff) not in [True, False],
            lambda is_staff, *args: "is_staff must be 0 or 1.",
        )
    )
)
```

The sample project has an example of this and other customizations.

# Demo
https://user-images.githubusercontent.com/12461302/133109664-3f2a223d-cc8c-4085-965a-c04e48065d72.mov