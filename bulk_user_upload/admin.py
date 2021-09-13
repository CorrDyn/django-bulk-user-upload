import pandas
import logging
from django.contrib import admin, messages
from django.contrib.admin.options import IS_POPUP_VAR
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.decorators import permission_required
from django.db import transaction
from django.urls import path, reverse
from django.utils.decorators import method_decorator
from django.views import generic

from bulk_user_upload.settings import bulk_user_upload_settings

from bulk_user_upload.utils import FieldValidator

logger = logging.getLogger(__file__)


class BulkUploadUserAdmin(UserAdmin):
    change_list_template = "admin/users_change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path(
                "admin/bulk_upload_users/",
                self.admin_site.admin_view(BulkUploadUsers.as_view()),
                name="bulk-upload-users",
            ),
        ]
        return my_urls + urls


class BulkUploadUsers(generic.FormView):
    form_class = bulk_user_upload_settings.USER_UPLOAD_FORM
    template_name = "admin/bulk_upload_users.html"
    email_template_name = "email/account_creation_email.html"
    email_sender_address = bulk_user_upload_settings.ACCOUNT_CREATION_EMAIL_SENDER_ADDRESS
    email_subject = bulk_user_upload_settings.ACCOUNT_CREATION_EMAIL_SUBJECT
    login_url = bulk_user_upload_settings.LOGIN_URL
    field_validator_cls = FieldValidator
    users_preprocessor_cls = bulk_user_upload_settings.USERS_PREPROCESSOR
    users_creator_cls = bulk_user_upload_settings.USERS_CREATOR
    email_sender_cls = bulk_user_upload_settings.EMAIL_SENDER
    username_field = bulk_user_upload_settings.USERNAME_FIELD
    email_field = bulk_user_upload_settings.EMAIL_FIELD

    @property
    def user_field_validators(self):
        return self.field_validator_cls(**bulk_user_upload_settings.USER_FIELD_VALIDATORS)

    @property
    def users_creator(self):
        return self.users_creator_cls(username_field=self.username_field, users_preprocessor_cls=self.users_preprocessor_cls)

    @property
    def email_sender(self):
        return self.email_sender_cls(username_field=self.username_field, email_field=self.email_field)

    @staticmethod
    def get_email_recipient_name(user):
        return bulk_user_upload_settings.GET_EMAIL_RECIPIENT_NAME(user)

    @method_decorator(
        permission_required(["users.add_user", "users.change_user"], raise_exception=True),
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @method_decorator(
        permission_required(["users.add_user", "users.change_user"], raise_exception=True),
    )
    def post(self, request, *args, **kwargs):
        """
        Handle POST requests: instantiate a form instance with the passed
        POST variables and then check if it's valid.
        """
        form = self.get_form()
        if form.is_valid("_validate" in request.POST):
            if form.validate_only:
                if "warnings" not in form.uploaded_data:
                    messages.add_message(request, messages.SUCCESS, "Uploaded CSV passed all checks.")
                return self.form_invalid(form)
            return self.form_valid(form)
        else:
            return self.form_invalid(form)

    def form_valid(self, form):
        try:
            with transaction.atomic():
                created, skipped = self.users_creator(form.uploaded_data)
                messages.add_message(self.request, messages.SUCCESS, f"{len(created)} New users created.")
                if form.cleaned_data["send_emails"]:
                    self.email_sender(
                        self.email_template_name,
                        self.request.build_absolute_uri('/'),
                        self.email_sender_address,
                        self.email_subject,
                        self.get_email_recipient_name,
                        created
                    )
                return self.form_invalid(form, created)
        except (Exception, BaseException) as e:  # noqa
            message = f"Something went wrong while creating users; some emails may have been sent in error: {e}"
            logger.exception(message, exc_info=e)
            messages.add_message(self.request, messages.ERROR, message)
        return self.form_invalid(form)

    def form_invalid(self, form, created=None):
        context_data = self.get_context_data(form=form)
        df = form.uploaded_data
        if "warnings" in df or "errors" in form.uploaded_data:
            user_field_validators = self.user_field_validators
            if "warnings" in df:
                context_data["warnings"] = df[df["warnings"].apply(bool)][["row", "warnings", *user_field_validators]].to_html(
                    index=False
                )
            if "errors" in form.uploaded_data:
                context_data["errors"] = df[df["errors"].apply(bool)][["row", "errors", *user_field_validators]].to_html(index=False)
        if created:
            context_data["created"] = pandas.DataFrame(
                [dict(username=getattr(u, self.username_field), email=u.email) for u in created]
            ).to_html(index=False)
        return self.render_to_response(context_data)

    def get_success_url(self):
        return reverse("admin:bulk-upload-users")

    def get_context_data(self, **kwargs):
        if "form" not in kwargs:
            kwargs["form"] = self.get_form()
        context = super().get_context_data(**kwargs)
        fieldsets = [(None, {"fields": list(context["form"].base_fields)})]
        context.update(
            dict(
                is_popup=True,
                is_popup_var=IS_POPUP_VAR,
                has_file_field=True,
                form_url=reverse("admin:bulk-upload-users"),
                form=admin.helpers.AdminForm(context["form"], fieldsets, {}),
            )
        )
        return context
