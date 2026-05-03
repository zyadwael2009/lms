from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.models import AttemptStatus, Lesson, Question, Quiz, QuizAnswer, QuizAttempt, SubCourse
from app.utils.decorators import approved_required


learning_bp = Blueprint("learning", __name__, template_folder="../templates")


def _can_access_sub_course(sub_course_id: int) -> bool:
    """Centralized access check for sub-course-protected routes."""

    return current_user.is_admin or current_user.can_access_sub_course(sub_course_id)


@learning_bp.route("/sub-courses/<int:sub_course_id>")
@login_required
@approved_required
def sub_course_detail(sub_course_id: int):
    """Shows modules, lessons, and quizzes for one unlocked sub-course."""

    sub_course = SubCourse.query.get_or_404(sub_course_id)
    if not _can_access_sub_course(sub_course.id):
        flash("You are not enrolled in this course.", "danger")
        return redirect(url_for("main.my_courses"))

    latest_attempts = {}
    for module in sub_course.modules:
        for quiz in module.quizzes:
            latest_attempt = (
                QuizAttempt.query.filter_by(quiz_id=quiz.id, user_id=current_user.id)
                .order_by(QuizAttempt.created_at.desc())
                .first()
            )
            if latest_attempt:
                latest_attempts[quiz.id] = latest_attempt

    return render_template(
        "learning/sub_course_detail.html",
        sub_course=sub_course,
        latest_attempts=latest_attempts,
    )


@learning_bp.route("/lessons/<int:lesson_id>")
@login_required
@approved_required
def lesson_detail(lesson_id: int):
    """Renders one lesson with support for text, video, and PDF content."""

    lesson = Lesson.query.get_or_404(lesson_id)
    sub_course_id = lesson.module.sub_course_id

    if not _can_access_sub_course(sub_course_id):
        flash("You cannot access this lesson.", "danger")
        return redirect(url_for("main.my_courses"))

    return render_template("learning/lesson_detail.html", lesson=lesson)


@learning_bp.route("/quizzes/<int:quiz_id>/start", methods=["POST"])
@login_required
@approved_required
def start_quiz(quiz_id: int):
    """Creates a fresh quiz attempt and redirects to the answer form."""

    quiz = Quiz.query.get_or_404(quiz_id)
    sub_course_id = quiz.module.sub_course_id

    if not _can_access_sub_course(sub_course_id):
        flash("You cannot start this quiz.", "danger")
        return redirect(url_for("main.my_courses"))

    if not quiz.is_published:
        flash("This quiz is not available yet.", "warning")
        return redirect(url_for("learning.sub_course_detail", sub_course_id=sub_course_id))

    if not quiz.questions:
        flash("This quiz has no questions yet.", "warning")
        return redirect(url_for("learning.sub_course_detail", sub_course_id=sub_course_id))

    attempt = QuizAttempt(
        quiz_id=quiz.id,
        user_id=current_user.id,
        status=AttemptStatus.STARTED,
        started_at=datetime.now(timezone.utc),
    )
    db.session.add(attempt)
    db.session.commit()

    return redirect(url_for("learning.take_quiz", attempt_id=attempt.id))


@learning_bp.route("/attempts/<int:attempt_id>")
@login_required
@approved_required
def take_quiz(attempt_id: int):
    """Displays one active quiz attempt form."""

    attempt = QuizAttempt.query.get_or_404(attempt_id)

    if not current_user.is_admin and attempt.user_id != current_user.id:
        flash("You cannot access this quiz attempt.", "danger")
        return redirect(url_for("main.my_courses"))

    if attempt.status != AttemptStatus.STARTED:
        return redirect(url_for("learning.quiz_result", attempt_id=attempt.id))

    sub_course_id = attempt.quiz.module.sub_course_id
    if not _can_access_sub_course(sub_course_id):
        flash("You cannot access this quiz.", "danger")
        return redirect(url_for("main.my_courses"))

    return render_template("learning/take_quiz.html", attempt=attempt)


@learning_bp.route("/attempts/<int:attempt_id>/submit", methods=["POST"])
@login_required
@approved_required
def submit_quiz(attempt_id: int):
    """Grades submitted answers and stores final score details."""

    attempt = QuizAttempt.query.get_or_404(attempt_id)

    if attempt.user_id != current_user.id:
        flash("You cannot submit this attempt.", "danger")
        return redirect(url_for("main.my_courses"))

    if attempt.status != AttemptStatus.STARTED:
        flash("This attempt is already submitted.", "warning")
        return redirect(url_for("learning.quiz_result", attempt_id=attempt.id))

    sub_course_id = attempt.quiz.module.sub_course_id
    if not _can_access_sub_course(sub_course_id):
        flash("You cannot submit this quiz.", "danger")
        return redirect(url_for("main.my_courses"))

    attempt.answers.clear()

    for question in attempt.quiz.questions:
        option_key = f"question_{question.id}_option"
        text_key = f"question_{question.id}_text"

        selected_option_id = request.form.get(option_key, type=int)
        text_answer = (request.form.get(text_key) or "").strip()

        # Guard against tampering by ensuring selected options belong to the question.
        if selected_option_id and not any(option.id == selected_option_id for option in question.options):
            selected_option_id = None

        is_correct, points_awarded = question.grade(
            selected_option_id=selected_option_id,
            text_answer=text_answer,
        )

        answer = QuizAnswer(
            question_id=question.id,
            selected_option_id=selected_option_id,
            text_answer=text_answer or None,
            is_correct=is_correct,
            points_awarded=points_awarded,
        )
        attempt.answers.append(answer)

    attempt.submitted_at = datetime.now(timezone.utc)
    attempt.status = AttemptStatus.SUBMITTED
    attempt.recalculate_totals()

    db.session.commit()

    flash("Quiz submitted and graded successfully.", "success")
    return redirect(url_for("learning.quiz_result", attempt_id=attempt.id))


@learning_bp.route("/attempts/<int:attempt_id>/result")
@login_required
@approved_required
def quiz_result(attempt_id: int):
    """Shows score summary and per-question grading."""

    attempt = QuizAttempt.query.get_or_404(attempt_id)

    if not current_user.is_admin and attempt.user_id != current_user.id:
        flash("You cannot access this result.", "danger")
        return redirect(url_for("main.my_courses"))

    question_lookup: dict[int, Question] = {question.id: question for question in attempt.quiz.questions}

    answer_lookup = {answer.question_id: answer for answer in attempt.answers}

    return render_template(
        "learning/quiz_result.html",
        attempt=attempt,
        question_lookup=question_lookup,
        answer_lookup=answer_lookup,
    )


@learning_bp.route("/results")
@login_required
@approved_required
def my_results():
    """Lists historical quiz results for the current user."""

    attempts = (
        QuizAttempt.query.filter_by(user_id=current_user.id)
        .order_by(QuizAttempt.created_at.desc())
        .all()
    )

    return render_template("learning/my_results.html", attempts=attempts)
