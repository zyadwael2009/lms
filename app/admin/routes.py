from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from app.admin.forms import (
    AdminUserForm,
    LessonForm,
    MainCourseForm,
    ManualEnrollmentForm,
    ModuleForm,
    ParentLinkForm,
    QuestionForm,
    QuizForm,
    SubCourseForm,
    SubscriptionPlanForm,
)
from app.extensions import db
from app.models import (
    AdminAccessLevel,
    CourseModule,
    Enrollment,
    Lesson,
    LessonContentType,
    MainCourse,
    Message,
    ParentStudentLink,
    Question,
    QuestionOption,
    QuestionType,
    Quiz,
    QuizAttempt,
    SubCourse,
    SubscriptionPlan,
    SubscriptionStatus,
    User,
    UserRole,
    UserSubscription,
)
from app.utils.decorators import admin_permission_required


admin_bp = Blueprint("admin", __name__, template_folder="../templates")


@admin_bp.route("/dashboard")
@login_required
@admin_permission_required("viewer")
def dashboard():
    """Admin overview with operational counts and quick analytics."""

    pending_users_count = User.query.filter(User.is_approved.is_(False), User.is_active.is_(True)).count()
    main_courses_count = MainCourse.query.count()
    sub_courses_count = SubCourse.query.count()
    quizzes_count = Quiz.query.count()
    attempts_count = QuizAttempt.query.count()
    messages_count = Message.query.count()
    active_subscriptions_count = UserSubscription.query.filter(
        UserSubscription.status == SubscriptionStatus.ACTIVE
    ).count()

    recent_users = User.query.order_by(User.created_at.desc()).limit(10).all()

    return render_template(
        "admin/dashboard.html",
        pending_users_count=pending_users_count,
        main_courses_count=main_courses_count,
        sub_courses_count=sub_courses_count,
        quizzes_count=quizzes_count,
        attempts_count=attempts_count,
        messages_count=messages_count,
        active_subscriptions_count=active_subscriptions_count,
        recent_users=recent_users,
    )


@admin_bp.route("/analytics")
@login_required
@admin_permission_required("analytics")
def analytics():
    """Provides high-level platform analytics for admins."""

    role_counts = {
        role.value: User.query.filter(User.role == role).count()
        for role in [UserRole.ADMIN, UserRole.STUDENT, UserRole.PARENT]
    }

    approval_counts = {
        "approved": User.query.filter(User.is_approved.is_(True), User.is_active.is_(True)).count(),
        "pending": User.query.filter(User.is_approved.is_(False), User.is_active.is_(True)).count(),
        "inactive": User.query.filter(User.is_active.is_(False)).count(),
    }

    content_counts = {
        "main_courses": MainCourse.query.count(),
        "sub_courses": SubCourse.query.count(),
        "modules": CourseModule.query.count(),
        "lessons": Lesson.query.count(),
        "quizzes": Quiz.query.count(),
        "questions": Question.query.count(),
    }

    avg_percentage = db.session.query(func.avg(QuizAttempt.percentage)).scalar() or 0.0
    total_attempts = QuizAttempt.query.count()

    quiz_performance_rows = (
        db.session.query(
            Quiz.title,
            func.count(QuizAttempt.id).label("attempt_count"),
            func.avg(QuizAttempt.percentage).label("avg_percentage"),
        )
        .join(QuizAttempt, QuizAttempt.quiz_id == Quiz.id)
        .group_by(Quiz.id, Quiz.title)
        .order_by(func.avg(QuizAttempt.percentage).desc())
        .limit(12)
        .all()
    )

    quiz_performance = [
        {
            "title": row.title,
            "attempt_count": int(row.attempt_count or 0),
            "avg_percentage": float(row.avg_percentage or 0.0),
        }
        for row in quiz_performance_rows
    ]

    return render_template(
        "admin/analytics.html",
        role_counts=role_counts,
        approval_counts=approval_counts,
        content_counts=content_counts,
        total_attempts=total_attempts,
        avg_percentage=float(avg_percentage),
        quiz_performance=quiz_performance,
    )


