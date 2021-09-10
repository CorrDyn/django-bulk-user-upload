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
    email = (lambda x: x and email_regex.match(x), None)
    username = (lambda x: x and username_regex.match(x), lambda username: f"username expected not to be blank.")

    _groups = None
    _permissions = None

    @property
    def groups(self):
        if not self._groups:
            self._groups = get_groups_map()

        invalid = []

        def validate_groups(group_list_string):
            for group in group_list_string.split(','):
                group = group.strip()
                if group and group not in self._groups:
                    invalid.append(group)
            return not invalid

        def invalid_info(group_list_string):
            return f"{','.join(invalid)} are not valid group names."

        return validate_groups, invalid_info

    @property
    def permissions(self):
        if not self._permissions:
            self._permissions = get_perms_map()

        invalid = []

        def validate_permissions(permissions_list_string):
            for perm in permissions_list_string.split(','):
                perm = perm.strip()
                if perm and perm not in self._permissions:
                    invalid.append(perm)
            return not invalid

        def invalid_info(permissions_list_string):
            return f"{','.join(invalid)} are not valid permission names; expecting format app_label.codename, e.g. {next(iter(self._permissions))}"

        return validate_permissions, invalid_info

    def __init__(self, **kwargs):
        super().__init__()
        self["email"] = self.email
        self["username"] = self.username
        self["groups"] = self.groups
        self["permissions"] = self.permissions
        for key, value in kwargs.items():
            if not value:
                self.pop(key, None)
            else:
                self[key] = value


def append_or_create(dict_obj, key, value):
    if key in dict_obj:
        return dict_obj[key].append(value)
    dict_obj[key] = [value]


def prepare_users_from_dataframe(users: pandas.DataFrame):
    users["email"] = users["email"].apply(lambda x: x.lower())
    return users


validation_result_tuple = namedtuple("validation_result", ["errors", "warnings"])


def validate_users_from_dataframe(users: pandas.DataFrame, validator_class=FieldValidator) -> validation_result_tuple:
    users = prepare_users_from_dataframe(users)
    issues = {
        "errors": {},
        "warnings": {},
    }
    validator = validator_class()

    def validate_row(row):
        for key, (is_valid, message_builder) in validator.items():
            value = row.get(key, None)
            if not is_valid(value):
                message = f"{key}='{value}' is invalid." if not message_builder else message_builder(value)
                append_or_create(issues["errors"], row.name, message)

    def check_duplicates(df):
        def record_duplicates(dup_row, column):
            append_or_create(issues["errors"], dup_row.name, f"row contains duplicate {column}='{dup_row[column]}'")

        df[df.duplicated("email", keep=False)].apply(lambda row: record_duplicates(row, "email"), axis=1)
        df[df.duplicated("username", keep=False)].apply(lambda row: record_duplicates(row, "username"), axis=1)

    def check_username_collision(df):
        """We want to error on any record where we already have the username but not the given email"""

        def record_collision(row):
            append_or_create(
                issues["errors"],
                row.name,
                f"row contains username='{row['username']}', but that user already exists with another email address",
            )

        q = Q(id=-1)
        for user in df.to_dict("records"):
            q |= Q(name=user["username"]) & ~Q(email__iexact=user["email"])
        existing_user_mapping = {user.username: user.email for user in User.objects.filter(q)}
        df[df["username"].apply(lambda username: username in existing_user_mapping)].apply(record_collision, axis=1)

    def check_email_collision(df):
        """We want to warn on any record where we already have the email matched with a different username"""

        def record_collision(row):
            append_or_create(
                issues["warnings"],
                row.name,
                f"row contains email='{row['email']}', but that user already exists with another username",
            )

        q = Q(id=-1)
        for user in df.to_dict("records"):
            q |= ~Q(name=user["username"]) & Q(email__iexact=user["email"])
        existing_user_mapping = {user.email: user.username for user in User.objects.filter(q)}
        df[df["email"].apply(lambda username: username in existing_user_mapping)].apply(record_collision, axis=1)

    users.apply(validate_row, axis=1)
    check_duplicates(users)
    check_username_collision(users)
    check_email_collision(users)

    return validation_result_tuple(issues["errors"], issues["warnings"])


creation_result_tuple = namedtuple("creation_result", ["created", "skipped"])


def create_users_from_dataframe(users: pandas.DataFrame) -> creation_result_tuple:
    users = prepare_users_from_dataframe(users)
    user_records = users.to_dict("records")

    groups_map = get_groups_map()
    perms_map = get_perms_map()
    user_access_map = {}
    for user_record in user_records:
        perms = [perms_map[p.strip()] for p in user_record.pop("permissions", "").split(",") if p]
        groups = [groups_map[g.strip()] for g in user_record.pop("groups", "").split(",") if g]
        user_access_map[user_record["username"]] = dict(perms=perms, groups=groups)

    existing_users = {getattr(u, "username"): u for u in User.objects.filter(username__in=[*user_access_map])}

    to_create, skipped = partition(lambda user: user["username"] in existing_users, user_records)

    results = User.objects.bulk_create([
        User(**dict(**user, password="no-login")) for user in to_create
    ], ignore_conflicts=False)

    results_with_ids = User.objects.filter(**{"username__in": [getattr(u, "username") for u in results]})
    for user in results_with_ids:
        if user_access_map[getattr(user, "username")]["perms"]:
            user.user_permissions.set(user_access_map[getattr(user, "username")]["perms"])
        if user_access_map[getattr(user, "username")]["groups"]:
            user.groups.set(user_access_map[getattr(user, "username")]["groups"])

    return creation_result_tuple(results_with_ids, [existing_users[u["username"]] for u in skipped])


def get_email_recipient_name(user: User):
    return f"{user.first_name} {user.last_name}" if user.first_name and user.last_name else user.email


def send_emails_for_created_users(
        template_name: str, login_url: str, from_email: str, subject: str, get_recipient_name, new_users: List[User]
):
    send_mass_mail(
        [
            (
                subject,
                render_to_string(
                    template_name=template_name,
                    context=dict(
                        login_url=login_url,
                        username=user.username,
                        recipient_name=get_recipient_name(user)
                    )
                ),
                from_email,
                [user.email],
            )
            for user in new_users
        ]
    )
