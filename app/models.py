from __future__ import annotations

import secrets
import string
from datetime import datetime, timezone
from enum import Enum

from flask_login import UserMixin

from .extensions import db, login_manager


class TimestampMixin:
    """Adds created_at and updated_at fields to inheriting models."""

    created_at = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class UserRole(Enum):
    ADMIN = "admin"
    TEACHER = "teacher"  # Legacy value kept for backward compatibility.
    STUDENT = "student"
    PARENT = "parent"


class AdminAccessLevel(Enum):
    FULL = "full"
    CONTENT = "content"
    GRADING = "grading"
    USERS = "users"
    ANALYTICS = "analytics"
    VIEWER = "viewer"


class LessonContentType(Enum):
    VIDEO = "video"
    PDF = "pdf"
    TEXT = "text"


class QuestionType(Enum):
    MCQ = "mcq"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"


class AttemptStatus(Enum):
    STARTED = "started"
    SUBMITTED = "submitted"
    GRADED = "graded"


class SubscriptionStatus(Enum):
    PENDING = "pending"
    ACTIVE = "active"
    CANCELED = "canceled"
    EXPIRED = "expired"


class PaymentStatus(Enum):
    INITIATED = "initiated"
    COMPLETED = "completed"
    FAILED = "failed"


class User(UserMixin, TimestampMixin, db.Model):
    """Represents every authenticated user in the LMS."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, index=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum(UserRole, native_enum=False), nullable=False, default=UserRole.STUDENT)
    admin_access_level = db.Column(
        db.Enum(AdminAccessLevel, native_enum=False), nullable=False, default=AdminAccessLevel.FULL
    )

    # New users start as pending until an admin approves them.
    is_approved = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    enrollments = db.relationship("Enrollment", back_populates="user", cascade="all, delete-orphan")
    quiz_attempts = db.relationship("QuizAttempt", back_populates="user", cascade="all, delete-orphan")

    sent_messages = db.relationship(
        "Message",
        foreign_keys="Message.sender_id",
        back_populates="sender",
        cascade="all, delete-orphan",
    )
    received_messages = db.relationship(
        "Message",
        foreign_keys="Message.receiver_id",
        back_populates="receiver",
        cascade="all, delete-orphan",
    )

    subscriptions = db.relationship("UserSubscription", back_populates="user", cascade="all, delete-orphan")

    parent_links = db.relationship(
        "ParentStudentLink",
        foreign_keys="ParentStudentLink.parent_id",
        back_populates="parent",
        cascade="all, delete-orphan",
    )
    student_links = db.relationship(
        "ParentStudentLink",
        foreign_keys="ParentStudentLink.student_id",
        back_populates="student",
        cascade="all, delete-orphan",
    )

    def set_password(self, raw_password: str) -> None:
        """Hashes and stores a password."""

        from werkzeug.security import generate_password_hash

        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        """Checks a plain password against the stored hash."""

        from werkzeug.security import check_password_hash

        return check_password_hash(self.password_hash, raw_password)

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    def has_admin_permission(self, permission: str) -> bool:
        """Checks if an admin account can access a protected admin capability."""

        if self.role != UserRole.ADMIN:
            return False

        if self.admin_access_level == AdminAccessLevel.FULL:
            return True

        if permission == "viewer":
            return True

        permission_map = {
            AdminAccessLevel.CONTENT: {"content"},
            AdminAccessLevel.GRADING: {"grading"},
            AdminAccessLevel.USERS: {"users"},
            AdminAccessLevel.ANALYTICS: {"analytics"},
            AdminAccessLevel.VIEWER: set(),
        }

        return permission in permission_map.get(self.admin_access_level, set())

    def can_access_main_course(self, main_course_id: int) -> bool:
        """Users can only access enrolled courses after approval."""

        if not self.is_approved and not self.is_admin:
            return False
        return any(enrollment.main_course_id == main_course_id for enrollment in self.enrollments)

    def can_access_sub_course(self, sub_course_id: int) -> bool:
        """Sub-course access is inherited from the parent main course enrollment."""

        sub_course = SubCourse.query.get(sub_course_id)
        if not sub_course:
            return False
        return self.can_access_main_course(sub_course.main_course_id)


class MainCourse(TimestampMixin, db.Model):
    """Top-level course that can contain multiple sub-courses."""

    __tablename__ = "main_courses"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)

    # Students can submit this code during registration to unlock course access.
    access_code = db.Column(db.String(24), unique=True, index=True, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    sub_courses = db.relationship(
        "SubCourse",
        back_populates="main_course",
        cascade="all, delete-orphan",
        order_by="SubCourse.sort_order",
    )
    enrollments = db.relationship("Enrollment", back_populates="main_course", cascade="all, delete-orphan")

    @staticmethod
    def generate_access_code(length: int = 8) -> str:
        """Creates an easy-to-share alphanumeric code for registrations."""

        alphabet = string.ascii_uppercase + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(length))


class SubCourse(TimestampMixin, db.Model):
    """Child course inside a main course."""

    __tablename__ = "sub_courses"

    id = db.Column(db.Integer, primary_key=True)
    main_course_id = db.Column(db.Integer, db.ForeignKey("main_courses.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    sort_order = db.Column(db.Integer, default=1, nullable=False)
    is_published = db.Column(db.Boolean, default=True, nullable=False)

    main_course = db.relationship("MainCourse", back_populates="sub_courses")
    modules = db.relationship(
        "CourseModule",
        back_populates="sub_course",
        cascade="all, delete-orphan",
        order_by="CourseModule.sort_order",
    )


class CourseModule(TimestampMixin, db.Model):
    """Logical grouping for lessons and quizzes inside a sub-course."""

    __tablename__ = "course_modules"

    id = db.Column(db.Integer, primary_key=True)
    sub_course_id = db.Column(db.Integer, db.ForeignKey("sub_courses.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    sort_order = db.Column(db.Integer, default=1, nullable=False)

    sub_course = db.relationship("SubCourse", back_populates="modules")
    lessons = db.relationship(
        "Lesson", back_populates="module", cascade="all, delete-orphan", order_by="Lesson.sort_order"
    )
    quizzes = db.relationship("Quiz", back_populates="module", cascade="all, delete-orphan")


class Lesson(TimestampMixin, db.Model):
    """Learning unit supporting video, PDF, or text content."""

    __tablename__ = "lessons"

    id = db.Column(db.Integer, primary_key=True)
    module_id = db.Column(db.Integer, db.ForeignKey("course_modules.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content_type = db.Column(
        db.Enum(LessonContentType, native_enum=False), default=LessonContentType.TEXT, nullable=False
    )
    content_url = db.Column(db.String(500))
    text_content = db.Column(db.Text)
    sort_order = db.Column(db.Integer, default=1, nullable=False)
    is_published = db.Column(db.Boolean, default=True, nullable=False)

    module = db.relationship("CourseModule", back_populates="lessons")


class Quiz(TimestampMixin, db.Model):
    """Quiz attached to a course module."""

    __tablename__ = "quizzes"

    id = db.Column(db.Integer, primary_key=True)
    module_id = db.Column(db.Integer, db.ForeignKey("course_modules.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    is_published = db.Column(db.Boolean, default=True, nullable=False)
    time_limit_minutes = db.Column(db.Integer)

    module = db.relationship("CourseModule", back_populates="quizzes")
    questions = db.relationship(
        "Question", back_populates="quiz", cascade="all, delete-orphan", order_by="Question.sort_order"
    )
    attempts = db.relationship("QuizAttempt", back_populates="quiz", cascade="all, delete-orphan")


class Question(TimestampMixin, db.Model):
    """Question with MCQ, true/false, or short-answer support."""

    __tablename__ = "questions"

    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey("quizzes.id"), nullable=False)
    prompt = db.Column(db.Text, nullable=False)
    question_type = db.Column(db.Enum(QuestionType, native_enum=False), nullable=False)
    points = db.Column(db.Float, default=1.0, nullable=False)
    sort_order = db.Column(db.Integer, default=1, nullable=False)

    quiz = db.relationship("Quiz", back_populates="questions")
    options = db.relationship(
        "QuestionOption",
        back_populates="question",
        cascade="all, delete-orphan",
        order_by="QuestionOption.id",
    )

    def grade(self, selected_option_id: int | None, text_answer: str | None) -> tuple[bool, float]:
        """Auto-grades objective questions and simple exact-match short answers."""

        if self.question_type in {QuestionType.MCQ, QuestionType.TRUE_FALSE}:
            correct_option = next((option for option in self.options if option.is_correct), None)
            is_correct = bool(correct_option and selected_option_id == correct_option.id)
            return is_correct, self.points if is_correct else 0.0

        # For short answer questions, correct options store accepted exact answers.
        accepted_answers = {
            option.option_text.strip().lower()
            for option in self.options
            if option.is_correct and option.option_text
        }
        normalized = (text_answer or "").strip().lower()
        is_correct = normalized in accepted_answers if accepted_answers else False
        return is_correct, self.points if is_correct else 0.0


class QuestionOption(TimestampMixin, db.Model):
    """Option used by MCQ/true-false and accepted answers for short-answer."""

    __tablename__ = "question_options"

    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id"), nullable=False)
    option_text = db.Column(db.String(500), nullable=False)
    is_correct = db.Column(db.Boolean, default=False, nullable=False)

    question = db.relationship("Question", back_populates="options")


class QuizAttempt(TimestampMixin, db.Model):
    """Tracks one student's attempt and resulting score."""

    __tablename__ = "quiz_attempts"

    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey("quizzes.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    status = db.Column(db.Enum(AttemptStatus, native_enum=False), default=AttemptStatus.STARTED, nullable=False)
    score = db.Column(db.Float, default=0.0, nullable=False)
    max_score = db.Column(db.Float, default=0.0, nullable=False)
    percentage = db.Column(db.Float, default=0.0, nullable=False)

    started_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    submitted_at = db.Column(db.DateTime(timezone=True))
    graded_at = db.Column(db.DateTime(timezone=True))

    quiz = db.relationship("Quiz", back_populates="attempts")
    user = db.relationship("User", back_populates="quiz_attempts")
    answers = db.relationship("QuizAnswer", back_populates="attempt", cascade="all, delete-orphan")

    def recalculate_totals(self) -> None:
        """Computes score statistics after grading answers."""

        self.max_score = sum(question.points for question in self.quiz.questions)
        self.score = sum(answer.points_awarded or 0.0 for answer in self.answers)
        self.percentage = (self.score / self.max_score * 100.0) if self.max_score else 0.0
        self.graded_at = datetime.now(timezone.utc)
        self.status = AttemptStatus.GRADED


class QuizAnswer(TimestampMixin, db.Model):
    """Stores an answer to one question inside an attempt."""

    __tablename__ = "quiz_answers"

    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey("quiz_attempts.id"), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey("questions.id"), nullable=False)
    selected_option_id = db.Column(db.Integer, db.ForeignKey("question_options.id"))
    text_answer = db.Column(db.Text)

    is_correct = db.Column(db.Boolean)
    points_awarded = db.Column(db.Float, default=0.0, nullable=False)

    attempt = db.relationship("QuizAttempt", back_populates="answers")
    question = db.relationship("Question")
    selected_option = db.relationship("QuestionOption")