@admin_bp.route("/users")
@login_required
@admin_permission_required("users")
def manage_users():
    """Lists users with filters and quick account management options."""

    query = User.query

    search = (request.args.get("q") or "").strip()
    role_filter = (request.args.get("role") or "").strip().lower()
    status_filter = (request.args.get("status") or "").strip().lower()

    if search:
        like_pattern = f"%{search}%"
        query = query.filter((User.full_name.ilike(like_pattern)) | (User.email.ilike(like_pattern)))

    if role_filter in {UserRole.ADMIN.value, UserRole.STUDENT.value, UserRole.PARENT.value}:
        query = query.filter(User.role == UserRole(role_filter))

    if status_filter == "approved":
        query = query.filter(User.is_approved.is_(True), User.is_active.is_(True))
    elif status_filter == "pending":
        query = query.filter(User.is_approved.is_(False), User.is_active.is_(True))
    elif status_filter == "inactive":
        query = query.filter(User.is_active.is_(False))

    users = query.order_by(User.created_at.desc()).all()

    return render_template(
        "admin/manage_users.html",
        users=users,
        search=search,
        role_filter=role_filter,
        status_filter=status_filter,
    )


@admin_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@admin_permission_required("users")
def edit_user(user_id: int):
    """Edits user role, approval state, activation, admin scope, and password."""

    user = User.query.get_or_404(user_id)
    form = AdminUserForm(obj=user)

    if request.method == "GET":
        form.role.data = user.role.value
        form.admin_access_level.data = user.admin_access_level.value

    if form.validate_on_submit():
        user.full_name = form.full_name.data.strip()
        user.role = UserRole(form.role.data)
        user.is_approved = bool(form.is_approved.data)
        user.is_active = bool(form.is_active.data)

        if user.role == UserRole.ADMIN:
            user.admin_access_level = AdminAccessLevel(form.admin_access_level.data)
        else:
            user.admin_access_level = AdminAccessLevel.VIEWER

        if user.id == current_user.id:
            if user.role != UserRole.ADMIN:
                flash("You cannot remove your own admin role.", "danger")
                return render_template("admin/edit_user.html", form=form, user=user)
            if not user.is_active:
                flash("You cannot deactivate your own account.", "danger")
                return render_template("admin/edit_user.html", form=form, user=user)

        if form.new_password.data:
            user.set_password(form.new_password.data)

        db.session.commit()
        flash("User updated successfully.", "success")
        return redirect(url_for("admin.manage_users"))

    return render_template("admin/edit_user.html", form=form, user=user)


@admin_bp.route("/users/pending")
@login_required
@admin_permission_required("users")
def pending_users():
    """Lists users waiting for approval."""

    users = (
        User.query.filter(User.is_approved.is_(False), User.is_active.is_(True), User.role != UserRole.ADMIN)
        .order_by(User.created_at.asc())
        .all()
    )
    return render_template("admin/pending_users.html", users=users)


@admin_bp.route("/users/<int:user_id>/approve", methods=["POST"])
@login_required
@admin_permission_required("users")
def approve_user(user_id: int):
    """Approves a user so enrolled courses become accessible."""

    user = User.query.get_or_404(user_id)

    if user.is_approved:
        flash("User is already approved.", "info")
        return redirect(url_for("admin.pending_users"))

    user.is_approved = True
    db.session.commit()

    flash(f"Approved {user.full_name}.", "success")
    return redirect(url_for("admin.pending_users"))


@admin_bp.route("/users/<int:user_id>/reject", methods=["POST"])
@login_required
@admin_permission_required("users")
def reject_user(user_id: int):
    """Rejects a pending user by deactivating the account."""

    user = User.query.get_or_404(user_id)
    if user.role == UserRole.ADMIN:
        flash("Cannot reject admin accounts.", "danger")
        return redirect(url_for("admin.pending_users"))

    user.is_active = False
    db.session.commit()

    flash(f"Rejected {user.full_name}.", "warning")
    return redirect(url_for("admin.pending_users"))


