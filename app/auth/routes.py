from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.auth.forms import LoginForm, RegistrationForm
from app.extensions import db
from app.models import Enrollment, MainCourse, User, UserRole


auth_bp = Blueprint("auth", __name__, template_folder="../templates")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """Registers a new user account and sets it to pending approval."""

    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = RegistrationForm()

    if form.validate_on_submit():
        course_code = (form.main_course_code.data or "").strip().upper()
        requested_main_course = None

        if course_code:
            requested_main_course = MainCourse.query.filter_by(access_code=course_code, is_active=True).first()
            if not requested_main_course:
                form.main_course_code.errors.append("Invalid main course code.")
                return render_template("auth/register.html", form=form)

        try:
            user = User(
                full_name=form.full_name.data.strip(),
                email=form.email.data.strip().lower(),
                role=UserRole(form.role.data),
                is_approved=False,
                is_active=True,
                follow_up_code=form.follow_up_code.data.strip()  # Add this line
            )
            user.set_password(form.password.data)

            db.session.add(user)
            db.session.flush()

            # Enrollment is created immediately, but access is blocked until admin approval.
            if requested_main_course:
                enrollment = Enrollment(
                    user_id=user.id,
                    main_course_id=requested_main_course.id,
                    source="registration_code",
                )
                db.session.add(enrollment)

            db.session.commit()

        except Exception:
            db.session.rollback()
            flash("Unable to register right now. Please try again.", "danger")
            return render_template("auth/register.html", form=form)

        flash(
            "Registration submitted successfully. Your account is pending admin approval.",
            "success",
        )
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Authenticates a user and redirects by role/approval state."""

    if current_user.is_authenticated:
        if current_user.is_admin:
            return redirect(url_for("admin.dashboard"))
        if not current_user.is_approved:
            return redirect(url_for("main.pending_approval"))
        return redirect(url_for("main.index"))

    form = LoginForm()

    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.strip().lower()).first()

        if not user or not user.check_password(form.password.data):
            flash("Invalid email or password.", "danger")
            return render_template("auth/login.html", form=form)

        if not user.is_active:
            flash("Your account is inactive. Please contact support.", "danger")
            return render_template("auth/login.html", form=form)

        login_user(user, remember=form.remember.data)
        flash("Welcome back!", "success")

        if user.is_admin:
            return redirect(url_for("admin.dashboard"))

        if not user.is_approved:
            return redirect(url_for("main.pending_approval"))

        return redirect(url_for("main.index"))

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    """Ends the current user session."""

    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
