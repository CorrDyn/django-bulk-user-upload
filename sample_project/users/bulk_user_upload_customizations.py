from django.contrib.auth import get_user_model
from django.db.models import Q

from bulk_user_upload.utils import UsersValidator, append_or_create

User = get_user_model()


class CustomUsersValidator(UsersValidator):
    def check_frame_duplicates(self, df):
        def record_duplicates(dup_row, column):
            append_or_create(
                self.issues["errors"],
                dup_row.name,
                f"row contains duplicate {column}='{dup_row[column]}'"
            )

        df[df.duplicated(self.email_field, keep=False)].apply(
            lambda row: record_duplicates(row, self.email_field), axis=1
        )
        df[df.duplicated(self.username_field, keep=False)].apply(
            lambda row: record_duplicates(row, self.username_field), axis=1
        )
        df[df.duplicated("name", keep=False)].apply(
            lambda row: record_duplicates(row, "name"), axis=1
        )

    def check_frame_name_collision(self, df):
        """We want to error on any record where we already have the username but not the given name"""
        def record_collision(row):
            append_or_create(
                self.issues["errors"],
                row.name,
                f"row contains name='{row['name']}', but that user already exists with another username",
            )

        q = Q(id=-1)
        for user in df.to_dict("records"):
            q |= Q(name=user["name"]) & ~Q(username=user["username"])
        existing_user_mapping = {user.username: user.name for user in User.objects.filter(q)}
        df[df["username"].apply(lambda username: username in existing_user_mapping)].apply(record_collision, axis=1)

