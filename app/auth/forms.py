from flask_wtf import FlaskForm
from wtforms import ValidationError
from wtforms import BooleanField, PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional

from app.models import User, UserRole


class RegistrationForm(FlaskForm):
    """Collects the information required to create a user account."""

    full_name = StringField("Full name", validators=[DataRequired(), Length(min=2, max=120)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    role = SelectField(
        "Account type",
        choices=[
            (UserRole.STUDENT.value, "Student"),
            (UserRole.PARENT.value, "Parent"),
        ],
        validators=[DataRequired()],
    )

    main_course_code = StringField(
        "Main course code",
        validators=[Optional(), Length(max=24)],
        description="Optional: enter a main course code to unlock all its sub-courses once approved.",
    )

    password = PasswordField("Password", validators=[DataRequired(), Length(min=8, max=128)])
    confirm_password = PasswordField(
        "Confirm password", validators=[DataRequired(), EqualTo("password", message="Passwords must match")]
    )
    submit = SubmitField("Create account")

    def validate_email(self, field):
        existing_user = User.query.filter_by(email=field.data.strip().lower()).first()
        if existing_user:
            raise ValidationError("An account already exists for this email address.")


class LoginForm(FlaskForm):
    """Login form for existing users."""

    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember = BooleanField("Remember me")
    submit = SubmitField("Sign in")
