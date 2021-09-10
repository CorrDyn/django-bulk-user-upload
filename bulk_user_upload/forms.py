import tempfile
from pathlib import Path

from django import forms
from django.core.exceptions import ValidationError

from bulk_user_upload.settings import bulk_user_upload_settings

import pandas

from bulk_user_upload.utils import FieldValidator


class BulkUserUploadForm(forms.Form):
    uploaded_data = pandas.DataFrame()
    csv_file = forms.FileField(label="CSV File")
    send_emails = forms.BooleanField(initial=True, required=False)

    @property
    def user_field_validators(self):
        return FieldValidator(**bulk_user_upload_settings.USER_FIELD_VALIDATORS)

    def is_valid(self, validate_only=False):
        self.validate_only = validate_only
        return super().is_valid()

    @staticmethod
    def _prepare_errors_and_warnings(users: pandas.DataFrame, errors, warnings):
        users["row"] = users.index + 2
        user_records = users.to_dict("records")
        for idx, error_list in errors.items():
            user_records[idx]["errors"] = "; ".join(error_list)
        for idx, warning_list in warnings.items():
            user_records[idx]["warnings"] = "; ".join(warning_list)
        return pandas.DataFrame(user_records).fillna("")

    def clean(self):
        self.uploaded_data = pandas.DataFrame()
        csv_file = self.cleaned_data.get("csv_file", None)
        if not csv_file:
            return self.cleaned_data

        with tempfile.TemporaryDirectory() as temp_dir:
            csv_file_path = Path(temp_dir) / "uploaded.csv"
            with open(csv_file_path, "wb+") as wb:
                for chunk in csv_file.chunks():
                    wb.write(chunk)
            users = pandas.read_csv(csv_file_path, keep_default_na=False)
            if len(users) > 100:
                raise ValidationError(f"Uploads are limited to 100 at a time.")
            missing = [required for required in self.user_field_validators if required not in users.columns]
            if any(missing):
                raise ValidationError(f"Expected headers {missing}; got {list(users.columns)}")
            users = users[self.user_field_validators]
            errors, warnings = bulk_user_upload_settings.VALIDATE_USERS(users)
            if self.validate_only or errors:
                self.uploaded_data = self._prepare_errors_and_warnings(users, errors, warnings)
                if errors:
                    self.add_error(None, "Some rows contained validation errors.")
                return self.cleaned_data
            self.uploaded_data = users

        return self.cleaned_data
