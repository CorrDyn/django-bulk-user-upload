import re
from collections import namedtuple
from typing import List

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.mail import send_mass_mail
from django.db.models import Q

import pandas
from django.template.loader import render_to_string
from django.utils.functional import partition

User = get_user_model()

email_regex = re.compile(r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)")
username_regex = re.compile(r"^([a-zA-Z_0-9]{3,})$")


def get_groups_map():
    return {g["name"]: g["id"] for g in Group.objects.values('id', 'name')}


def get_perms_map():
    return {
        f"{v['content_type__app_label']}.{v['codename']}": v["id"] for v in
        Permission.objects.values('id', 'content_type__app_label', 'codename')
    }


class FieldValidator(dict):
    # field_name = (validator, custom_error_message)
    email = (lambda x: not x or not email_regex.match(x), None)
    username = (
        lambda x: not x or not username_regex.match(x),
        lambda username, *args: f"username must consist of 3 or more alphanumeric characters or underscores"
    )

    _groups = None
    _permissions = None

    @property
    def groups(self):
        if not self._groups:
            self._groups = get_groups_map()

        def validate_groups(group_list_string):
            invalid = []

            for group in group_list_string.split(','):
                group = group.strip()
                if group and group not in self._groups:
                    invalid.append(group)
            return invalid

        def invalid_info(group_list_string, invalid):
            message = f"{','.join(invalid)} are not valid group names."
            return message

        return validate_groups, invalid_info

    @property
    def permissions(self):
        if not self._permissions:
            self._permissions = get_perms_map()

        def validate_permissions(permissions_list_string):
            invalid = []

            for perm in permissions_list_string.split(','):
                perm = perm.strip()
                if perm and perm not in self._permissions:
                    invalid.append(perm)
            return invalid

        def invalid_info(permissions_list_string, invalid):
            message = f"{','.join(invalid)} are not valid permission names; expecting format app_label.codename, e.g. {next(iter(self._permissions))}"
            return message

        return validate_permissions, invalid_info

    def __init__(self, username_field=None, email_field=None, **kwargs):
        super().__init__()
        username_field = username_field if username_field else "username"
        email_field = email_field if email_field else "email"
        if kwargs.get(email_field, True):
            self[email_field] = kwargs.get(email_field, self.email)
        if kwargs.get(username_field, True):
            self[username_field] = kwargs.get(username_field, self.username)
        if kwargs.get("groups", True):
            self["groups"] = kwargs.get("groups", self.groups)
        if kwargs.get("permissions", True):
            self["permissions"] = kwargs.get("permissions", self.permissions)
        for key, value in kwargs.items():
            if not value:
                self.pop(key, None)
            else:
                self[key] = value


def append_or_create(dict_obj, key, value):
    if key in dict_obj:
        return dict_obj[key].append(value)
    dict_obj[key] = [value]


class UsersPreProcessor:

    @staticmethod
    def __call__(users: pandas.DataFrame):
        users["email"] = users["email"].apply(lambda x: x.lower())
        return users


validation_result_tuple = namedtuple("validation_result", ["errors", "warnings"])


class BaseUsersValidator:
    """
        Validates a user dataframe. Any method with a name that starts as check_frame_ will be used to validate the
        entire dataframe and any method with a name check_row_ will be used to validate each row.
        """
    issues = None
    field_validator_cls = FieldValidator
    field_validator_overrides = {}
    dataframe_validators_prefix = "check_frame_"
    row_validators_prefix = "check_row_"
    username_field = "username"
    email_field = "email"

    def __init__(self, username_field=None, email_field=None, field_validator_cls=None, field_validator_overrides=None):
        self.field_validator_overrides = field_validator_overrides if field_validator_overrides \
            else self.field_validator_overrides
        self.field_validator = field_validator_cls(**self.field_validator_overrides) if field_validator_cls \
            else self.field_validator_cls(**self.field_validator_overrides)
        self.username_field = username_field if username_field else self.username_field
        self.email_field = email_field if email_field else self.email_field

    def __call__(self, users: pandas.DataFrame) -> validation_result_tuple:
        self.issues = {
            "errors": {},
            "warnings": {},
        }
        users.apply(self.validate_row, axis=1)
        for method in self.get_row_validators():
            users.apply(method, axis=1)
        for method in self.get_dataframe_validators():
            method(users)

        return validation_result_tuple(self.issues["errors"], self.issues["warnings"])

    def get_dataframe_validators(self):
        methods = []
        for method_name in dir(self):
            maybe_method = getattr(self, method_name)
            if callable(maybe_method) and method_name.startswith(self.dataframe_validators_prefix):
                methods.append(maybe_method)
        return methods

    def get_row_validators(self):
        methods = []
        for method_name in dir(self):
            maybe_method = getattr(self, method_name)
            if callable(maybe_method) and method_name.startswith(self.row_validators_prefix):
                methods.append(maybe_method)
        return methods

    def validate_row(self, row):
        for key, (is_invalid, message_builder) in self.field_validator.items():
            value = row.get(key, None)
            invalid = is_invalid(value)
            if invalid:
                message = f"{key}='{value}' is invalid." if not message_builder else message_builder(value, invalid)
                append_or_create(self.issues["errors"], row.name, message)