@admin_bp.route("/enrollments", methods=["GET", "POST"])
@login_required
@admin_permission_required("users")
def manage_enrollments():
    """Allows admins to manually enroll users in main courses."""

    form = ManualEnrollmentForm()

    eligible_users = (
        User.query.filter(User.role.in_([UserRole.STUDENT, UserRole.PARENT]), User.is_active.is_(True))
        .order_by(User.full_name.asc())
        .all()
    )
    main_courses = MainCourse.query.order_by(MainCourse.title.asc()).all()

    form.user_id.choices = [(u.id, f"{u.full_name} ({u.email})") for u in eligible_users]
    form.main_course_id.choices = [(c.id, f"{c.title} ({c.access_code})") for c in main_courses]

    if form.validate_on_submit():
        existing = Enrollment.query.filter_by(user_id=form.user_id.data, main_course_id=form.main_course_id.data).first()
        if existing:
            flash("This enrollment already exists.", "warning")
            return redirect(url_for("admin.manage_enrollments"))

        enrollment = Enrollment(
            user_id=form.user_id.data,
            main_course_id=form.main_course_id.data,
            source="admin_manual",
        )
        db.session.add(enrollment)
        db.session.commit()

        flash("Enrollment created successfully.", "success")
        return redirect(url_for("admin.manage_enrollments"))

    enrollments = (
        Enrollment.query.join(User, Enrollment.user_id == User.id)
        .join(MainCourse, Enrollment.main_course_id == MainCourse.id)
        .order_by(Enrollment.created_at.desc())
        .all()
    )

    return render_template("admin/manage_enrollments.html", form=form, enrollments=enrollments)


@admin_bp.route("/enrollments/<int:enrollment_id>/delete", methods=["POST"])
@login_required
@admin_permission_required("users")
def delete_enrollment(enrollment_id: int):
    """Removes a manual or code-based enrollment."""

    enrollment = Enrollment.query.get_or_404(enrollment_id)
    db.session.delete(enrollment)
    db.session.commit()

    flash("Enrollment removed.", "info")
    return redirect(url_for("admin.manage_enrollments"))


@admin_bp.route("/parent-links", methods=["GET", "POST"])
@login_required
@admin_permission_required("users")
def manage_parent_links():
    """Manages parent-to-student guardianship links."""

    form = ParentLinkForm()

    parents = User.query.filter_by(role=UserRole.PARENT, is_active=True).order_by(User.full_name.asc()).all()
    students = User.query.filter_by(role=UserRole.STUDENT, is_active=True).order_by(User.full_name.asc()).all()
    form.parent_id.choices = [(u.id, f"{u.full_name} ({u.email})") for u in parents]
    form.student_id.choices = [(u.id, f"{u.full_name} ({u.email})") for u in students]

    if form.validate_on_submit():
        if form.parent_id.data == form.student_id.data:
            flash("Parent and student cannot be the same account.", "danger")
            return redirect(url_for("admin.manage_parent_links"))

        existing = ParentStudentLink.query.filter_by(
            parent_id=form.parent_id.data,
            student_id=form.student_id.data,
        ).first()
        if existing:
            flash("This parent-student link already exists.", "warning")
            return redirect(url_for("admin.manage_parent_links"))

        link = ParentStudentLink(parent_id=form.parent_id.data, student_id=form.student_id.data)
        db.session.add(link)
        db.session.commit()
        flash("Parent linked to student successfully.", "success")
        return redirect(url_for("admin.manage_parent_links"))

    links = ParentStudentLink.query.order_by(ParentStudentLink.created_at.desc()).all()

    return render_template("admin/manage_parent_links.html", form=form, links=links)


