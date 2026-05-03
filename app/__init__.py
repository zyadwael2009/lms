from __future__ import annotations

import click
from flask import Flask

from config import config_by_name

from .extensions import csrf, db, login_manager, migrate
from .models import (
    CourseModule,
    Lesson,
    LessonContentType,
    MainCourse,
    Question,
    QuestionOption,
    QuestionType,
    Quiz,
    SubCourse,
    SubscriptionPlan,
    User,
    UserRole,
)


def create_app(config_name: str = "development") -> Flask:
    """Application factory used by Flask CLI and production servers."""

    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(config_by_name.get(config_name, config_by_name["development"]))

    initialize_extensions(app)
    register_blueprints(app)
    register_cli_commands(app)

    return app


def initialize_extensions(app: Flask) -> None:
    """Initializes extension objects with the Flask app."""

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to continue."
    login_manager.login_message_category = "warning"


def register_blueprints(app: Flask) -> None:
    """Registers all route groups (Blueprints)."""

    from .admin.routes import admin_bp
    from .auth.routes import auth_bp
    from .billing.routes import billing_bp
    from .learning.routes import learning_bp
    from .main.routes import main_bp
    from .messaging.routes import messaging_bp
    from .teacher.routes import teacher_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(learning_bp, url_prefix="/learning")
    app.register_blueprint(messaging_bp, url_prefix="/messages")
    app.register_blueprint(billing_bp, url_prefix="/billing")
    app.register_blueprint(teacher_bp, url_prefix="/admin/teaching")


def register_cli_commands(app: Flask) -> None:
    """Adds helpful CLI commands for setup and admin bootstrapping."""

    @app.cli.command("init-db")
    def init_db_command() -> None:
        db.create_all()
        click.echo("Database tables created.")

    @app.cli.command("create-admin")
    @click.option("--name", prompt=True, help="Admin full name")
    @click.option("--email", prompt=True, help="Admin email")
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
    def create_admin_command(name: str, email: str, password: str) -> None:
        normalized_email = email.strip().lower()
        existing_user = User.query.filter_by(email=normalized_email).first()
        if existing_user:
            click.echo("A user with this email already exists.")
            return

        admin = User(
            full_name=name.strip(),
            email=normalized_email,
            role=UserRole.ADMIN,
            is_approved=True,
            is_active=True,
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()

        click.echo("Admin user created successfully.")

    @app.cli.command("seed-main-course")
    @click.option("--title", prompt=True, help="Main course title")
    @click.option("--description", prompt=False, default="", help="Main course description")
    @click.option("--code", prompt=False, default="", help="Optional custom access code")
    def seed_main_course_command(title: str, description: str, code: str) -> None:
        access_code = (code or MainCourse.generate_access_code()).strip().upper()
        while MainCourse.query.filter_by(access_code=access_code).first():
            access_code = MainCourse.generate_access_code()

        main_course = MainCourse(title=title.strip(), description=description.strip(), access_code=access_code)
        db.session.add(main_course)
        db.session.commit()

        click.echo(f"Main course created with access code: {access_code}")

    @app.cli.command("seed-plan")
    @click.option("--name", prompt=True, help="Plan name")
    @click.option("--price", prompt=True, type=float, help="Plan price")
    @click.option("--currency", prompt=False, default="USD", help="Currency code")
    @click.option("--cycle", prompt=False, default="monthly", help="Billing cycle")
    @click.option("--description", prompt=False, default="", help="Plan description")
    def seed_plan_command(name: str, price: float, currency: str, cycle: str, description: str) -> None:
        normalized_name = name.strip()
        existing_plan = SubscriptionPlan.query.filter_by(name=normalized_name).first()
        if existing_plan:
            click.echo("A plan with this name already exists.")
            return

        plan = SubscriptionPlan(
            name=normalized_name,
            description=description.strip(),
            price=price,
            currency=currency.strip().upper(),
            billing_cycle=cycle.strip().lower(),
            is_active=True,
        )
        db.session.add(plan)
        db.session.commit()
        click.echo("Subscription plan created.")

    @app.cli.command("seed-demo-content")
    @click.option("--main-course-id", type=int, default=0, help="Existing main course ID")
    def seed_demo_content_command(main_course_id: int) -> None:
        """Seeds one sub-course, module, lesson, and quiz with mixed question types."""

        main_course = None
        if main_course_id:
            main_course = MainCourse.query.get(main_course_id)

        if not main_course:
            main_course = MainCourse.query.order_by(MainCourse.id.asc()).first()

        if not main_course:
            access_code = MainCourse.generate_access_code()
            while MainCourse.query.filter_by(access_code=access_code).first():
                access_code = MainCourse.generate_access_code()
            main_course = MainCourse(
                title="Demo Main Course",
                description="Generated demo main course",
                access_code=access_code,
            )
            db.session.add(main_course)
            db.session.flush()

        sub_course = SubCourse(
            main_course_id=main_course.id,
            title="Demo Sub-Course",
            description="Generated sub-course for testing phase 2",
            sort_order=1,
            is_published=True,
        )
        db.session.add(sub_course)
        db.session.flush()

        module = CourseModule(
            sub_course_id=sub_course.id,
            title="Demo Module",
            description="Contains one lesson and one quiz",
            sort_order=1,
        )
        db.session.add(module)
        db.session.flush()

        lesson = Lesson(
            module_id=module.id,
            title="Demo Text Lesson",
            content_type=LessonContentType.TEXT,
            text_content="This is a demo lesson used to validate learning flows.",
            sort_order=1,
            is_published=True,
        )
        db.session.add(lesson)
        db.session.flush()

        quiz = Quiz(
            module_id=module.id,
            title="Demo Quiz",
            description="Auto-graded demonstration quiz",
            is_published=True,
            time_limit_minutes=None,
        )
        db.session.add(quiz)
        db.session.flush()

        mcq = Question(
            quiz_id=quiz.id,
            prompt="Which planet is known as the Red Planet?",
            question_type=QuestionType.MCQ,
            points=2,
            sort_order=1,
        )
        tf = Question(
            quiz_id=quiz.id,
            prompt="The Earth is flat.",
            question_type=QuestionType.TRUE_FALSE,
            points=1,
            sort_order=2,
        )
        short = Question(
            quiz_id=quiz.id,
            prompt="Write the capital city of France.",
            question_type=QuestionType.SHORT_ANSWER,
            points=2,
            sort_order=3,
        )
        db.session.add_all([mcq, tf, short])
        db.session.flush()

        db.session.add_all(
            [
                QuestionOption(question_id=mcq.id, option_text="Mars", is_correct=True),
                QuestionOption(question_id=mcq.id, option_text="Venus", is_correct=False),
                QuestionOption(question_id=mcq.id, option_text="Jupiter", is_correct=False),
                QuestionOption(question_id=tf.id, option_text="True", is_correct=False),
                QuestionOption(question_id=tf.id, option_text="False", is_correct=True),
                QuestionOption(question_id=short.id, option_text="Paris", is_correct=True),
            ]
        )

        db.session.commit()
        click.echo(f"Demo content created under main course: {main_course.title} ({main_course.access_code})")