class UsersValidator(BaseUsersValidator):

    def check_frame_duplicates(self, df):
        def record_duplicates(dup_row, column):
            append_or_create(
                self.issues["errors"],
                dup_row.name,
                f"row contains duplicate {column}='{dup_row[column]}'"
            )

        df[df.duplicated(self.email_field, keep=False)].apply(lambda row: record_duplicates(row, self.email_field), axis=1)
        df[df.duplicated(self.username_field, keep=False)].apply(lambda row: record_duplicates(row, self.username_field), axis=1)

    def check_frame_username_collision(self, df):
        """We want to error on any record where we already have the username but not the given email"""

        def record_collision(row):
            append_or_create(
                self.issues["errors"],
                row.name,
                f"row contains username='{row[self.username_field]}', but that user already exists with another email address",
            )

        q = Q(id=-1)
        for user in df.to_dict("records"):
            q |= Q(**{f"{self.username_field}": user[self.username_field]}) \
                 & ~Q(**{f"{self.email_field}__iexact": user[self.email_field]})
        existing_user_mapping = {
            getattr(user, self.username_field): getattr(user, self.email_field) for user in User.objects.filter(q)
        }
        df[df[self.username_field].apply(lambda username: username in existing_user_mapping)].apply(record_collision, axis=1)


creation_result_tuple = namedtuple("creation_result", ["created", "skipped"])


class BaseUsersCreator:
    username_field = "username"
    users_preprocessor_cls = UsersPreProcessor

    def preprocess_users(self, users):
        return self.users_preprocessor_cls()(users)

    def __init__(self, username_field=None, users_preprocessor_cls=None):
        self.username_field = username_field if username_field else self.username_field
        self.users_preprocessor_cls = users_preprocessor_cls if users_preprocessor_cls else self.users_preprocessor_cls

    def __call__(self, users: pandas.DataFrame) -> creation_result_tuple:
        username_field = self.username_field
        users = self.preprocess_users(users)
        user_records = users.to_dict("records")

        groups_map = get_groups_map()
        perms_map = get_perms_map()
        user_access_map = {}
        for user_record in user_records:
            perms = [perms_map[p.strip()] for p in user_record.pop("permissions", "").split(",") if p]
            groups = [groups_map[g.strip()] for g in user_record.pop("groups", "").split(",") if g]
            user_access_map[user_record[username_field]] = dict(perms=perms, groups=groups)

        existing_users = {
            getattr(u, username_field): u for u in User.objects.filter(**{f"{username_field}__in": [*user_access_map]})
        }

        to_create, skipped = partition(lambda user: user[username_field] in existing_users, user_records)

        results = User.objects.bulk_create([
            User(**dict(**user, password="no-login")) for user in to_create
        ], ignore_conflicts=False)

        results_with_ids = User.objects.filter(**{f"{username_field}__in": [getattr(u, username_field) for u in results]})
        for user in results_with_ids:
            if user_access_map[getattr(user, username_field)]["perms"]:
                user.user_permissions.set(user_access_map[getattr(user, username_field)]["perms"])
            if user_access_map[getattr(user, username_field)]["groups"]:
                user.groups.set(user_access_map[getattr(user, username_field)]["groups"])

        return creation_result_tuple(results_with_ids, [existing_users[u[username_field]] for u in skipped])


def get_email_recipient_name(user: User):
    return f"{user.first_name} {user.last_name}" if user.first_name and user.last_name else user.email


class EmailSender:
    username_field = "username"
    email_field = "email"

    def __init__(self, username_field=None, email_field=None):
        self.username_field = username_field if username_field else self.username_field
        self.email_field = email_field if email_field else self.email_field

    def __call__(
        self,
        template_name: str,
        login_url: str,
        from_email: str,
        subject: str,
        get_recipient_name,
        new_users: List[User]
    ):
        send_mass_mail(
            [
                (
                    subject,
                    render_to_string(
                        template_name=template_name,
                        context=dict(
                            login_url=login_url,
                            username=getattr(user, self.username_field),
                            recipient_name=get_recipient_name(user)
                        )
                    ),
                    from_email,
                    [getattr(user, self.email_field)],
                )
                for user in new_users
            ]
        )