@admin_bp.route("/parent-links/<int:link_id>/delete", methods=["POST"])
@login_required
@admin_permission_required("users")
def delete_parent_link(link_id: int):
    """Removes a parent-student relationship link."""

    link = ParentStudentLink.query.get_or_404(link_id)
    db.session.delete(link)
    db.session.commit()

    flash("Parent link removed.", "info")
    return redirect(url_for("admin.manage_parent_links"))


@admin_bp.route("/courses", methods=["GET", "POST"])
@login_required
@admin_permission_required("content")
def manage_courses():
    """Creates and lists main courses."""

    form = MainCourseForm()

    if form.validate_on_submit():
        custom_code = (form.access_code.data or "").strip().upper()
        access_code = custom_code or MainCourse.generate_access_code()

        if custom_code and MainCourse.query.filter_by(access_code=custom_code).first():
            form.access_code.errors.append("This access code already exists.")
            main_courses = MainCourse.query.order_by(MainCourse.created_at.desc()).all()
            return render_template("admin/manage_courses.html", form=form, main_courses=main_courses)

        while MainCourse.query.filter_by(access_code=access_code).first():
            access_code = MainCourse.generate_access_code()

        main_course = MainCourse(
            title=form.title.data.strip(),
            description=(form.description.data or "").strip(),
            access_code=access_code,
            is_active=True,
        )
        db.session.add(main_course)
        db.session.commit()

        flash(f"Main course created. Access code: {access_code}", "success")
        return redirect(url_for("admin.manage_courses"))

    main_courses = MainCourse.query.order_by(MainCourse.created_at.desc()).all()
    return render_template("admin/manage_courses.html", form=form, main_courses=main_courses)


@admin_bp.route("/courses/<int:main_course_id>/edit", methods=["GET", "POST"])
@login_required
@admin_permission_required("content")
def edit_course(main_course_id: int):
    """Edits a main course."""

    course = MainCourse.query.get_or_404(main_course_id)
    form = MainCourseForm(obj=course)

    if form.validate_on_submit():
        code = (form.access_code.data or course.access_code).strip().upper()
        duplicate = MainCourse.query.filter(MainCourse.access_code == code, MainCourse.id != course.id).first()
        if duplicate:
            form.access_code.errors.append("This access code already exists.")
            return render_template("admin/edit_course.html", form=form, course=course)

        course.title = form.title.data.strip()
        course.description = (form.description.data or "").strip()
        course.access_code = code
        db.session.commit()

        flash("Main course updated.", "success")
        return redirect(url_for("admin.manage_courses"))

    return render_template("admin/edit_course.html", form=form, course=course)


@admin_bp.route("/courses/<int:main_course_id>/delete", methods=["POST"])
@login_required
@admin_permission_required("content")
def delete_course(main_course_id: int):
    """Deletes a main course and its cascading content."""

    course = MainCourse.query.get_or_404(main_course_id)
    db.session.delete(course)
    db.session.commit()
    flash("Main course deleted.", "info")
    return redirect(url_for("admin.manage_courses"))


@admin_bp.route("/courses/<int:main_course_id>/sub-courses", methods=["GET", "POST"])
@login_required
@admin_permission_required("content")
def manage_sub_courses(main_course_id: int):
    """Creates sub-courses under a specific main course."""

    main_course = MainCourse.query.get_or_404(main_course_id)
    form = SubCourseForm()

    if form.validate_on_submit():
        sub_course = SubCourse(
            main_course_id=main_course.id,
            title=form.title.data.strip(),
            description=(form.description.data or "").strip(),
            sort_order=form.sort_order.data,
            is_published=True,
        )
        db.session.add(sub_course)
        db.session.commit()
        flash("Sub-course created successfully.", "success")
        return redirect(url_for("admin.manage_sub_courses", main_course_id=main_course.id))

    sub_courses = SubCourse.query.filter_by(main_course_id=main_course.id).order_by(SubCourse.sort_order.asc()).all()

    return render_template(
        "admin/manage_sub_courses.html",
        main_course=main_course,
        form=form,
        sub_courses=sub_courses,
    )