class Enrollment(TimestampMixin, db.Model):
    """Enrollment in a main course grants access to all of its sub-courses."""

    __tablename__ = "enrollments"
    __table_args__ = (db.UniqueConstraint("user_id", "main_course_id", name="uq_user_main_course"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    main_course_id = db.Column(db.Integer, db.ForeignKey("main_courses.id"), nullable=False)
    source = db.Column(db.String(50), default="registration_code", nullable=False)

    user = db.relationship("User", back_populates="enrollments")
    main_course = db.relationship("MainCourse", back_populates="enrollments")


class ParentStudentLink(TimestampMixin, db.Model):
    """Links parent accounts with student accounts for guardian visibility."""

    __tablename__ = "parent_student_links"
    __table_args__ = (db.UniqueConstraint("parent_id", "student_id", name="uq_parent_student_link"),)

    id = db.Column(db.Integer, primary_key=True)
    parent_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    parent = db.relationship("User", foreign_keys=[parent_id], back_populates="parent_links")
    student = db.relationship("User", foreign_keys=[student_id], back_populates="student_links")


class Message(TimestampMixin, db.Model):
    """Direct user-to-user messaging."""

    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    subject = db.Column(db.String(200))
    body = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)

    sender = db.relationship("User", foreign_keys=[sender_id], back_populates="sent_messages")
    receiver = db.relationship("User", foreign_keys=[receiver_id], back_populates="received_messages")


class SubscriptionPlan(TimestampMixin, db.Model):
    """Defines purchasable subscription plans."""

    __tablename__ = "subscription_plans"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False, default=0.0)
    currency = db.Column(db.String(10), nullable=False, default="USD")
    billing_cycle = db.Column(db.String(20), nullable=False, default="monthly")
    features_json = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    user_subscriptions = db.relationship("UserSubscription", back_populates="plan")


