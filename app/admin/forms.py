from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    DecimalField,
    IntegerField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, NumberRange, Optional

from app.models import AdminAccessLevel, LessonContentType, QuestionType, UserRole


class MainCourseForm(FlaskForm):
    """Admin form for creating top-level main courses."""

    title = StringField("Title", validators=[DataRequired(), Length(min=3, max=200)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=5000)])
    access_code = StringField(
        "Access code",
        validators=[Optional(), Length(min=4, max=24)],
        description="Leave blank to auto-generate a unique code.",
    )
    submit = SubmitField("Create main course")


class SubCourseForm(FlaskForm):
    """Admin form for adding sub-courses inside a selected main course."""

    title = StringField("Title", validators=[DataRequired(), Length(min=3, max=200)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=5000)])
    sort_order = IntegerField("Sort order", validators=[DataRequired(), NumberRange(min=1)], default=1)
    submit = SubmitField("Add sub-course")


class ModuleForm(FlaskForm):
    """Admin form for creating modules in a sub-course."""

    title = StringField("Title", validators=[DataRequired(), Length(min=3, max=200)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=5000)])
    sort_order = IntegerField("Sort order", validators=[DataRequired(), NumberRange(min=1)], default=1)
    submit = SubmitField("Add module")


class LessonForm(FlaskForm):
    """Admin form for creating lessons under a module."""

    title = StringField("Title", validators=[DataRequired(), Length(min=3, max=200)])
    content_type = SelectField(
        "Content type",
        choices=[
            (LessonContentType.TEXT.value, "Text"),
            (LessonContentType.VIDEO.value, "Video"),
            (LessonContentType.PDF.value, "PDF"),
        ],
        validators=[DataRequired()],
    )
    content_url = StringField("Content URL", validators=[Optional(), Length(max=500)])
    text_content = TextAreaField("Text content", validators=[Optional(), Length(max=25000)])
    sort_order = IntegerField("Sort order", validators=[DataRequired(), NumberRange(min=1)], default=1)
    is_published = BooleanField("Published", default=True)
    submit = SubmitField("Add lesson")


class QuizForm(FlaskForm):
    """Admin form for creating quizzes under a module."""

    title = StringField("Title", validators=[DataRequired(), Length(min=3, max=200)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=5000)])
    time_limit_minutes = IntegerField("Time limit (minutes)", validators=[Optional(), NumberRange(min=1)])
    is_published = BooleanField("Published", default=True)
    submit = SubmitField("Add quiz")


class QuestionForm(FlaskForm):
    """Admin form for creating quiz questions with multiple types."""

    prompt = TextAreaField("Question prompt", validators=[DataRequired(), Length(min=3, max=5000)])
    question_type = SelectField(
        "Question type",
        choices=[
            (QuestionType.MCQ.value, "MCQ"),
            (QuestionType.TRUE_FALSE.value, "True / False"),
            (QuestionType.SHORT_ANSWER.value, "Short Answer"),
        ],
        validators=[DataRequired()],
    )
    points = DecimalField("Points", validators=[DataRequired(), NumberRange(min=0.1)], default=1)
    sort_order = IntegerField("Sort order", validators=[DataRequired(), NumberRange(min=1)], default=1)

    option_a = StringField("Option A", validators=[Optional(), Length(max=500)])
    option_b = StringField("Option B", validators=[Optional(), Length(max=500)])
    option_c = StringField("Option C", validators=[Optional(), Length(max=500)])
    option_d = StringField("Option D", validators=[Optional(), Length(max=500)])
    correct_option = SelectField(
        "Correct MCQ option",
        choices=[("", "Choose correct option"), ("a", "A"), ("b", "B"), ("c", "C"), ("d", "D")],
        validators=[Optional()],
    )
    true_false_correct = SelectField(
        "Correct true/false answer",
        choices=[("", "Choose"), ("true", "True"), ("false", "False")],
        validators=[Optional()],
    )
    accepted_answers = TextAreaField(
        "Accepted short answers",
        validators=[Optional(), Length(max=5000)],
        description="Enter one answer per line.",
    )

    submit = SubmitField("Add question")


class SubscriptionPlanForm(FlaskForm):
    """Admin form for creating subscription plans."""

    name = StringField("Plan name", validators=[DataRequired(), Length(min=2, max=100)])
    description = TextAreaField("Description", validators=[Optional(), Length(max=5000)])
    price = DecimalField("Price", validators=[DataRequired(), NumberRange(min=0)])
    currency = StringField("Currency", validators=[DataRequired(), Length(min=3, max=10)], default="USD")
    billing_cycle = SelectField(
        "Billing cycle",
        choices=[("monthly", "Monthly"), ("yearly", "Yearly")],
        validators=[DataRequired()],
    )
    features_json = TextAreaField(
        "Features (JSON or text)",
        validators=[Optional(), Length(max=10000)],
        description="Optional: store raw JSON or plain text list of features.",
    )
    is_active = BooleanField("Active", default=True)
    submit = SubmitField("Create plan")


class AdminUserForm(FlaskForm):
    """Admin form for updating user account settings."""

    full_name = StringField("Full name", validators=[DataRequired(), Length(min=2, max=120)])
    role = SelectField(
        "Role",
        choices=[
            (UserRole.STUDENT.value, "Student"),
            (UserRole.PARENT.value, "Parent"),
            (UserRole.ADMIN.value, "Admin"),
        ],
        validators=[DataRequired()],
    )
    admin_access_level = SelectField(
        "Admin access level",
        choices=[
            (AdminAccessLevel.FULL.value, "Full Access"),
            (AdminAccessLevel.CONTENT.value, "Content Only"),
            (AdminAccessLevel.GRADING.value, "Grading Only"),
            (AdminAccessLevel.USERS.value, "User Management Only"),
            (AdminAccessLevel.ANALYTICS.value, "Analytics Only"),
            (AdminAccessLevel.VIEWER.value, "View Only"),
        ],
        validators=[DataRequired()],
    )
    is_approved = BooleanField("Approved")
    is_active = BooleanField("Active")
    new_password = StringField(
        "Optional new password",
        validators=[Optional(), Length(min=8, max=128)],
    )
    submit = SubmitField("Save User")


class ManualEnrollmentForm(FlaskForm):
    """Admin form for manually assigning a user to a main course."""

    user_id = SelectField("User", coerce=int, validators=[DataRequired()])
    main_course_id = SelectField("Main course", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Add Enrollment")


class ParentLinkForm(FlaskForm):
    """Admin form for linking parent and student accounts."""

    parent_id = SelectField("Parent", coerce=int, validators=[DataRequired()])
    student_id = SelectField("Student", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Link Parent to Student")