@admin_bp.route("/sub-courses/<int:sub_course_id>/edit", methods=["GET", "POST"])
@login_required
@admin_permission_required("content")
def edit_sub_course(sub_course_id: int):
    """Edits a sub-course."""

    sub_course = SubCourse.query.get_or_404(sub_course_id)
    form = SubCourseForm(obj=sub_course)

    if form.validate_on_submit():
        sub_course.title = form.title.data.strip()
        sub_course.description = (form.description.data or "").strip()
        sub_course.sort_order = form.sort_order.data
        db.session.commit()
        flash("Sub-course updated.", "success")
        return redirect(url_for("admin.manage_sub_courses", main_course_id=sub_course.main_course_id))

    return render_template("admin/edit_sub_course.html", form=form, sub_course=sub_course)


@admin_bp.route("/sub-courses/<int:sub_course_id>/delete", methods=["POST"])
@login_required
@admin_permission_required("content")
def delete_sub_course(sub_course_id: int):
    """Deletes a sub-course with child modules/content."""

    sub_course = SubCourse.query.get_or_404(sub_course_id)
    main_course_id = sub_course.main_course_id
    db.session.delete(sub_course)
    db.session.commit()

    flash("Sub-course deleted.", "info")
    return redirect(url_for("admin.manage_sub_courses", main_course_id=main_course_id))


@admin_bp.route("/sub-courses/<int:sub_course_id>/modules", methods=["GET", "POST"])
@login_required
@admin_permission_required("content")
def manage_modules(sub_course_id: int):
    """Creates modules inside a sub-course."""

    sub_course = SubCourse.query.get_or_404(sub_course_id)
    form = ModuleForm()

    if form.validate_on_submit():
        module = CourseModule(
            sub_course_id=sub_course.id,
            title=form.title.data.strip(),
            description=(form.description.data or "").strip(),
            sort_order=form.sort_order.data,
        )
        db.session.add(module)
        db.session.commit()
        flash("Module created successfully.", "success")
        return redirect(url_for("admin.manage_modules", sub_course_id=sub_course.id))

    modules = CourseModule.query.filter_by(sub_course_id=sub_course.id).order_by(CourseModule.sort_order.asc()).all()
    return render_template("admin/manage_modules.html", sub_course=sub_course, form=form, modules=modules)


@admin_bp.route("/modules/<int:module_id>/edit", methods=["GET", "POST"])
@login_required
@admin_permission_required("content")
def edit_module(module_id: int):
    """Edits a module."""

    module = CourseModule.query.get_or_404(module_id)
    form = ModuleForm(obj=module)

    if form.validate_on_submit():
        module.title = form.title.data.strip()
        module.description = (form.description.data or "").strip()
        module.sort_order = form.sort_order.data
        db.session.commit()
        flash("Module updated.", "success")
        return redirect(url_for("admin.manage_modules", sub_course_id=module.sub_course_id))

    return render_template("admin/edit_module.html", form=form, module=module)


@admin_bp.route("/modules/<int:module_id>/delete", methods=["POST"])
@login_required
@admin_permission_required("content")
def delete_module(module_id: int):
    """Deletes a module and its child lessons/quizzes."""

    module = CourseModule.query.get_or_404(module_id)
    sub_course_id = module.sub_course_id
    db.session.delete(module)
    db.session.commit()

    flash("Module deleted.", "info")
    return redirect(url_for("admin.manage_modules", sub_course_id=sub_course_id))