class UserSubscription(TimestampMixin, db.Model):
    """Connects a user to a subscription plan and tracks lifecycle."""

    __tablename__ = "user_subscriptions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    plan_id = db.Column(db.Integer, db.ForeignKey("subscription_plans.id"), nullable=False)
    status = db.Column(
        db.Enum(SubscriptionStatus, native_enum=False), default=SubscriptionStatus.PENDING, nullable=False
    )

    starts_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    ends_at = db.Column(db.DateTime(timezone=True))
    auto_renew = db.Column(db.Boolean, default=True, nullable=False)

    payment_provider = db.Column(db.String(50))
    payment_reference = db.Column(db.String(255))

    user = db.relationship("User", back_populates="subscriptions")
    plan = db.relationship("SubscriptionPlan", back_populates="user_subscriptions")
    transactions = db.relationship("PaymentTransaction", back_populates="subscription")


class PaymentTransaction(TimestampMixin, db.Model):
    """Stores payment events for auditing and reconciliation."""

    __tablename__ = "payment_transactions"

    id = db.Column(db.Integer, primary_key=True)
    user_subscription_id = db.Column(db.Integer, db.ForeignKey("user_subscriptions.id"), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), nullable=False, default="USD")
    status = db.Column(db.Enum(PaymentStatus, native_enum=False), default=PaymentStatus.INITIATED, nullable=False)
    provider = db.Column(db.String(50))
    provider_transaction_id = db.Column(db.String(255))
    paid_at = db.Column(db.DateTime(timezone=True))

    subscription = db.relationship("UserSubscription", back_populates="transactions")


@login_manager.user_loader
def load_user(user_id: str) -> User | None:
    """Flask-Login callback for loading user sessions."""

    if not user_id.isdigit():
        return None
    return User.query.get(int(user_id))
