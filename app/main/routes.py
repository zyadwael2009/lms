from __future__ import annotations

from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from app.models import Enrollment, MainCourse, ParentStudentLink, QuizAttempt, UserRole
from app.utils.decorators import approved_required, roles_required


main_bp = Blueprint("main", __name__, template_folder="../templates")


@main_bp.route("/")
def index():
    """Homepage/dashboard: public view for guests, course view for approved users."""

    if not current_user.is_authenticated:
        return render_template("main/index.html", enrolled_main_courses=[])

    if current_user.is_admin:
        return render_template("main/index.html", enrolled_main_courses=[])

    if not current_user.is_approved:
        return render_template("main/pending_approval.html")

    enrolled_main_courses = (
        MainCourse.query.join(Enrollment)
        .filter(Enrollment.user_id == current_user.id)
        .order_by(MainCourse.title.asc())
        .all()
    )

    return render_template("main/index.html", enrolled_main_courses=enrolled_main_courses)


@main_bp.route("/pending-approval")
@login_required
def pending_approval():
    """Shown to users while they are waiting for admin approval."""

    if current_user.is_admin or current_user.is_approved:
        return redirect(url_for("main.index"))
    return render_template("main/pending_approval.html")


@main_bp.route("/my-courses")
@login_required
@approved_required
def my_courses():
    """Explicit route listing all unlocked main and sub-courses for the user."""

    enrolled_main_courses = (
        MainCourse.query.join(Enrollment)
        .filter(Enrollment.user_id == current_user.id)
        .order_by(MainCourse.title.asc())
        .all()
    )

    return render_template("main/index.html", enrolled_main_courses=enrolled_main_courses)


@main_bp.route("/parent/children")
@login_required
@approved_required
@roles_required(UserRole.PARENT)
def parent_children():
    """Shows linked students and their learning summary to parent accounts."""

    links = ParentStudentLink.query.filter_by(parent_id=current_user.id).all()
    student_ids = [link.student_id for link in links]

    students = [link.student for link in links]

    course_counts = {}
    attempt_counts = {}
    average_scores = {}

    if student_ids:
        course_rows = (
            Enrollment.query.with_entities(Enrollment.user_id, func.count(Enrollment.id))
            .filter(Enrollment.user_id.in_(student_ids))
            .group_by(Enrollment.user_id)
            .all()
        )
        course_counts = {user_id: count for user_id, count in course_rows}

        attempt_rows = (
            QuizAttempt.query.with_entities(QuizAttempt.user_id, func.count(QuizAttempt.id))
            .filter(QuizAttempt.user_id.in_(student_ids))
            .group_by(QuizAttempt.user_id)
            .all()
        )
        attempt_counts = {user_id: count for user_id, count in attempt_rows}

        average_rows = (
            QuizAttempt.query.with_entities(QuizAttempt.user_id, func.avg(QuizAttempt.percentage))
            .filter(QuizAttempt.user_id.in_(student_ids))
            .group_by(QuizAttempt.user_id)
            .all()
        )
        average_scores = {user_id: float(avg or 0.0) for user_id, avg in average_rows}

    recent_attempts = (
        QuizAttempt.query.filter(QuizAttempt.user_id.in_(student_ids))
        .order_by(QuizAttempt.created_at.desc())
        .limit(20)
        .all()
        if student_ids
        else []
    )

    return render_template(
        "main/parent_children.html",
        students=students,
        course_counts=course_counts,
        attempt_counts=attempt_counts,
        average_scores=average_scores,
        recent_attempts=recent_attempts,
    )