@admin_bp.route("/modules/<int:module_id>/lessons", methods=["GET", "POST"])
@login_required
@admin_permission_required("content")
def manage_lessons(module_id: int):
    """Creates lessons inside a module."""

    module = CourseModule.query.get_or_404(module_id)
    form = LessonForm()

    if form.validate_on_submit():
        lesson_type = LessonContentType(form.content_type.data)
        text_content = (form.text_content.data or "").strip()
        content_url = (form.content_url.data or "").strip()

        if lesson_type == LessonContentType.TEXT and not text_content:
            form.text_content.errors.append("Text content is required for text lessons.")
        elif lesson_type in {LessonContentType.VIDEO, LessonContentType.PDF} and not content_url:
            form.content_url.errors.append("Content URL is required for video/PDF lessons.")
        else:
            lesson = Lesson(
                module_id=module.id,
                title=form.title.data.strip(),
                content_type=lesson_type,
                content_url=content_url or None,
                text_content=text_content or None,
                sort_order=form.sort_order.data,
                is_published=form.is_published.data,
            )
            db.session.add(lesson)
            db.session.commit()
            flash("Lesson created successfully.", "success")
            return redirect(url_for("admin.manage_lessons", module_id=module.id))

    lessons = Lesson.query.filter_by(module_id=module.id).order_by(Lesson.sort_order.asc()).all()
    return render_template("admin/manage_lessons.html", module=module, form=form, lessons=lessons)


@admin_bp.route("/lessons/<int:lesson_id>/edit", methods=["GET", "POST"])
@login_required
@admin_permission_required("content")
def edit_lesson(lesson_id: int):
    """Edits lesson content and publish state."""

    lesson = Lesson.query.get_or_404(lesson_id)
    form = LessonForm(obj=lesson)

    if request.method == "GET":
        form.content_type.data = lesson.content_type.value

    if form.validate_on_submit():
        lesson_type = LessonContentType(form.content_type.data)
        text_content = (form.text_content.data or "").strip()
        content_url = (form.content_url.data or "").strip()

        if lesson_type == LessonContentType.TEXT and not text_content:
            form.text_content.errors.append("Text content is required for text lessons.")
            return render_template("admin/edit_lesson.html", form=form, lesson=lesson)

        if lesson_type in {LessonContentType.VIDEO, LessonContentType.PDF} and not content_url:
            form.content_url.errors.append("Content URL is required for video/PDF lessons.")
            return render_template("admin/edit_lesson.html", form=form, lesson=lesson)

        lesson.title = form.title.data.strip()
        lesson.content_type = lesson_type
        lesson.content_url = content_url or None
        lesson.text_content = text_content or None
        lesson.sort_order = form.sort_order.data
        lesson.is_published = bool(form.is_published.data)
        db.session.commit()

        flash("Lesson updated.", "success")
        return redirect(url_for("admin.manage_lessons", module_id=lesson.module_id))

    return render_template("admin/edit_lesson.html", form=form, lesson=lesson)


@admin_bp.route("/lessons/<int:lesson_id>/delete", methods=["POST"])
@login_required
@admin_permission_required("content")
def delete_lesson(lesson_id: int):
    """Deletes a lesson."""

    lesson = Lesson.query.get_or_404(lesson_id)
    module_id = lesson.module_id
    db.session.delete(lesson)
    db.session.commit()

    flash("Lesson deleted.", "info")
    return redirect(url_for("admin.manage_lessons", module_id=module_id))


@admin_bp.route("/modules/<int:module_id>/quizzes", methods=["GET", "POST"])
@login_required
@admin_permission_required("content")
def manage_quizzes(module_id: int):
    """Creates quizzes inside a module."""

    module = CourseModule.query.get_or_404(module_id)
    form = QuizForm()

    if form.validate_on_submit():
        quiz = Quiz(
            module_id=module.id,
            title=form.title.data.strip(),
            description=(form.description.data or "").strip(),
            is_published=form.is_published.data,
            time_limit_minutes=form.time_limit_minutes.data or None,
        )
        db.session.add(quiz)
        db.session.commit()
        flash("Quiz created successfully.", "success")
        return redirect(url_for("admin.manage_quizzes", module_id=module.id))

    quizzes = Quiz.query.filter_by(module_id=module.id).order_by(Quiz.created_at.desc()).all()
    return render_template("admin/manage_quizzes.html", module=module, form=form, quizzes=quizzes)


