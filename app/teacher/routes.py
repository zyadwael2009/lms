from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.extensions import db
from app.models import (
    AttemptStatus,
    Lesson,
    MainCourse,
    Quiz,
    QuizAttempt,
    SubCourse,
    User,
    UserRole,
)
from app.utils.decorators import admin_permission_required


teacher_bp = Blueprint("teacher", __name__, template_folder="../templates")


@teacher_bp.route("/dashboard")
@login_required
@admin_permission_required("viewer")
def dashboard():
    """Admin teaching dashboard with quick instructional metrics."""

    metrics = {
        "students": User.query.filter_by(role=UserRole.STUDENT, is_active=True, is_approved=True).count(),
        "sub_courses": SubCourse.query.filter_by(is_published=True).count(),
        "lessons": Lesson.query.filter_by(is_published=True).count(),
        "quizzes": Quiz.query.filter_by(is_published=True).count(),
        "attempts": QuizAttempt.query.count(),
    }

    latest_attempts = QuizAttempt.query.order_by(QuizAttempt.created_at.desc()).limit(10).all()

    return render_template("teacher/dashboard.html", metrics=metrics, latest_attempts=latest_attempts)


@teacher_bp.route("/content-review")
@login_required
@admin_permission_required("content")
def content_review():
    """Central workflow for publishing/unpublishing teaching content."""

    unpublished_sub_courses = (
        SubCourse.query.filter_by(is_published=False).order_by(SubCourse.created_at.desc()).all()
    )
    unpublished_lessons = Lesson.query.filter_by(is_published=False).order_by(Lesson.created_at.desc()).all()
    unpublished_quizzes = Quiz.query.filter_by(is_published=False).order_by(Quiz.created_at.desc()).all()

    published_sub_courses = SubCourse.query.filter_by(is_published=True).order_by(SubCourse.created_at.desc()).limit(10).all()
    published_lessons = Lesson.query.filter_by(is_published=True).order_by(Lesson.created_at.desc()).limit(10).all()
    published_quizzes = Quiz.query.filter_by(is_published=True).order_by(Quiz.created_at.desc()).limit(10).all()

    return render_template(
        "teacher/content_review.html",
        unpublished_sub_courses=unpublished_sub_courses,
        unpublished_lessons=unpublished_lessons,
        unpublished_quizzes=unpublished_quizzes,
        published_sub_courses=published_sub_courses,
        published_lessons=published_lessons,
        published_quizzes=published_quizzes,
    )


@teacher_bp.route("/sub-courses/<int:sub_course_id>/toggle-publish", methods=["POST"])
@login_required
@admin_permission_required("content")
def toggle_sub_course_publish(sub_course_id: int):
    """Toggles publication status of a sub-course."""

    sub_course = SubCourse.query.get_or_404(sub_course_id)
    sub_course.is_published = not sub_course.is_published
    db.session.commit()

    status = "published" if sub_course.is_published else "unpublished"
    flash(f"Sub-course '{sub_course.title}' is now {status}.", "success")
    return redirect(url_for("teacher.content_review"))


@teacher_bp.route("/lessons/<int:lesson_id>/toggle-publish", methods=["POST"])
@login_required
@admin_permission_required("content")
def toggle_lesson_publish(lesson_id: int):
    """Toggles publication status of a lesson."""

    lesson = Lesson.query.get_or_404(lesson_id)
    lesson.is_published = not lesson.is_published
    db.session.commit()

    status = "published" if lesson.is_published else "unpublished"
    flash(f"Lesson '{lesson.title}' is now {status}.", "success")
    return redirect(url_for("teacher.content_review"))


@teacher_bp.route("/quizzes/<int:quiz_id>/toggle-publish", methods=["POST"])
@login_required
@admin_permission_required("content")
def toggle_quiz_publish(quiz_id: int):
    """Toggles publication status of a quiz."""

    quiz = Quiz.query.get_or_404(quiz_id)
    quiz.is_published = not quiz.is_published
    db.session.commit()

    status = "published" if quiz.is_published else "unpublished"
    flash(f"Quiz '{quiz.title}' is now {status}.", "success")
    return redirect(url_for("teacher.content_review"))


@teacher_bp.route("/attempts")
@login_required
@admin_permission_required("grading")
def attempts():
    """Lists quiz attempts for manual review and override grading."""

    status_filter = (request.args.get("status") or "").strip().lower()

    query = QuizAttempt.query.order_by(QuizAttempt.created_at.desc())

    status_map = {
        "started": AttemptStatus.STARTED,
        "submitted": AttemptStatus.SUBMITTED,
        "graded": AttemptStatus.GRADED,
    }
    if status_filter in status_map:
        query = query.filter(QuizAttempt.status == status_map[status_filter])

    records = query.limit(200).all()

    return render_template("teacher/attempts.html", attempts=records, status_filter=status_filter)


@teacher_bp.route("/attempts/<int:attempt_id>/review", methods=["GET", "POST"])
@login_required
@admin_permission_required("grading")
def review_attempt(attempt_id: int):
    """Allows admin to override points/correctness per answer."""

    attempt = QuizAttempt.query.get_or_404(attempt_id)

    if request.method == "POST":
        updates = 0
        for answer in attempt.answers:
            points_raw = request.form.get(f"points_{answer.id}", "").strip()
            is_correct_flag = request.form.get(f"correct_{answer.id}") == "on"

            try:
                points_value = float(points_raw) if points_raw else (answer.points_awarded or 0.0)
            except ValueError:
                flash("Invalid numeric value in points fields.", "danger")
                return redirect(url_for("teacher.review_attempt", attempt_id=attempt.id))

            max_points = answer.question.points if answer.question else 0.0
            points_value = max(0.0, min(points_value, float(max_points)))

            if answer.points_awarded != points_value or answer.is_correct != is_correct_flag:
                answer.points_awarded = points_value
                answer.is_correct = is_correct_flag
                updates += 1

        if updates:
            attempt.recalculate_totals()
            attempt.status = AttemptStatus.GRADED
            db.session.commit()
            flash("Attempt grading overrides saved.", "success")
        else:
            flash("No grading changes detected.", "info")

        return redirect(url_for("teacher.review_attempt", attempt_id=attempt.id))

    return render_template("teacher/review_attempt.html", attempt=attempt)


@teacher_bp.route("/course-overview")
@login_required
@admin_permission_required("content")
def course_overview():
    """Shows course hierarchy for quick admin teaching navigation."""

    main_courses = MainCourse.query.order_by(MainCourse.title.asc()).all()
    return render_template("teacher/course_overview.html", main_courses=main_courses)