@admin_bp.route("/quizzes/<int:quiz_id>/edit", methods=["GET", "POST"])
@login_required
@admin_permission_required("content")
def edit_quiz(quiz_id: int):
    """Edits a quiz metadata and publish state."""

    quiz = Quiz.query.get_or_404(quiz_id)
    form = QuizForm(obj=quiz)

    if form.validate_on_submit():
        quiz.title = form.title.data.strip()
        quiz.description = (form.description.data or "").strip()
        quiz.time_limit_minutes = form.time_limit_minutes.data or None
        quiz.is_published = bool(form.is_published.data)
        db.session.commit()

        flash("Quiz updated.", "success")
        return redirect(url_for("admin.manage_quizzes", module_id=quiz.module_id))

    return render_template("admin/edit_quiz.html", form=form, quiz=quiz)


@admin_bp.route("/quizzes/<int:quiz_id>/delete", methods=["POST"])
@login_required
@admin_permission_required("content")
def delete_quiz(quiz_id: int):
    """Deletes a quiz and child questions/attempts."""

    quiz = Quiz.query.get_or_404(quiz_id)
    module_id = quiz.module_id
    db.session.delete(quiz)
    db.session.commit()

    flash("Quiz deleted.", "info")
    return redirect(url_for("admin.manage_quizzes", module_id=module_id))


@admin_bp.route("/quizzes/<int:quiz_id>/questions", methods=["GET", "POST"])
@login_required
@admin_permission_required("content")
def manage_questions(quiz_id: int):
    """Creates question sets for a quiz, including answer options."""

    quiz = Quiz.query.get_or_404(quiz_id)
    form = QuestionForm()

    if form.validate_on_submit():
        question_type = QuestionType(form.question_type.data)

        option_values = {
            "a": (form.option_a.data or "").strip(),
            "b": (form.option_b.data or "").strip(),
            "c": (form.option_c.data or "").strip(),
            "d": (form.option_d.data or "").strip(),
        }

        if question_type == QuestionType.MCQ:
            filtered_options = {key: value for key, value in option_values.items() if value}
            if len(filtered_options) < 2:
                flash("MCQ questions require at least 2 non-empty options.", "danger")
                questions = Question.query.filter_by(quiz_id=quiz.id).order_by(Question.sort_order.asc()).all()
                return render_template("admin/manage_questions.html", quiz=quiz, form=form, questions=questions)

            if form.correct_option.data not in filtered_options:
                flash("Select the correct MCQ option.", "danger")
                questions = Question.query.filter_by(quiz_id=quiz.id).order_by(Question.sort_order.asc()).all()
                return render_template("admin/manage_questions.html", quiz=quiz, form=form, questions=questions)

            question = Question(
                quiz_id=quiz.id,
                prompt=form.prompt.data.strip(),
                question_type=question_type,
                points=float(form.points.data),
                sort_order=form.sort_order.data,
            )
            db.session.add(question)
            db.session.flush()

            for key, value in filtered_options.items():
                db.session.add(
                    QuestionOption(
                        question_id=question.id,
                        option_text=value,
                        is_correct=(key == form.correct_option.data),
                    )
                )

        elif question_type == QuestionType.TRUE_FALSE:
            if form.true_false_correct.data not in {"true", "false"}:
                flash("Select the correct true/false value.", "danger")
                questions = Question.query.filter_by(quiz_id=quiz.id).order_by(Question.sort_order.asc()).all()
                return render_template("admin/manage_questions.html", quiz=quiz, form=form, questions=questions)

            question = Question(
                quiz_id=quiz.id,
                prompt=form.prompt.data.strip(),
                question_type=question_type,
                points=float(form.points.data),
                sort_order=form.sort_order.data,
            )
            db.session.add(question)
            db.session.flush()

            db.session.add_all(
                [
                    QuestionOption(
                        question_id=question.id,
                        option_text="True",
                        is_correct=form.true_false_correct.data == "true",
                    ),
                    QuestionOption(
                        question_id=question.id,
                        option_text="False",
                        is_correct=form.true_false_correct.data == "false",
                    ),
                ]
            )

        else:
            accepted_answers = [
                line.strip()
                for line in (form.accepted_answers.data or "").replace(",", "\n").splitlines()
                if line.strip()
            ]
            if not accepted_answers:
                flash("Short answer questions need at least one accepted answer.", "danger")
                questions = Question.query.filter_by(quiz_id=quiz.id).order_by(Question.sort_order.asc()).all()
                return render_template("admin/manage_questions.html", quiz=quiz, form=form, questions=questions)

            question = Question(
                quiz_id=quiz.id,
                prompt=form.prompt.data.strip(),
                question_type=question_type,
                points=float(form.points.data),
                sort_order=form.sort_order.data,
            )
            db.session.add(question)
            db.session.flush()

            for answer in accepted_answers:
                db.session.add(
                    QuestionOption(
                        question_id=question.id,
                        option_text=answer,
                        is_correct=True,
                    )
                )

        db.session.commit()
        flash("Question created successfully.", "success")
        return redirect(url_for("admin.manage_questions", quiz_id=quiz.id))

    questions = Question.query.filter_by(quiz_id=quiz.id).order_by(Question.sort_order.asc()).all()
    return render_template("admin/manage_questions.html", quiz=quiz, form=form, questions=questions)


@admin_bp.route("/questions/<int:question_id>/delete", methods=["POST"])
@login_required
@admin_permission_required("content")
def delete_question(question_id: int):
    """Deletes one quiz question."""

    question = Question.query.get_or_404(question_id)
    quiz_id = question.quiz_id
    db.session.delete(question)
    db.session.commit()

    flash("Question deleted.", "info")
    return redirect(url_for("admin.manage_questions", quiz_id=quiz_id))


@admin_bp.route("/plans", methods=["GET", "POST"])
@login_required
@admin_permission_required("content")
def manage_plans():
    """Creates and lists subscription plans."""

    form = SubscriptionPlanForm()

    if form.validate_on_submit():
        normalized_name = form.name.data.strip()
        existing = SubscriptionPlan.query.filter_by(name=normalized_name).first()
        if existing:
            form.name.errors.append("A plan with this name already exists.")
            plans = SubscriptionPlan.query.order_by(SubscriptionPlan.created_at.desc()).all()
            return render_template("admin/manage_plans.html", form=form, plans=plans)

        plan = SubscriptionPlan(
            name=normalized_name,
            description=(form.description.data or "").strip(),
            price=float(form.price.data),
            currency=form.currency.data.strip().upper(),
            billing_cycle=form.billing_cycle.data,
            features_json=(form.features_json.data or "").strip() or None,
            is_active=form.is_active.data,
        )
        db.session.add(plan)
        db.session.commit()
        flash("Subscription plan created.", "success")
        return redirect(url_for("admin.manage_plans"))

    plans = SubscriptionPlan.query.order_by(SubscriptionPlan.created_at.desc()).all()
    return render_template("admin/manage_plans.html", form=form, plans=plans)


@admin_bp.route("/plans/<int:plan_id>/toggle", methods=["POST"])
@login_required
@admin_permission_required("content")
def toggle_plan(plan_id: int):
    """Toggles activation status for a subscription plan."""

    plan = SubscriptionPlan.query.get_or_404(plan_id)
    plan.is_active = not plan.is_active
    db.session.commit()

    flash("Plan status updated.", "success")
    return redirect(url_for("admin.manage_plans"))
